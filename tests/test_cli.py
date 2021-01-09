from pvtrace import scene
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.cli.parse import parse
from pvtrace import Scene, Node, Sphere, Material, Light, cone
from pvtrace.scene.scene import do_simulation
from meshcat.servers.zmqserver import start_zmq_server_as_subprocess
import pytest
import os
import time
import functools
import copy
import numpy as np

# ../tests/
HERE = os.path.dirname(os.path.relpath(__file__))

# ../examples
EXAMPLES = os.path.abspath(os.path.join(HERE, "..", "examples"))

FULL_EXAMPLE_YML = os.path.abspath(os.path.join(HERE, "data", "pvtrace-scene-spec.yml"))

LSC_EXAMPLE_YML = os.path.abspath(os.path.join(HERE, "data", "lsc_scene.yml"))

from tests.data.lsc_scene import scene as py_lsc_scene, green_laser as py_light_node

HELLO_WORLD_YML = os.path.abspath(os.path.join(EXAMPLES, "hello_world.yml"))


@pytest.fixture(scope="session")
def meshcat_zmq_url1():
    server_proc, zmq_url, web_url = start_zmq_server_as_subprocess()
    yield zmq_url
    server_proc.terminate()


@pytest.fixture(scope="session")
def meshcat_zmq_url2():
    server_proc, zmq_url, web_url = start_zmq_server_as_subprocess()
    yield zmq_url
    server_proc.terminate()


# def make_hello_world_scene():
#     world = Node(
#         name="world",
#         geometry=Sphere(
#             radius=10.0,
#             material=Material(refractive_index=1.0),
#         ),
#     )
#     ball_lens = Node(
#         name="ball-lens",
#         geometry=Sphere(
#             radius=1.0,
#             material=Material(refractive_index=1.5),
#         ),
#         parent=world,
#     )
#     ball_lens.location = (0, 0, 2)
#     green_laser = Node(
#         name="green-laser",
#         light=Light(direction=functools.partial(cone, np.pi / 8), name="green-laser"),
#         parent=world,
#     )
#     return Scene(world)


def test_parse_full_example_yml():
    assert isinstance(parse(FULL_EXAMPLE_YML), Scene)


def test_parse_hello_world_yml():
    assert isinstance(parse(HELLO_WORLD_YML), Scene)


def test_equality_by_tracing():
    """ Quite an important test!

        This checks that a scene yml and an equivalent python scene
        produce identical path histories for rays (given the same seed).
    """
    scene_A = parse(LSC_EXAMPLE_YML)
    scene_B = copy.deepcopy(py_lsc_scene)

    num = len(scene_A.light_nodes)

    # Check seed is respected
    result_B_run1 = do_simulation(scene_B, num, 42)
    result_B_run2 = do_simulation(scene_B, num, 42)
    assert result_B_run1 == result_B_run2

    # Make sure each light node generates a ray
    result_A = do_simulation(scene_A, num, 42)
    assert result_A[0] == result_B_run1[0]


def test_full_example_by_tracing():
    scene = parse(FULL_EXAMPLE_YML)
    # Make sure each light node generates a ray
    num = len(scene.light_nodes)
    assert len(do_simulation(scene, num, 42)) == num


def test_full_example_by_rendering(meshcat_zmq_url1):
    scene = parse(FULL_EXAMPLE_YML)
    history = do_simulation(scene, 300, 42)
    r = MeshcatRenderer(zmq_url=meshcat_zmq_url1, open_browser=True, wireframe=True)
    r.render(scene)
    [r.add_history(x) for x in history]
    time.sleep(2.0)


@pytest.mark.skip(reason="Superseeded by non-rendering version")
def test_equality_by_renderer(meshcat_zmq_url1, meshcat_zmq_url2):
    scene_A = parse(HELLO_WORLD_YML)
    scene_B = make_hello_world_scene()
    rA = MeshcatRenderer(zmq_url=meshcat_zmq_url1, open_browser=True, wireframe=True)
    rA.render(scene_A)

    rB = MeshcatRenderer(zmq_url=meshcat_zmq_url2, open_browser=True, wireframe=True)
    rB.render(scene_B)

    num = len(scene_A.light_nodes)

    resultB = do_simulation(scene_B, num, 42)
    for history in resultB:
        rB.add_history(history)

    resultA = do_simulation(scene_A, num, 42)
    print(resultA)
    for history in resultA:
        rA.add_history(history)

    time.sleep(4.0)


def test_parse_light_source_in_lsc_scene():
    yml_scene = parse(LSC_EXAMPLE_YML)
    # Get light node, name should be same as in python script
    found = [x for x in yml_scene.root.children if x.name == py_light_node.name]
    assert (
        len(found) == 1
    ), "Python scene and YML seen don't have same light source name"

    yml_light_node = found[0]
    assert py_light_node.name == yml_light_node.name
