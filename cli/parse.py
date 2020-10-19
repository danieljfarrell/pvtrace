"""
Parses the pvtrace-scene.yml file and generates Python objects.
"""
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
from typing import Tuple, List, Dict, Optional
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
)

from pvtrace.material.utils import isotropic as isotropic_phase_function
from pvtrace.material.utils import lambertian as lambertian_phase_function
from pvtrace.material.utils import cone as cone_phase_function
from pvtrace.material.utils import henyey_greenstein as henyey_greenstein_phase_function
from pvtrace.light.light import rectangular_mask, cube_mask, circular_mask


SCHEMA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "pvtrace-schema-scene-spec.json"
)


def get_builtin_absorption_spectrum(name):
    raise NotImplementedError()


def get_builtin_emission_spectrum(name):
    raise NotImplementedError()


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
        filename = spec["file"]
        mesh = trimesh.exchange.load.load(filename)
        material = parse_material(spec["material"], component_map)
        return Mesh(trimesh=mesh, material=material)

    def parse_position_mask(spec):
        if "rect" in spec:
            return rectangular_mask(*spec["rect"])

        if "cube" in spec:
            return cube_mask(*spec["cube"])

        if "circle" in spec:
            return circular_mask(spec["circle"])

        raise ValueError("Missing attribute")

    def parse_direction_mask(spec):
        if "isotropic" in spec:
            return isotropic_phase_function

        if "lambertian" in spec:
            return lambertian_phase_function

        if "cone" in spec:
            half_angle = spec["cone"]["half-angle"]  # degrees
            return cone_phase_function(np.radians(float(half_angle)))

        if "henyey-greenstein" in spec:
            g = spec["g"]
            return henyey_greenstein_phase_function(g)

        raise ValueError("Missing attribute")

    def parse_wavelength_mask(spec):
        if "nanometers" in spec:
            return float(spec["nanometers"])

        if "spectrum" in spec:
            return load_spectrum(spec["spectrum"])

        raise ValueError("Missing attribute")

    def parse_light(spec, name: str):

        # Prepare default wavelength. This can be override by mask section.
        wavelength = spec.get("wavelength", None)
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

    def load_spectrum(filename: str) -> Optional[numpy.ndarray]:
        spectrum: Optional[numpy.ndarray] = None
        # Get absolute path to the spectrum CSV
        if not os.path.isabs(filename):
            filename = os.path.abspath(os.path.join(working_directory, filename))

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

        spectrum = load_spectrum(spec["spectrum"])

        if coefficient and (spectrum is not None):
            spectrum[:, 1] = spectrum[:, 1] / numpy.max(spectrum[:, 1]) * coefficient
            return Absorber(spectrum, name=name, hist=hist)
        elif spectrum:
            return Absorber(spectrum, name=name, hist=hist)
        elif coefficient:
            return Absorber(coefficient, name=name)

        raise ValueError("Unexpected absorber format.")

    def parse_scatterer(spec, name):
        coefficient = None
        if "coefficient" in spec:
            coefficient = spec["coefficient"]

        hist = False
        if "hist" in spec:
            hist = spec["hist"]

        phase_function = None
        if "phase-function" in spec:
            phase_function = spec["phase-function"]

        quantum_yield = 1.0
        if "quantum-yield" in spec:
            quantum_yield = spec["quantum-yield"]

        spectrum = load_spectrum(spec["spectrum"])

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

    def parse_luminophore(spec, name, builtin):

        coefficient = None
        if "coefficient" in spec["absorption"]:
            coefficient = spec["absorption"]["coefficient"]

        hist = False
        if "hist" in spec:
            hist = spec["absorption"]["hist"]

        phase_function = None
        if "phase-function" in spec:
            phase_function = spec["emission"]["phase-function"]

        quantum_yield = 1.0
        if "quantum-yield" in spec:
            quantum_yield = spec["emission"]["quantum-yield"]

        if builtin:
            absorption_spectrum = get_builtin_absorption_spectrum(builtin)
        else:
            absorption_spectrum = load_spectrum(spec["absorption"]["spectrum"])

        if builtin:
            emission_spectrum = get_builtin_emission_spectrum(builtin)
        else:
            emission_spectrum = load_spectrum(spec["emission"]["spectrum"])

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

    def parse_component(spec, name, builtin):

        if "absorber" in spec:
            return parse_absorber(spec["absorber"], name)
        elif "scatterer" in spec:
            return parse_scatterer(spec["scatterer"], name)
        elif "luminophore" in spec:
            return parse_luminophore(spec["luminophore"], name, builtin)
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
            light = parse_light(spec["light"], name=f"{name}/light")
            return Node(light=light, name=name)

        raise ValueError()

    component_map = {}
    component_specs = spec.get("components", None)
    if "components" in spec:
        for k, v in component_specs.items():
            print(f"component: {k}")
            builtin = component_specs[k].get("builtin", None)
            component_map[k] = parse_component(component_specs[k], k, builtin)

    node_specs = spec["nodes"]
    nodes = {}
    for k, v in node_specs.items():
        print(f"node: {k}")
        nodes[k] = parse_node(v, k, component_map=component_map)

    return Scene(nodes["world"])


if __name__ == "__main__":
    scene_spec = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "pvtrace-scene-spec.yml"
    )
    parse(scene_spec)