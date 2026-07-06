"""
Parses the pvtrace-scene.yml file and generates Python objects.
"""

from pvtrace.material.distribution import Distribution
from pvtrace.material.component import Luminophore, Scatterer
import jsonschema
import yaml
import json
import numpy
import pandas
import os
import trimesh
import numpy as np
import pvtrace
from typing import Callable, Tuple, List, Dict, Optional
from pvtrace import (
    Scene,
    Box,
    Mesh,
    Cylinder,
    Sphere,
    Material,
    Node,
    Absorber,
    Scatterer,
    Luminophore,
    Light,
    MeshcatRenderer,
)

from pvtrace.material.utils import isotropic as isotropic_phase_function
from pvtrace.material.utils import lambertian as lambertian_phase_function
from pvtrace.material.utils import (
    Cone as ConePhaseFunction,
)
from pvtrace.material.utils import (
    HenyeyGreenstein as HenyeyGreensteinPhaseFunction,
)
from pvtrace.light.light import (
    CubeMask,
    RectangularMask,
    CircularMask,
    ConstantWavelengthMask,
    SpectrumWavelengthMask,
)
from pvtrace.data import lumogen_f_red_305, fluro_red  # these are modules


SCHEMA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "pvtrace-schema-scene-spec.json"
)


SPECTRUM_MODULES = {"lumogen-f-red-305": lumogen_f_red_305, "fluro-red": fluro_red}


def load_schema():
    print(SCHEMA)
    with open(SCHEMA, "r") as fp:
        schema = json.load(fp)
        jsonschema.Draft7Validator.check_schema(schema)
        return schema


def load_spec(filename):
    """Load user's scene specification file."""
    with open(filename, "r") as fp:
        spec = yaml.load(fp, Loader=yaml.Loader)
        return spec


def parse(filename: str) -> Scene:
    schema = load_schema()
    spec = load_spec(filename)
    jsonschema.validate(spec, schema=schema)
    schema_version = spec["version"]
    if schema_version == "1.0":
        return parse_v_1_0(spec, os.path.dirname(filename))
    else:
        raise ValueError("Version {} not supported".format(schema_version))


def parse_v_1_0(spec: dict, working_directory: str) -> Scene:
    """Work in progress YAML version 1.0 YAML file parse."""

    def parse_spectrum(spec, named_type=None):
        # A spectrum can be of two types: file or name
        if "file" in spec:
            return load_spectrum(spec["file"])
        elif "name" in spec:
            return load_named_spectrum(spec, named_type)

    def parse_material(spec, component_map) -> Material:
        """Returns pvtrace Material object and a dictionary which maps
        component keys to a material.
        """

        # Check that the declared components on the material have
        # actually been defined in the components section of the
        # file.
        component_keys = []
        if "components" in spec:
            component_keys = spec["components"]

        for k in component_keys:
            if not (k in component_map):
                raise ValueError(f"Missing {k} component")

        refractive_index = spec["refractive-index"]
        components = [component_map[k] for k in component_keys]
        material = Material(refractive_index=refractive_index, components=components)
        return material

    def parse_box(spec, component_map):
        size = spec["size"]
        material = parse_material(spec["material"], component_map)
        return Box(size=size, material=material)

    def parse_cylinder(spec, component_map):
        length = spec["length"]
        radius = spec["radius"]
        material = parse_material(spec["material"], component_map)
        return Cylinder(length=length, radius=radius, material=material)

    def parse_sphere(spec, component_map):
        radius = spec["radius"]
        material = parse_material(spec["material"], component_map)
        return Sphere(radius=radius, material=material)

    def parse_mesh(spec, component_map):
        if os.path.isabs(spec["file"]):
            filename = spec["file"]
        else:
            filename = os.path.join(working_directory, spec["file"])

        mesh = trimesh.exchange.load.load(filename)
        material = parse_material(spec["material"], component_map)
        return Mesh(trimesh=mesh, material=material)

    def parse_position_mask(spec):
        if "rect" in spec:
            return RectangularMask(*spec["rect"])

        if "cube" in spec:
            return CubeMask(*spec["cube"])

        if "circle" in spec:
            return CircularMask(spec["circle"])

        raise ValueError("Missing attribute")

    def parse_cone_phase_function(spec) -> Callable:
        half_angle = float(spec["half-angle"])  # degrees
        rads = float(np.radians(half_angle))
        func = ConePhaseFunction(rads)
        return func

    def parse_henyey_greenstein_phase_function(spec) -> Callable:
        g = float(spec["g"])
        return HenyeyGreensteinPhaseFunction(g)

    def parse_direction_mask(spec) -> Callable:
        if "isotropic" in spec:
            return isotropic_phase_function

        if "lambertian" in spec:
            return lambertian_phase_function

        if "cone" in spec:
            return parse_cone_phase_function(spec["cone"])

        if "henyey-greenstein" in spec:
            return parse_henyey_greenstein_phase_function(spec["henyey-greenstein"])

        raise ValueError("Missing attribute")

    def parse_wavelength_mask(spec) -> Callable:
        if "nanometers" in spec:
            nm = float(spec["nanometers"])
            return ConstantWavelengthMask(nm)

        if "spectrum" in spec:
            spectrum = parse_spectrum(spec["spectrum"], named_type="absorption")
            dist = Distribution(spectrum[:, 0], spectrum[:, 1])
            return SpectrumWavelengthMask(dist)

        raise ValueError("Missing attribute")

    def parse_light(spec, name: str):

        # Prepare default wavelength. This can be override by mask section.
        wavelength_nm = wavelength = spec.get("wavelength", None)
        if wavelength_nm:
            wavelength = ConstantWavelengthMask(wavelength_nm)

        position = None
        direction = None

        mask = spec.get("mask", None)
        if mask:
            if mask.get("wavelength", None):
                wavelength = parse_wavelength_mask(mask["wavelength"])

            if mask.get("position", None):
                position = parse_position_mask(mask["position"])

            if mask.get("direction", None):
                direction = parse_direction_mask(mask["direction"])

        return Light(
            position=position, direction=direction, wavelength=wavelength, name=name
        )

    def load_named_spectrum(spec, named_type) -> Optional[numpy.ndarray]:
        x = np.arange(
            spec["range"]["min"],
            spec["range"]["max"] + spec["range"]["spacing"],
            spec["range"]["spacing"],
        )
        module = SPECTRUM_MODULES[spec["name"]]
        if named_type == "absorption":
            return np.column_stack((x, module.absorption(x)))
        elif named_type == "emission":
            return np.column_stack((x, module.emission(x)))

        raise ValueError("Requires named type")

    def load_spectrum(filename: str) -> Optional[numpy.ndarray]:
        spectrum: Optional[numpy.ndarray] = None

        # Get absolute path to the spectrum CSV
        if not os.path.isabs(filename):
            filename = os.path.abspath(os.path.join(working_directory, filename))
            print(f"Reading {filename}")

        df = pandas.read_csv(
            filename,
            usecols=[0, 1, 2],
            index_col=0,
        )
        # like numpy.column_stack((x, y))
        spectrum = df.iloc[:, 0:2].values
        return spectrum

    def parse_absorber(spec, name):

        coefficient = None
        if "coefficient" in spec:
            coefficient = spec["coefficient"]

        hist = False
        if "hist" in spec:
            hist = spec["hist"]

        spectrum = None
        if "spectrum" in spec:
            spectrum = parse_spectrum(spec["spectrum"], named_type="absorption")

        if coefficient and (spectrum is not None):
            spectrum[:, 1] = spectrum[:, 1] / numpy.max(spectrum[:, 1]) * coefficient
            return Absorber(spectrum, name=name, hist=hist)
        elif spectrum:
            return Absorber(spectrum, name=name, hist=hist)
        elif coefficient:
            return Absorber(coefficient, name=name)

        raise ValueError("Unexpected absorber format.")

    def parse_phase_function(spec):
        return parse_direction_mask(spec)

    def parse_scatterer(spec, name):

        coefficient = None
        if "coefficient" in spec:
            coefficient = spec["coefficient"]

        hist = False
        if "hist" in spec:
            hist = spec["hist"]

        phase_function = None
        if "phase-function" in spec:
            phase_function = parse_phase_function(spec["phase-function"])

        quantum_yield = 1.0
        if "quantum-yield" in spec:
            quantum_yield = spec["quantum-yield"]

        spectrum = parse_spectrum(spec["spectrum"], named_type="absorption")

        if coefficient and (spectrum is not None):
            spectrum[:, 1] = spectrum[:, 1] / numpy.max(spectrum[:, 1]) * coefficient
            return Scatterer(
                spectrum,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )
        elif spectrum:
            return Scatterer(
                spectrum,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )
        elif coefficient:
            return Scatterer(
                coefficient,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )

        raise ValueError("Unexpected scatterer format.")

    def parse_luminophore(spec, name):

        coefficient = None
        if "coefficient" in spec["absorption"]:
            coefficient = spec["absorption"]["coefficient"]

        hist = False
        if "hist" in spec:
            hist = spec["hist"]

        phase_function = isotropic_phase_function
        quantum_yield = 1.0
        if "emission" in spec:
            if "phase-function" in spec["emission"]:
                phase_function = parse_phase_function(
                    spec["emission"]["phase-function"]
                )

            if "quantum-yield" in spec["emission"]:
                quantum_yield = spec["emission"]["quantum-yield"]

        absorption_spectrum = parse_spectrum(
            spec["absorption"]["spectrum"], named_type="absorption"
        )

        emission_spectrum = parse_spectrum(
            spec["emission"]["spectrum"], named_type="emission"
        )

        if emission_spectrum is None:
            raise ValueError("Luminophore must have an emission spectrum")

        if coefficient and (absorption_spectrum is not None):
            absorption_spectrum[:, 1] = (
                absorption_spectrum[:, 1]
                / numpy.max(absorption_spectrum[:, 1])
                * coefficient
            )
            return Luminophore(
                absorption_spectrum,
                emission=emission_spectrum,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )
        elif absorption_spectrum:
            return Luminophore(
                absorption_spectrum,
                emission=emission_spectrum,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )
        elif coefficient:
            return Luminophore(
                coefficient,
                emission=emission_spectrum,
                quantum_yield=quantum_yield,
                phase_function=phase_function,
                name=name,
                hist=hist,
            )

        raise ValueError("Unexpected luminophore format.")

    def parse_component(spec, name):
        print(spec)
        if "absorber" in spec:
            return parse_absorber(spec["absorber"], name)
        elif "scatterer" in spec:
            return parse_scatterer(spec["scatterer"], name)
        elif "luminophore" in spec:
            return parse_luminophore(spec["luminophore"], name)
        raise ValueError("Unknown component type")

    def parse_node(spec, name, component_map=None):

        geometry_types = ("box", "cylinder", "sphere", "mesh")
        geometry_mapper = {
            "box": parse_box,
            "sphere": parse_sphere,
            "cylinder": parse_cylinder,
            "mesh": parse_mesh,
        }
        for geometry_type in geometry_types:
            if geometry_type in spec:
                geometry = geometry_mapper[geometry_type](
                    spec[geometry_type], component_map=component_map
                )
                return Node(geometry=geometry, name=name)

        if "light" in spec:
            light = parse_light(spec["light"], name=name)
            return Node(light=light, name=name)

        raise ValueError()

    component_map = {}
    component_specs = spec.get("components", None)
    if "components" in spec:
        for k, v in component_specs.items():
            print(f"component: {k}")
            component_map[k] = parse_component(component_specs[k], k)

    coordinate_systems = dict()
    node_specs = spec["nodes"]
    nodes = {}
    for k, v in node_specs.items():

        # YAML to node
        print(f"node: {k}")
        nodes[k] = parse_node(v, k, component_map=component_map)

        # Capture additional information which can apply later
        # once all nodes are instantiated.
        coordinate_systems[k] = {
            "parent": v.get("parent", None),
            "direction": v.get("direction", None),
            "location": v.get("location", None),
        }

    # Assign parent nodes and apply node transformations
    for k in nodes:
        node = nodes[k]
        coordsys = coordinate_systems[k]
        if node.name == "world":
            node.parent = None
        elif coordsys.get("parent", None) is None:
            node.parent = nodes["world"]
        else:
            node.parent = nodes[coordsys["parent"]]

        location = coordsys.get("location", None)
        if location:
            node.location = location

        direction = coordsys.get("direction", None)
        if direction:
            print(f"Using direction {direction} for node {node}")
            node.look_at(direction)

    return Scene(nodes["world"])


if __name__ == "__main__":

    import time
    import sys
    import IPython

    def load_test_scene():
        scene_spec = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "pvtrace-scene-spec.yml"
        )
        return parse(scene_spec)

    def load_hello_world_scene():
        scene_spec = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "hello_world.yml"
        )
        return parse(scene_spec)

    renderer = MeshcatRenderer(
        zmq_url="tcp://127.0.0.1:6000", open_browser=True, wireframe=True
    )
    renderer.render(load_hello_world_scene())
    IPython.embed()
