from pvtrace.material.component import Absorber, Luminophore
from pvtrace.light.light import Light, rectangular_mask
from pvtrace.light.event import Event
from pvtrace.scene.node import Node
from pvtrace.material.material import Material
from pvtrace.material.utils import isotropic, cone, lambertian
from pvtrace.scene.scene import Scene
from pvtrace.geometry.box import Box
from pvtrace.geometry.utils import EPS_ZERO
from pvtrace.data import lumogen_f_red_305, fluro_red
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.material.surface import Surface, FresnelSurfaceDelegate
from pvtrace.material.distribution import Distribution
from pvtrace.algorithm import photon_tracer
from dataclasses import asdict
import numpy as np
import pandas as pd
import functools
import time


class OptionalMirrorAndSolarCell(FresnelSurfaceDelegate):
    """ A delegate adds an ideal specular mirror to the bottom surface and 
        perfectly indexed matched and perfectly absorbing solar cells to the edges.
    """

    def __init__(self, lsc):
        super(OptionalMirrorAndSolarCell, self).__init__()
        self.lsc = lsc

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        normal = geometry.normal(ray.position)
        cell_locations = self.lsc._solar_cell_surfaces
        back_surface_mirror = self.lsc._back_surface_mirror_info
        want_back_surface_mirror = back_surface_mirror["want_back_surface_mirror"]
        if np.allclose((0, 0, -1), normal) and want_back_surface_mirror:
            return 1.0  # perfect mirror
        elif np.allclose((-1, 0, 0), normal) and "left" in cell_locations:  # left
            return 0.0  # perfect absorption
        elif np.allclose((1, 0, 0), normal) and "right" in cell_locations:  # right
            return 0.0
        elif np.allclose((0, -1, 0), normal) and "near" in cell_locations:  # near
            return 0.0
        elif np.allclose((0, 1, 0), normal) and "far" in cell_locations:  # far
            return 0.0
        return super(OptionalMirrorAndSolarCell, self).reflectivity(
            surface, ray, geometry, container, adjacent
        )  # opt-out of handling custom reflection

    def transmitted_direction(self, surface, ray, geometry, container, adjacent):
        cell_locations = self.lsc._solar_cell_surfaces
        normal = geometry.normal(ray.position)
        if (
            (np.allclose((-1, 0, 0), normal) and "left" in cell_locations)
            or (np.allclose((1, 0, 0), normal) and "right" in cell_locations)
            or (np.allclose((0, -1, 0), normal) and "near" in cell_locations)
            or (np.allclose((0, 1, 0), normal) and "far" in cell_locations)
        ):
            return ray.direction  #  solar cell is perfectly index matched
        return super(OptionalMirrorAndSolarCell, self).transmitted_direction(
            surface, ray, geometry, container, adjacent
        )  # opt-out of handling custom reflection


class AirGapMirror(FresnelSurfaceDelegate):
    def __init__(self, lsc):
        super(AirGapMirror, self).__init__()
        self.lsc = lsc

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        return 1.0  # perfect reflector. NB don't reduce.

    def reflected_direction(self, surface, ray, geometry, container, adjacent):
        if not self.lsc._air_gap_mirror_info["lambertian"]:
            # Specular reflection
            return super(AirGapMirror, self).transmitted_direction(
                surface, ray, geometry, container, adjacent
            )
        else:
            normal = geometry.normal(ray.position)
            if not np.allclose((0.0, 0.0, 1.0), normal):  # top surface
                raise NotImplementedError("Not yet generalised to other surfaces.")
            # Currently this return lambertian direction along +z axis and is not
            # generalised to other orientations. This is simple to do using a transform
            # which first moves into to the z+ frame and then back out.
            return tuple(lambertian().tolist())


class LSC(object):
    """Abstraction of a luminescent solar concentrator.
    
       This is intended to be a high-level API to easy use.
    """

    def __init__(self, size, wavelength_range=None, n0=1.0, n1=1.5):
        super(LSC, self).__init__()
        if wavelength_range is None:
            self.wavelength_range = np.arange(400, 800)

        self.size = size  # centimetres
        self.n0 = n0
        self.n1 = n1

        self._solar_cell_surfaces = set()
        self._back_surface_mirror_info = {"want_back_surface_mirror": False}
        self._air_gap_mirror_info = {"want_air_gap_mirror": False, "lambertian": False}
        self._scene = None
        self._renderer = None
        self._store = None
        self._df = None
        self._counts = None
        self._user_lights = []
        self._user_components = []

    def _make_default_components(self):
        """ Default LSC contains Lumogen F Red 305. With concentration such that
            the absorption coefficient at peak is 10 cm-1.
        """
        x = self.wavelength_range
        coefficient = lumogen_f_red_305.absorption(x) * 10.0  # cm-1
        emission = lumogen_f_red_305.emission(x)
        coefficient = np.column_stack((x, coefficient))
        emission = np.column_stack((x, emission))
        lumogen = {
            "cls": Luminophore,
            "name": "Lumogen F Red 305",
            "coefficient": coefficient,
            "emission": emission,
            "quantum_yield": 1.0,
            "phase_function": None,  # will select isotropic
        }
        background = {"cls": Absorber, "coefficient": 0.1, "name": "Background"}  # cm-1
        return [lumogen, background]

    def _make_default_lights(self):
        """ Default light is a spotlight (cone of 20-deg) of single wavelength 555nm.
        """
        light = {
            "name": "Light",
            "location": (0.0, 0.0, self.size[-1] * 5),
            "rotation": (np.radians(180), (1, 0, 0)),
            "direction": functools.partial(cone, np.radians(20)),
            "wavelength": None,
            "position": None,
        }
        return [light]

    def _make_scene(self):
        """ Creates the scene based on configuration values.
        """
        # Make world node
        (l, w, d) = self.size
        world = Node(
            name="World",
            geometry=Box(
                (l * 100, w * 100, d * 100), material=Material(refractive_index=self.n0)
            ),
        )

        # Create components (Absorbers, Luminophores and Scatteres)
        if len(self._user_components) == 0:
            self._user_components = self._make_default_components()
        components = []
        for component_data in self._user_components:
            cls = component_data.pop("cls")
            coefficient = component_data.pop("coefficient")
            component = cls(coefficient, **component_data)
            components.append(component)

        # Create LSC node
        lsc = Node(
            name="LSC",
            geometry=Box(
                (l, w, d),
                material=Material(
                    refractive_index=self.n1,
                    components=components,
                    surface=Surface(delegate=OptionalMirrorAndSolarCell(self)),
                ),
            ),
            parent=world,
        )

        if self._air_gap_mirror_info["want_air_gap_mirror"]:
            sheet_thickness = 0.25 * d  # make it appear thinner than the LSC
            air_gap_mirror = Node(
                name="Air Gap Mirror",
                geometry=Box(
                    (l, w, sheet_thickness),  # same surface air but very thin
                    material=Material(
                        refractive_index=self.n0,
                        components=[],
                        surface=Surface(delegate=AirGapMirror(self)),
                    ),
                ),
                parent=world,
            )
            # Move adjacent to bottom surface with a small air gap
            air_gap_mirror.translate((0.0, 0.0, -(0.5 * d + sheet_thickness)))

        # Use user light if any have been given, otherwise use default values.
        if len(self._user_lights) == 0:
            self._user_lights = self._make_default_lights()

        # Create light nodes
        for light_data in self._user_lights:
            name = light_data["name"]
            light = Light(
                name=name,
                direction=light_data["direction"],
                wavelength=light_data["wavelength"],
                position=light_data["position"],
            )
            light_node = Node(name=name, light=light, parent=world)
            light_node.location = light_data["location"]
            if light_data["rotation"]:
                light_node.rotate(*light_data["rotation"])

        self._scene = Scene(world)

    def component_names(self):
        if self._scene is None:
            raise ValueError("Run a simulation before calling this method.")
        return {c["name"] for c in self._user_components}

    def light_names(self):
        if self._scene is None:
            raise ValueError("Run a simulation before calling this method.")
        return {l["name"] for l in self._user_lights}

    def add_luminophore(
        self, name, coefficient, emission, quantum_yield, phase_function=None
    ):
        self._user_components.append(
            {
                "cls": Luminophore,
                "name": name,
                "coefficient": coefficient,
                "emission": emission,
                "quantum_yield": quantum_yield,
                "phase_function": phase_function,
            }
        )

    def add_absorber(self, name, coefficient):
        self._user_components.append(
            {"cls": Absorber, "name": name, "coefficient": coefficient}
        )

    def add_scatterer(self, name, coefficient, phase_function=None):
        self._user_components.append(
            {
                "cls": Scatterer,
                "name": name,
                "coefficient": coefficient,
                "phase_function": phase_function,
            }
        )

    def add_light(
        self,
        name,
        location,  # node location in parent
        rotation=None,  # node rotation in parent frame
        direction=None,  # direction delegate callable
        wavelength=None,  # wavelength delegate callable
        position=None,  # position delegate callable
    ):
        self._user_lights.append(
            {
                "name": name,
                "location": location,
                "rotation": rotation,
                "direction": direction,
                "wavelength": wavelength,
                "position": position,
            }
        )

    def add_solar_cell(self, facets):
        if not isinstance(facets, (list, tuple, set)):
            raise ValueError("Facets should be a set. e.g. `{'left', 'right'}`")
        facets = set(facets)
        allowed = {"left", "near", "far", "right"}
        if not facets.issubset(allowed):
            raise ValueError("Solar cell have allowed surfaces", allowed)

        self._solar_cell_surfaces = facets.union(self._solar_cell_surfaces)

    def add_back_surface_mirror(self):
        self._back_surface_mirror_info = {"want_back_surface_mirror": True}

    def add_air_gap_mirror(self, lambertian=False):
        self._air_gap_mirror_info = {
            "want_air_gap_mirror": True,
            "lambertian": lambertian,
        }

    # Simulate

    def show(
        self,
        wireframe=True,
        baubles=True,
        bauble_radius=None,
        world_segment="short",
        short_length=None,
        open_browser=False,
    ):

        if bauble_radius is None:
            bauble_radius = np.min(self.size) * 0.05

        if short_length is None:
            short_length = np.min(self.size) * 0.1

        self._add_history_kwargs = {
            "bauble_radius": bauble_radius,
            "baubles": baubles,
            "world_segment": world_segment,
            "short_length": short_length,
        }

        if self._scene is None:
            self._make_scene()

        self._renderer = MeshcatRenderer(
            open_browser=open_browser,
            transparency=False,
            opacity=0.5,
            wireframe=wireframe,
            max_histories=50,
        )
        self._renderer.render(self._scene)
        time.sleep(1.0)
        return self._renderer

    def simulate(self, n, progress=None, emit_method="kT"):
        if self._scene is None:
            self._make_scene()
        scene = self._scene

        # Simulate can be called multiple time to append rays to the store
        if self._store is None:
            store = {"entrance_rays": [], "exit_rays": []}

        vis = self._renderer
        count = 0
        for ray in scene.emit(n):
            history = photon_tracer.follow(scene, ray, emit_method=emit_method)
            rays, events = zip(*history)
            store["entrance_rays"].append((rays[1], events[1]))
            if events[-1] in (Event.ABSORB, Event.KILL):
                # final event is a lost store path information at final event
                store["exit_rays"].append((rays[-1], events[-1]))
            elif events[-1] == Event.EXIT:
                # final event hits the world node. Store path information at
                # penultimate location
                store["exit_rays"].append((rays[-2], events[-2]))

            # Update visualiser
            if vis:
                vis.add_history(history, **self._add_history_kwargs)

            # Progress callback
            if progress:
                count += 1
                progress(count)

        self._store = store
        print("Tracing finished.")
        print("Preparing results.")
        df = self._make_dataframe()
        df = self.expand_coords(df, "direction")
        df = self.expand_coords(df, "position")
        df = self.label_facets(df, *self.size)
        self._df = df

    def _make_dataframe(self):

        # to-do: Only need to process additional rays not whole dataframe! Optimise!
        df = pd.DataFrame()

        # Rays entering the scene
        for ray, event in self._store["entrance_rays"]:
            rep = asdict(ray)
            rep["kind"] = "entrance"
            rep["event"] = event.name.lower()
            df = df.append(rep, ignore_index=True)

        # Rays exiting the scene
        for ray, event in self._store["exit_rays"]:
            rep = asdict(ray)
            rep["kind"] = "exit"
            rep["event"] = event.name.lower()
            df = df.append(rep, ignore_index=True)

        self._df = df
        return df

    def expand_coords(self, df, column):
        """ Returns a dataframe with coordinate column expanded into components.
    
            Parameters
            ----------
            df : pandas.DataFrame
                The dataframe
            column : str
                The column label
        
            Returns
            -------
            df : pandas.DataFrame
                The dataframe with the column expanded.
        
            Example
            -------
            Given the dataframe::
        
                df = pd.DataFrame({'position': [(1,2,3)]})
        
            the function will return a new dataframe::
        
                edf = expand_coords(df, 'position')
                edf == pd.DataFrame({'position_x': [1], 'position_y': [2], 'position_z': [3]})
        
        """
        coords = np.stack(df[column].values)
        df["{}_x".format(column)] = coords[:, 0]
        df["{}_y".format(column)] = coords[:, 1]
        df["{}_z".format(column)] = coords[:, 2]
        df.drop(columns=column, inplace=True)
        return df

    def label_facets(self, df, length, width, height):
        """ Label rows with facet names for a box LSC.
    
            Notes
            -----
            This function only works if the coordinates in the dataframe
            are in the local frame of the box. If the coordinates are in the
            world frame then this will still work provided the box is axis
            aligned with the world node and centred at the origin.
        """
        xmin, xmax = -0.5 * length, 0.5 * length
        ymin, ymax = -0.5 * width, 0.5 * width
        zmin, zmax = -0.5 * height, 0.5 * height
        df.loc[(np.isclose(df["position_x"], xmin, atol=EPS_ZERO)), "facet"] = "left"
        df.loc[(np.isclose(df["position_x"], xmax, atol=EPS_ZERO)), "facet"] = "right"
        df.loc[(np.isclose(df["position_y"], ymin, atol=EPS_ZERO)), "facet"] = "far"
        df.loc[(np.isclose(df["position_y"], ymax, atol=EPS_ZERO)), "facet"] = "near"
        df.loc[(np.isclose(df["position_z"], zmin, atol=EPS_ZERO)), "facet"] = "bottom"
        df.loc[(np.isclose(df["position_z"], zmax, atol=EPS_ZERO)), "facet"] = "top"
        return df

    def _make_counts(self, df):

        if self._counts is not None:
            return self._counts

        components = self._scene.component_nodes
        lights = self._scene.light_nodes
        all_components = {component.name for component in components}
        all_lights = {light.name for light in lights}

        # Count solar photons exiting
        solar_out = dict()
        for facet in {"left", "right", "near", "far", "top", "bottom"}:
            solar_out[facet] = self.spectrum(
                facets={facet}, source=all_lights, kind="last"
            ).shape[0]

        # Count solar photons entering
        solar_in = dict()
        for facet in {"left", "right", "near", "far", "top", "bottom"}:
            solar_in[facet] = self.spectrum(
                facets={facet}, source=all_lights, kind="first"
            ).shape[0]

        # Count luminescent photons exiting
        lum_out = dict()
        for facet in {"left", "right", "near", "far", "top", "bottom"}:
            lum_out[facet] = self.spectrum(
                facets={facet}, source=all_components, kind="last"
            ).shape[0]

        # Count luminescent photons entering
        lum_in = dict()
        for facet in {"left", "right", "near", "far", "top", "bottom"}:
            lum_in[facet] = self.spectrum(
                facets={facet}, source=all_components, kind="first"
            ).shape[0]

        self._counts = counts = pd.DataFrame(
            {
                "Solar In": pd.Series(solar_in),
                "Solar Out": pd.Series(solar_out),
                "Luminescent Out": pd.Series(lum_out),
                "Luminescent In": pd.Series(lum_in),
            },
            index=["left", "right", "near", "far", "top", "bottom"],
        )
        return counts

    def spectrum(self, facets=set(), kind="last", source="all", events=None):
        if self._df is None:
            raise ValueError("Run a simulation before calling this method.")

        df = self._df

        if kind is not None:
            if not kind in {"first", "last"}:
                raise ValueError("Direction must be either `'first'` or `'last'.`")

        if kind is None:
            want_kind = True  # Opt-out
        else:
            if kind == "first":
                want_kind = df["kind"] == "entrance"
            else:
                want_kind = df["kind"] == "exit"

        all_sources = self.component_names() | self.light_names()
        if source == "all":
            want_sources = all_sources
        else:
            if isinstance(source, str):
                source = {source}
            if not set(source).issubset(all_sources):
                unknown_source_set = set(source).difference(all_sources)
                raise ValueError("Unknown source requested.", unknown_source_set)

        if source == "all":
            want_source = df["source"].isin(all_sources)
        else:
            want_source = df["source"].isin(set(source))

        if isinstance(facets, (list, tuple, set)):
            if len(facets) > 0:
                want_facets = df["facet"].isin(set(facets))
            else:
                want_facets = True  # don't filter by facets
        else:
            raise ValueError(
                "`'facets'` should be a set `{'left', 'right'}`", {"got": facets}
            )

        if events is None:
            want_events = True  # Don't filter by events
        else:
            all_events = {e.name.lower() for e in Event}
            if isinstance(events, (list, tuple, set)):
                events = set(events)
                if events.issubset(all_events):
                    want_events = df["event"].isin(events)
                else:
                    raise ValueError(
                        "Contained some unknown events",
                        {"got": events, "expected": all_events},
                    )
            else:
                raise ValueError(
                    "Events must be set of event strings", {"allowed": all_events}
                )

        return df.loc[want_kind & want_source & want_facets & want_events]["wavelength"]

    def counts(self):
        df = self._df
        if df is None:
            df = self._make_dataframe()
            df = self.expand_coords(df, "direction")
            df = self.expand_coords(df, "position")
            df = self.label_facets(df, *self.size)

        counts = self._make_counts(df)
        return counts

    def summary(self):
        counts = self._make_counts(self._df)
        all_facets = {"left", "right", "near", "far", "top", "bottom"}

        lum_collected = 0
        for facet in self._solar_cell_surfaces:
            lum_collected += counts["Luminescent Out"][facet]

        lum_escaped = 0
        for facet in all_facets - self._solar_cell_surfaces:
            lum_escaped += counts["Luminescent Out"][facet]

        incident = 0
        for facet in all_facets:
            incident += counts["Solar In"][facet]

        lost = self.spectrum(source="all", events={"absorb"}, kind="last").shape[0]

        optical_efficiency = lum_collected / incident
        waveguide_efficiency = lum_collected / (lum_collected + lum_escaped)

        (l, w, d) = self.size
        a1 = w * l
        a2 = 2 * l * d + 2 * w * d
        Cg = a1 / a2
        n = self.n1
        s = pd.Series(
            {
                "Optical Efficiency": optical_efficiency,
                "Waveguide Efficiency": waveguide_efficiency,
                "Waveguide Efficiency (Thermodynamic Prediction)": (
                    n ** 2 / (Cg + n ** 2)
                ),
                "Non-radiative Loss (fraction):": lost / incident,
                "Incident": incident,
                "Geometric Concentration": Cg,
                "Refractive Index": n,
                "Cell Surfaces": self._solar_cell_surfaces,
                "Components": self.component_names(),
                "Lights": self.light_names(),
            }
        )
        return s

    def report(self):
        print()
        print("Simulation Report")
        print("-----------------")
        print()
        print("Surface Counts:")
        print(self.counts())
        print()
        print("Summary:")
        print(self.summary())


def test1():
    x = np.arange(400, 801, dtype=np.float)
    size = (l, w, d) = (4.8, 1.8, 0.250)  # cm-1
    lsc = LSC(size, wavelength_range=x)

    lsc.add_luminophore(
        "Fluro Red",
        np.column_stack((x, fluro_red.absorption(x) * 11.387815)),  # cm-1
        np.column_stack((x, fluro_red.emission(x))),
        quantum_yield=0.95,
    )

    lsc.add_absorber("PMMA", 0.02)  # cm-1

    def lamp_spectrum(x):
        """ Fit to an experimentally measured lamp spectrum with long wavelength filter.
        """

        def g(x, a, p, w):
            return a * np.exp(-(((p - x) / w) ** 2))

        a1 = 0.53025700136646192
        p1 = 512.91400020614333
        w1 = 93.491838802960473
        a2 = 0.63578999789955015
        p2 = 577.63100003089369
        w2 = 66.031706473985736
        return g(x, a1, p1, w1) + g(x, a2, p2, w2)

    lamp_dist = Distribution(x, lamp_spectrum(x))
    wavelength_callable = lambda: lamp_dist.sample(np.random.uniform())
    position_callable = lambda: rectangular_mask(l / 2, w / 2)
    lsc.add_light(
        "Oriel Lamp + Filter",
        (0.0, 0.0, 0.5 * d + 0.01),  # put close to top surface
        rotation=(np.radians(180), (1, 0, 0)),  # normal and into the top surface
        wavelength=wavelength_callable,  # wavelength delegate callable
        position=position_callable,  # uniform surface illumination
    )

    lsc.show()
    throw = 2500
    lsc.simulate(throw, emit_method="redshift")
    edge = lsc.spectrum(facets={"left", "right", "near", "far"}, source="all")
    escape = lsc.spectrum(facets={"top", "bottom"}, source="all")
    lost = lsc.spectrum(source="all", events={"absorb"})

    import matplotlib.pyplot as plt

    plt.hist(edge, bins=np.linspace(400, 800, 10), label="edge")
    plt.hist(escape, bins=np.linspace(400, 800, 10), label="escape")
    plt.hist(lost, bins=np.linspace(400, 800, 10), label="lost")
    plt.show()
    # number of lamp rays hitting the top surface
    incident = lsc.spectrum(
        source={"Oriel Lamp + Filter"}, kind="first", facets={"top"}
    )
    hitting = len(incident)
    counts = {"edge": len(edge), "escape": len(escape), "lost": len(lost)}
    fractions = {
        "edge": counts["edge"] / hitting,
        "escape": counts["escape"] / hitting,
        "lost": counts["lost"] / hitting,
    }
    print(counts, "sum", np.sum(list(counts.values())))
    print(fractions, "sum", np.sum(list(fractions.values())))


def test2():
    x = np.arange(400, 801, dtype=np.float)
    size = (l, w, d) = (4.8, 1.8, 0.250)  # cm-1
    lsc = LSC(size, wavelength_range=x)

    lsc.add_luminophore(
        "Fluro Red",
        np.column_stack((x, fluro_red.absorption(x) * 11.387815)),  # cm-1
        np.column_stack((x, fluro_red.emission(x))),
        quantum_yield=0.95,
    )

    lsc.add_absorber("PMMA", 0.02)  # cm-1

    def lamp_spectrum(x):
        """ Fit to an experimentally measured lamp spectrum with long wavelength filter.
        """

        def g(x, a, p, w):
            return a * np.exp(-(((p - x) / w) ** 2))

        a1 = 0.53025700136646192
        p1 = 512.91400020614333
        w1 = 93.491838802960473
        a2 = 0.63578999789955015
        p2 = 577.63100003089369
        w2 = 66.031706473985736
        return g(x, a1, p1, w1) + g(x, a2, p2, w2)

    lamp_dist = Distribution(x, lamp_spectrum(x))
    wavelength_callable = lambda: lamp_dist.sample(np.random.uniform())
    position_callable = lambda: rectangular_mask(l / 2, w / 2)
    lsc.add_light(
        "Oriel Lamp + Filter",
        (0.0, 0.0, 0.5 * d + 0.01),  # put close to top surface
        rotation=(np.radians(180), (1, 0, 0)),  # normal and into the top surface
        wavelength=wavelength_callable,  # wavelength delegate callable
        position=position_callable,  # uniform surface illumination
    )

    lsc.add_solar_cell({"left", "right", "near", "far"})
    lsc.add_air_gap_mirror(lambertian=False)

    lsc.show()
    throw = 300
    lsc.simulate(throw, emit_method="redshift")
    lsc.report()


if __name__ == "__main__":
    test2()
