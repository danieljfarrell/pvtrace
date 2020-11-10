from pvtrace import scene
from pvtrace.scene.renderer import MeshcatRenderer
from cli.parse import parse
from pvtrace import Scene, Node, Sphere, Material, Light, cone
from pvtrace.scene.scene import do_simulation
from meshcat.servers.zmqserver import start_zmq_server_as_subprocess
import pytest
import os
import time
import functools
import numpy as np

# ../tests/
HERE = os.path.dirname(os.path.relpath(__file__))

# ../examples
EXAMPLES = os.path.abspath(os.path.join(HERE, "..", "examples"))

FULL_EXAMPLE_YML = os.path.abspath(os.path.join(HERE, "data", "pvtrace-scene-spec.yml"))

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


def make_hello_world_scene():
    world = Node(
        name="world",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0),
        ),
    )
    ball_lens = Node(
        name="ball-lens",
        geometry=Sphere(
            radius=1.0,
            material=Material(refractive_index=1.5),
        ),
        parent=world,
    )
    ball_lens.location = (0, 0, 2)
    green_laser = Node(
        name="green-laser",
        light=Light(
            direction=functools.partial(cone, np.pi / 8), name="green-laser/light"
        ),
        parent=world,
    )
    return Scene(world)


def test_parse_full_example_yml():
    assert isinstance(parse(FULL_EXAMPLE_YML), Scene)


def test_parse_hello_world_yml():
    assert isinstance(parse(HELLO_WORLD_YML), Scene)


def test_equality_by_tracing():
    scene_A = parse(HELLO_WORLD_YML)
    scene_B = make_hello_world_scene()

    # Check seed is respected
    result_B_run1 = do_simulation(scene_B, 3, 42)
    result_B_run2 = do_simulation(scene_B, 3, 42)
    assert result_B_run1 == result_B_run2

    result_A = do_simulation(scene_A, 3, 42)

    assert result_A == result_B_run1


def test_full_example_by_tracing():
    scene = parse(FULL_EXAMPLE_YML)
    assert len(do_simulation(scene, 3, 42)) == 3


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

    resultB = do_simulation(scene_B, 3, 42)
    for history in resultB:
        rB.add_history(history)

    resultA = do_simulation(scene_A, 3, 42)
    print(resultA)
    for history in resultA:
        rA.add_history(history)

    time.sleep(4.0)
