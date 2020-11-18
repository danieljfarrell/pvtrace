from pvtrace import *
from pvtrace.light.event import Event
from pvtrace.geometry.utils import EPS_ZERO
from pvtrace.material.utils import gaussian
import numpy as np
import functools
import sys
import time


def make_embedded_scene(n1=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0)
        )
    )
    box = Node(
        name="box (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(refractive_index=n1)
            ),
        parent=world
    )
    scene = Scene(world)
    return scene, world, box

def make_embedded_lossy_scene(n1=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0)
        )
    )
    box = Node(
        name="box (absorber)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(
                refractive_index=n1,
                components=[
                    Absorber(coefficient=10.0)
                ]
            ),
        ),
        parent=world
    )
    scene = Scene(world)
    return scene, world, box

def make_embedded_lossy_scene_w_reactor(n1=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0)
        )
    )
    box = Node(
        name="box (reactor)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(
                refractive_index=n1,
                components=[
                    Reactor(coefficient=10.0)
                ]
            ),
        ),
        parent=world
    )
    scene = Scene(world)
    return scene, world, box

def make_embedded_lumophore_scene(n1=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0)
        )
    )
    box = Node(
        name="box (lumophore)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(
                refractive_index=n1,
                components=[
                    Luminophore(
                        x=np.linspace(300.0, 1000.0),
                        coefficient=10.0, 
                        quantum_yield=1.0
                    )
                ],
            )
        ),
        parent=world
    )
    scene = Scene(world)
    return scene, world, box


def make_touching_scene(n1=1.5, n2=1.5, n3=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Material(refractive_index=1.0)
        )
    )
    box1 = Node(
        name="box one (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(refractive_index=n1)
            ),
        parent=world
    )

    box2 = Node(
        name="box two (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(refractive_index=n2)
        ),
        parent=world
    )
    box2.translate((0.0, 0.0, 1.0))
    box3 = Node(
        name="box three (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Material(refractive_index=n3)
        ),
        parent=world
    )
    box3.translate((0.0, 0.0, 2.0))
    scene = Scene(world)
    return scene, world, box1, box2, box3


def test_follow_embedded_scene_1():
    
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_scene()
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Refraction into box
        (0.00, 0.00,  0.50), # Refraction out of box
        (0.00, 0.00, 10.0),  # Hit world node
    ]
    expected_events = [
        Event.GENERATE,
        Event.TRANSMIT,
        Event.TRANSMIT,
        Event.EXIT
    ]
    for expected_point, point, expected_event, event in zip(expected_positions, positions, expected_events, events):
        assert expected_event == event
        assert np.allclose(expected_point, point, atol=EPS_ZERO)


def test_follow_embedded_scene_2():
    
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_scene(n1=100.0)
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Reflection
        (0.00, 0.00, -10.0), # Hit world node
    ]
    expected_events = [
        Event.GENERATE,
        Event.REFLECT,
        Event.EXIT
    ]
    
    for expected_point, point, expected_event, event in zip(expected_positions, positions, expected_events, events):
        assert expected_event == event
        assert np.allclose(expected_point, point, atol=EPS_ZERO)


def test_follow_lossy_embedded_scene_1():
    
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_lossy_scene()
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Hit box
        (0.00, 0.00, -0.3744069237034118), # Absorbed
    ]
    expected_events = [
        Event.GENERATE,
        Event.TRANSMIT,
        Event.ABSORB,
    ]
    for expected_point, point, expected_event, event in zip(
        expected_positions, positions, expected_events, events):
        assert expected_event == event
        assert np.allclose(expected_point, point, atol=EPS_ZERO)


def test_follow_lossy_embedded_scene_w_reactor():
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_lossy_scene_w_reactor()
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00),  # Starting
        (0.00, 0.00, -0.50),  # Hit box
        (0.00, 0.00, -0.3744069237034118),  # Absorbed and reacted
    ]
    expected_events = [
        Event.GENERATE,
        Event.TRANSMIT,
        Event.REACT,
    ]
    for expected_point, point, expected_event, event in zip(
            expected_positions, positions, expected_events, events):
        assert expected_event == event
        assert np.allclose(expected_point, point, atol=EPS_ZERO)


def test_follow_embedded_lumophore_scene_1():
    
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_lumophore_scene()
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    # First two are before box
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Refraction into box
    ]
    assert len(expected_positions) < len(positions[:-1])
    print("Expected: {}".format(expected_positions))
    assert all([
        np.allclose(expected, actual, atol=EPS_ZERO)
        for (expected, actual) in zip(expected_positions, positions[0:2])
    ])
    
    
def test_touching_scene_intersections():
    print("test_touching_scene_intersections")
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box1, box2, box3 = make_touching_scene()
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    assert nodes == (box1, box1, box2, box2, box3, box3, world)


def test_follow_touching_scene():
    
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box1, box2, box3 = make_touching_scene()
    np.random.seed(0)
    path = photon_tracer.follow(scene, ray)
    path, events = zip(*path)
    positions = [x.position for x in path]
    print(events)
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Refraction
        (0.00, 0.00,  0.50), # Refraction
        (0.00, 0.00,  1.50), # Refraction
        (0.00, 0.00,  2.50), # Refraction
        (0.00, 0.00, 10.0),  # Hit world node
    ]
    expected_events = [
        Event.GENERATE,
        Event.TRANSMIT,
        Event.TRANSMIT,
        Event.TRANSMIT,
        Event.TRANSMIT,
        Event.EXIT
    ]
    for expected_point, point, expected_event, event in zip(
        expected_positions, positions, expected_events, events):
        assert np.allclose(expected_point, point, atol=EPS_ZERO)
        assert expected_event == event



def test_find_container_embedded_scene():
    scene, world, box = make_embedded_scene()
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    container = photon_tracer.find_container(intersections)
    assert container == world

    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    container = photon_tracer.find_container(intersections)
    assert container == box
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    status = photon_tracer.find_container(intersections)
    assert status == world


def test_find_container_touching_scene():
    scene, world, box1, box2, box3 = make_touching_scene()
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    container = photon_tracer.find_container(intersections)
    assert container == world

    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    container = photon_tracer.find_container(intersections)
    assert container == box1
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    status = photon_tracer.find_container(intersections)
    assert status == box2

    ray = Ray(
        position=(0.0, 0.0, 1.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    status = photon_tracer.find_container(intersections)
    assert status == box3

    ray = Ray(
        position=(0.0, 0.0, 2.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    status = photon_tracer.find_container(intersections)
    assert status == world

