"""
Parses the pvtrace-scene.yml file and generates Python objects.
"""
import jsonschema
import yaml
import json
import os
import pvtrace
from pvtrace import Scene, Box, Sphere


SCHEMA = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "pvtrace-schema-scene-spec.json"
)


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
        return parse_v_1_0(spec)
    else:
        raise ValueError("Version {} not supported".format(schema_version))


def parse_v_1_0(spec: dict) -> Scene:
    """Work in progress YAML version 1.0 YAML file parse."""

    def parse_material(spec):
        refractive_index = spec["refractive-index"]
        component_names = []
        if "components" in spec:
            raise NotImplementedError("Cannot parse components yet")

    def parse_box(spec):
        print(spec)
        size = spec["size"]
        material = parse_material(spec["material"])
        return Box(size=size, material=material)

    def parse_cylinder(spec):
        raise NotImplementedError()

    def parse_sphere(spec):
        radius = spec["radius"]
        material = parse_material(spec["material"])
        return Sphere(radius=radius, material=material)

    def parse_mesh(spec):
        raise NotImplementedError()

    def parse_node(spec):
        geometry_types = ("box", "cylinder", "sphere", "mesh")
        geometry_mapper = {"box": parse_box, "sphere": parse_sphere}
        for geometry_type in geometry_types:
            if geometry_type in spec:
                geometry = geometry_mapper[geometry_type](spec[geometry_type])

    node_specs = spec["nodes"]
    nodes = {k: parse_node(v) for k, v in node_specs.items()}
    return Scene(nodes["world"])


if __name__ == "__main__":
    scene_spec = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "pvtrace-scene-spec.yml"
    )
    parse(scene_spec)