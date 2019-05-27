from pvtrace.geometry.box import Box
from pvtrace.geometry.sphere import Sphere
from pvtrace.geometry.utils import EPS_ZERO
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.scene.scene import Scene
from pvtrace.scene.node import Node
from pvtrace.light.light import Light
from pvtrace.light.ray import Ray
from pvtrace.algorithm.photon_tracer import follow
from pvtrace.material.lumophore import Lumophore
from pvtrace.material.dielectric import Dielectric, LossyDielectric
from pvtrace.material.material import Decision
import numpy as np
import functools
import sys
import time


def make_embedded_scene(n1=1.5):
    world = Node(
        name="world (air)",
        geometry=Sphere(
            radius=10.0,
            material=Dielectric.air()
        )
    )
    box = Node(
        name="box (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Dielectric.make_constant(
                x_range=(300.0, 4000.0), refractive_index=n1
            )
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
            material=Dielectric.air()
        )
    )
    box = Node(
        name="box (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=LossyDielectric.make_constant(
                x_range=(300.0, 4000.0),
                refractive_index=n1,
                absorption_coefficient=10.0
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
            material=Dielectric.air()
        )
    )
    box = Node(
        name="box (lumophore)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Lumophore.make_lumogen_f_red(
                x=np.linspace(300.0, 4000.0),
                absorption_coefficient=10.0,
                quantum_yield=1.0
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
            material=Dielectric.air()
        )
    )
    box1 = Node(
        name="box one (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Dielectric.make_constant(
                x_range=(300.0, 4000.0), refractive_index=n1
            )
        ),
        parent=world
    )
    box2 = Node(
        name="box two (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Dielectric.make_constant(
                x_range=(300.0, 4000.0), refractive_index=n2
            )
        ),
        parent=world
    )
    box2.translate((0.0, 0.0, 1.0))
    box3 = Node(
        name="box three (glass)",
        geometry=Box(
            (1.0, 1.0, 1.0),
            material=Dielectric.make_constant(
                x_range=(300.0, 4000.0), refractive_index=n3
            )
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
    path = follow(ray, scene)
    path, decisions = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Hit box
        (0.00, 0.00, -0.50), # Refraction into box
        (0.00, 0.00,  0.50), # Hit box
        (0.00, 0.00,  0.50), # Refraction out of box
        (0.00, 0.00, 10.0),  # Hit world node
        (0.00, 0.00, 10.0),  # Kill ray
    ]
    expected_decisions = [
        Decision.EMIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.KILL
    ]
    for expected_point, point, expected_decision, decision in zip(expected_positions, positions, expected_decisions, decisions):
        assert expected_decision == decision
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
    path = follow(ray, scene)
    path, decisions = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Hit box
        (0.00, 0.00, -0.50), # Reflection
        (0.00, 0.00, -10.0),   # Hit world node
        (0.00, 0.00, -10.0)   # Ray killed
    ]
    expected_decisions = [
        Decision.EMIT,
        Decision.TRAVEL,
        Decision.RETURN,
        Decision.TRAVEL,
        Decision.KILL
    ]
    for expected_point, point, expected_decision, decision in zip(expected_positions, positions, expected_decisions, decisions):
        assert expected_decision == decision
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
    path = follow(ray, scene)
    path, decisions = zip(*path)
    positions = [x.position for x in path]
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Hit box
        (0.00, 0.00, -0.50), # Reflection
        (0.00, 0.00, -0.3744069237034118), # Absorbed
    ]
    expected_decisions = [
        Decision.EMIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.ABSORB,
    ]
    for expected_point, point, expected_decision, decision in zip(
        expected_positions, positions, expected_decisions, decisions):
        assert expected_decision == decision
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
    path = follow(ray, scene)
    path, decisions = zip(*path)
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
    path = follow(ray, scene)
    path, decisions = zip(*path)
    positions = [x.position for x in path]
    print(decisions)
    expected_positions = [
        (0.00, 0.00, -1.00), # Starting
        (0.00, 0.00, -0.50), # Hit box
        (0.00, 0.00, -0.50), # Refraction into box
        (0.00, 0.00,  0.50), # Hit box 
        (0.00, 0.00,  0.50), # Refraction
        (0.00, 0.00,  1.50), # Hit box 
        (0.00, 0.00,  1.50), # Refraction
        (0.00, 0.00,  2.50), # Hit box 
        (0.00, 0.00,  2.50), # Refraction
        (0.00, 0.00, 10.0),  # Hit world node
        (0.00, 0.00, 10.0)   # Kill
    ]
    expected_decisions = [
        Decision.EMIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.TRANSIT,
        Decision.TRAVEL,
        Decision.KILL
    ]
    for expected_point, point, expected_decision, decision in zip(
        expected_positions, positions, expected_decisions, decisions):
        assert np.allclose(expected_point, point, atol=EPS_ZERO)
        assert expected_decision == decision



def test_find_container_embedded_scene():
    from pvtrace.algorithm.photon_tracer import find_container
    scene, world, box = make_embedded_scene()
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container = find_container(ray, nodes)
    assert container == world

    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container = find_container(ray, nodes)
    assert container == box
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    status = find_container(ray, nodes)
    assert status == world


def test_find_container_touching_scene():
    from pvtrace.algorithm.photon_tracer import find_container
    scene, world, box1, box2, box3 = make_touching_scene()
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container = find_container(ray, nodes)
    assert container == world

    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container = find_container(ray, nodes)
    assert container == box1
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    status = find_container(ray, nodes)
    assert status == box2

    ray = Ray(
        position=(0.0, 0.0, 1.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    status = find_container(ray, nodes)
    assert status == box3

    ray = Ray(
        position=(0.0, 0.0, 2.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    status = find_container(ray, nodes)
    assert status == world



def test_ray_status_embedded_scene():
    from pvtrace.algorithm.photon_tracer import ray_status
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box = make_embedded_scene()
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == world,
        to_node == box,
        surface_node == box
        ]
    )
    
    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == box,
        to_node == world,
        surface_node == box
        ]
    )
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == world,
        to_node == None,
        surface_node == world
        ]
    )


def test_ray_status_touching_scene():
    from pvtrace.algorithm.photon_tracer import ray_status
    ray = Ray(
        position=(0.0, 0.0, -1.0),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    scene, world, box1, box2, box3 = make_touching_scene()
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == world,
        to_node == box1,
        surface_node == box1
        ]
    )
    
    ray = Ray(
        position=(0.0, 0.0, -0.4),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == box1,
        to_node == box2,
        surface_node == box1
        ]
    )
    
    ray = Ray(
        position=(0.0, 0.0, 0.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == box2,
        to_node == box3,
        surface_node == box2
        ]
    )

    ray = Ray(
        position=(0.0, 0.0, 1.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == box3,
        to_node == world,
        surface_node == box3
        ]
    )
    
    ray = Ray(
        position=(0.0, 0.0, 2.6),
        direction=(0.0, 0.0, 1.0),
        wavelength=555.0,
        is_alive=True
    )
    intersections = scene.intersections(ray.position, ray.direction)
    points, nodes = zip(*[(x.point, x.hit) for x in intersections])
    container, to_node, surface_node = ray_status(ray, points, nodes)
    assert all([
        container == world,
        to_node == None,
        surface_node == world
        ]
    )
