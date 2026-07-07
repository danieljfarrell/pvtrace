"""Compile a pvtrace Scene into flat numpy tables for the native kernel.

The scene graph, geometry objects, materials and components are Python
objects with per-ray callbacks; the compiler lowers the supported subset
of them into arrays so the tracing loop never needs to call back into
Python. Scenes using custom delegates, custom phase functions, meshes or
histogram-sampled spectra are rejected with ``UnsupportedSceneError`` so
callers can fall back to the Python tracer.
"""
import numpy as np
from anytree import PreOrderIter

from pvtrace.engine.recorder import EVENTS, PROPERTIES, Heatmap, Histogram, Recorder
from pvtrace.geometry.box import Box
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.sphere import Sphere
from pvtrace.material.component import Absorber, Luminophore, Reactor, Scatterer
from pvtrace.material.surface import FresnelSurfaceDelegate, NullSurfaceDelegate
from pvtrace.material.utils import Cone, HenyeyGreenstein, isotropic

# Volume interaction selectors cannot be restricted by surface facet
VOLUME_EVENTS = {"lost", "reacted", "killed"}
MAX_RECORDERS = 256  # per-ray distinct tracking array size in the kernel

# Geometry type tags
GEOM_BOX = 0
GEOM_SPHERE = 1
GEOM_CYLINDER = 2

# Surface type tags
SURF_FRESNEL = 0
SURF_NULL = 1

# Component type tags
COMP_ABSORBER = 0
COMP_SCATTERER = 1
COMP_LUMINOPHORE = 2
COMP_REACTOR = 3

# Phase function tags
PHASE_ISOTROPIC = 0
PHASE_HENYEY_GREENSTEIN = 1
PHASE_CONE = 2

# Emission method tags
EMIT_KT = 0
EMIT_REDSHIFT = 1
EMIT_FULL = 2

EMIT_METHODS = {"kT": EMIT_KT, "redshift": EMIT_REDSHIFT, "full": EMIT_FULL}


class UnsupportedSceneError(Exception):
    """The scene uses a feature the compiled engine does not support."""


class CompiledScene:
    """Flat-table representation of a scene for the native kernel."""

    def __init__(self, scene):
        nodes = [
            node for node in PreOrderIter(scene.root) if node.geometry is not None
        ]
        if len(nodes) == 0:
            raise UnsupportedSceneError("Scene has no geometry nodes.")
        if scene.root.geometry is None:
            raise UnsupportedSceneError("Root node must have a geometry.")

        n = len(nodes)
        self.scene = scene
        self.nodes = nodes
        self.node_names = [node.name for node in nodes]
        self.root_id = nodes.index(scene.root)

        self.geom_type = np.zeros(n, dtype=np.int32)
        self.geom_params = np.zeros((n, 4), dtype=np.float64)
        self.local_to_world = np.zeros((n, 4, 4), dtype=np.float64)
        self.world_to_local = np.zeros((n, 4, 4), dtype=np.float64)
        self.refractive_index = np.zeros(n, dtype=np.float64)
        self.surface_type = np.zeros(n, dtype=np.int32)
        self.comp_start = np.zeros(n, dtype=np.int32)
        self.comp_count = np.zeros(n, dtype=np.int32)

        comp_rows = []
        abs_x, abs_y = [], []
        ems_x, ems_cdf = [], []
        self.component_names = []

        for i, node in enumerate(nodes):
            geometry = node.geometry
            self._compile_geometry(i, geometry)
            self._compile_transform(i, node, scene.root)

            material = geometry.material
            if material is None:
                raise UnsupportedSceneError(
                    f"Node {node.name!r} has geometry without a material."
                )
            self.refractive_index[i] = float(material.refractive_index)
            self.surface_type[i] = self._surface_tag(node, material)

            self.comp_start[i] = len(comp_rows)
            for component in material.components:
                comp_rows.append(
                    self._compile_component(
                        node, component, abs_x, abs_y, ems_x, ems_cdf
                    )
                )
                self.component_names.append(component.name)
            self.comp_count[i] = len(material.components)

        # Component table columns
        if comp_rows:
            rows = np.array(comp_rows, dtype=np.float64)
        else:
            rows = np.zeros((0, 10), dtype=np.float64)
        self.comp_type = rows[:, 0].astype(np.int32)
        self.comp_qy = rows[:, 1].copy()
        self.comp_tau_rad = rows[:, 2].copy()
        self.comp_tau_nr = rows[:, 3].copy()
        self.comp_phase_type = rows[:, 4].astype(np.int32)
        self.comp_phase_param = rows[:, 5].copy()
        self.comp_abs_start = rows[:, 6].astype(np.int32)
        self.comp_abs_n = rows[:, 7].astype(np.int32)
        self.comp_ems_start = rows[:, 8].astype(np.int32)
        self.comp_ems_n = rows[:, 9].astype(np.int32)

        self.abs_x = np.array(abs_x, dtype=np.float64)
        self.abs_y = np.array(abs_y, dtype=np.float64)
        self.ems_x = np.array(ems_x, dtype=np.float64)
        self.ems_cdf = np.array(ems_cdf, dtype=np.float64)

        self._compile_recorders(nodes)

    def _compile_recorders(self, nodes):
        recorders = []
        for i, node in enumerate(nodes):
            for recorder in getattr(node, "recorders", []):
                if not isinstance(recorder, Recorder):
                    raise UnsupportedSceneError(
                        f"Node {node.name!r} recorders must be Recorder objects."
                    )
                if recorder.event in VOLUME_EVENTS and recorder.facet is not None:
                    raise UnsupportedSceneError(
                        f"Recorder {recorder.name!r}: facet filters only apply "
                        "to surface events."
                    )
                recorders.append((i, recorder))
        if len(recorders) > MAX_RECORDERS:
            raise UnsupportedSceneError(
                f"At most {MAX_RECORDERS} recorders are supported."
            )
        names = [rec.name for _, rec in recorders]
        if len(set(names)) != len(names):
            raise UnsupportedSceneError("Recorder names must be unique.")

        n = len(recorders)
        self.recorder_names = names
        self.recorder_specs = [rec for _, rec in recorders]
        self.rec_node = np.zeros(n, dtype=np.int32)
        self.rec_event = np.zeros(n, dtype=np.int32)
        self.rec_has_facet = np.zeros(n, dtype=np.int32)
        self.rec_facet = np.zeros((max(n, 1), 3), dtype=np.float64)
        self.rec_atol = np.zeros(n, dtype=np.float64)
        self.rec_hist_start = np.zeros(n, dtype=np.int32)
        self.rec_hist_n = np.zeros(n, dtype=np.int32)

        h_rows = []
        offset = 0
        for r, (node_index, recorder) in enumerate(recorders):
            self.rec_node[r] = node_index
            self.rec_event[r] = EVENTS[recorder.event]
            if recorder.facet is not None:
                self.rec_has_facet[r] = 1
                self.rec_facet[r] = recorder.facet
            self.rec_atol[r] = recorder.atol
            self.rec_hist_start[r] = len(h_rows)
            for hist in recorder.histograms:
                if isinstance(hist, Heatmap):
                    a, b = hist.a, hist.b
                    h_rows.append(
                        [PROPERTIES[a.prop], PROPERTIES[b.prop], a.bins, b.bins,
                         a.start, a.stop, b.start, b.stop, offset]
                    )
                    offset += a.bins * b.bins
                else:
                    h_rows.append(
                        [PROPERTIES[hist.prop], -1, hist.bins, 1,
                         hist.start, hist.stop, 0.0, 1.0, offset]
                    )
                    offset += hist.bins
            self.rec_hist_n[r] = len(recorder.histograms)

        rows = np.array(h_rows, dtype=np.float64) if h_rows else np.zeros((0, 9))
        self.hist_prop_a = rows[:, 0].astype(np.int32)
        self.hist_prop_b = rows[:, 1].astype(np.int32)
        self.hist_na = rows[:, 2].astype(np.int32)
        self.hist_nb = rows[:, 3].astype(np.int32)
        self.hist_lo_a = rows[:, 4].copy()
        self.hist_hi_a = rows[:, 5].copy()
        self.hist_lo_b = rows[:, 6].copy()
        self.hist_hi_b = rows[:, 7].copy()
        self.hist_offset = rows[:, 8].astype(np.int32)
        self.total_bins = offset

    # -- geometry ------------------------------------------------------

    def _compile_geometry(self, i, geometry):
        if isinstance(geometry, Box):
            self.geom_type[i] = GEOM_BOX
            size = np.asarray(geometry._size, dtype=np.float64)
            self.geom_params[i, :3] = size
        elif isinstance(geometry, Sphere):
            self.geom_type[i] = GEOM_SPHERE
            self.geom_params[i, 0] = float(geometry.radius)
        elif isinstance(geometry, Cylinder):
            self.geom_type[i] = GEOM_CYLINDER
            self.geom_params[i, 0] = float(geometry.length)
            self.geom_params[i, 1] = float(geometry.radius)
        else:
            raise UnsupportedSceneError(
                f"Geometry type {type(geometry).__name__} is not supported."
            )

    def _compile_transform(self, i, node, root):
        l2w = np.asarray(node.transformation_to(root), dtype=np.float64)
        rotation = l2w[:3, :3]
        if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-9):
            raise UnsupportedSceneError(
                f"Node {node.name!r} transform is not rigid (has scale or shear)."
            )
        self.local_to_world[i] = l2w
        self.world_to_local[i] = np.linalg.inv(l2w)

    # -- surfaces ------------------------------------------------------

    def _surface_tag(self, node, material):
        delegate = material.surface.delegate
        if type(delegate) is FresnelSurfaceDelegate:
            return SURF_FRESNEL
        if type(delegate) is NullSurfaceDelegate:
            return SURF_NULL
        raise UnsupportedSceneError(
            f"Node {node.name!r} uses surface delegate "
            f"{type(delegate).__name__}; only FresnelSurfaceDelegate and "
            "NullSurfaceDelegate are supported."
        )

    # -- components ----------------------------------------------------

    def _compile_component(self, node, component, abs_x, abs_y, ems_x, ems_cdf):
        # Order matters: Reactor < Absorber < Scatterer, Luminophore < Scatterer
        if isinstance(component, Reactor):
            ctype = COMP_REACTOR
        elif isinstance(component, Absorber):
            ctype = COMP_ABSORBER
        elif isinstance(component, Luminophore):
            ctype = COMP_LUMINOPHORE
        elif isinstance(component, Scatterer):
            ctype = COMP_SCATTERER
        else:
            raise UnsupportedSceneError(
                f"Component type {type(component).__name__} is not supported."
            )

        phase_type, phase_param = self._phase_tag(node, component)

        a_start, a_n = self._compile_distribution(
            node, component._abs_dist, abs_x, abs_y
        )

        e_start, e_n = 0, 0
        if ctype == COMP_LUMINOPHORE:
            dist = component._ems_dist
            if dist.hist:
                raise UnsupportedSceneError(
                    f"Node {node.name!r}: histogram-sampled emission spectra "
                    "are not supported."
                )
            e_start = len(ems_x)
            ems_x.extend(np.asarray(dist._x, dtype=np.float64).tolist())
            ems_cdf.extend(np.asarray(dist._cdf, dtype=np.float64).tolist())
            e_n = len(ems_x) - e_start

        tau_rad = component.tau_rad if component.tau_rad else 0.0
        tau_nr = component.tau_nr if component.tau_nr else 0.0
        return [
            float(ctype),
            float(component.quantum_yield),
            float(tau_rad),
            float(tau_nr),
            float(phase_type),
            float(phase_param),
            float(a_start),
            float(a_n),
            float(e_start),
            float(e_n),
        ]

    def _phase_tag(self, node, component):
        phase = component.phase_function
        if phase is isotropic:
            return PHASE_ISOTROPIC, 0.0
        if isinstance(phase, HenyeyGreenstein):
            return PHASE_HENYEY_GREENSTEIN, float(phase.g)
        if isinstance(phase, Cone):
            return PHASE_CONE, float(phase.theta_max)
        raise UnsupportedSceneError(
            f"Node {node.name!r}: custom phase functions are not supported."
        )

    def _compile_distribution(self, node, dist, xs, ys):
        if dist.hist:
            raise UnsupportedSceneError(
                f"Node {node.name!r}: histogram-sampled spectra are not "
                "supported."
            )
        start = len(xs)
        if dist._x is None:
            # Constant coefficient
            xs.append(0.0)
            ys.append(float(dist._y))
            return start, 1
        xs.extend(np.asarray(dist._x, dtype=np.float64).tolist())
        ys.extend(np.asarray(dist._y, dtype=np.float64).tolist())
        return start, len(xs) - start


def compile_scene(scene) -> CompiledScene:
    """Compile `scene` into flat tables, or raise `UnsupportedSceneError`."""
    return CompiledScene(scene)
