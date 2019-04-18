import pytest
import sys
import os
import numpy as np
from anytree import RenderTree
from pvtrace.scene.node import Node
from pvtrace.geometry.sphere import Sphere


def node_tree():
    b_pos = (1.0, 0.0, 0.0)
    b_axis = (0.0, 1.0, 0.0)
    b_rads = 3.14159265 / 2
    c_pos = (1.0, 0.0, 0.0)
    a = Node(name="a", parent=None)
    b = Node(name="b", parent=a)
    b.location = b_pos
    b.rotate(b_rads, b_axis)
    c = b.add_child_node(name="c")
    c.location = c_pos
    return a, b, c

class TestNode:
    
    def test_init(self):
        assert type(Node()) == Node
    
    def test_name(self):
        assert Node(name="a").name == 'a'
    
    def test_parent(self):
        a = Node()
        b = Node(parent=a)
        assert a.parent == None
        assert b.parent == a

    def test_coodinate_system_conversions(self):
        a = Node(name='a')
        b = Node(name='b', parent=a)
        c = Node(name='c', parent=b)
        d = Node(name='d', parent=a)
        b.translate((1,1,1))
        c.translate((0,1,1))
        d.translate((-1, -1, -1))
        theta = 0.5 * np.pi
        b.rotate(theta, (0, 0, 1))
        c.rotate(theta, (1, 0, 0))
        d.rotate(theta, (0, 1, 0))
        # Points in node d to a require just travelling up the nodes.
        assert np.allclose(d.point_to_node((0, 0, 0), a), (-1, -1, -1))
        assert np.allclose(d.point_to_node((1, 1, 1), a), (0, 0, -2))
        # Directions in node d to a require just travelling up the nodes.
        assert np.allclose(d.vector_to_node((1, 0, 0), a), (0, 0, -1))
        assert np.allclose(d.vector_to_node((0, 1, 0), a), (0, 1, 0))
        assert np.allclose(d.vector_to_node((0, 0, 1), a), (1, 0, 0))
        # Points in node d to c requires going up and down nodes
        assert np.allclose(c.point_to_node((0, 0, 0), d), (-3, 2, 1))
        assert np.allclose(c.point_to_node((1, 1, 1), d), (-4, 3, 2))
        # Directions in node d to c require going up and down nodes
        assert np.allclose(c.vector_to_node((1, 0, 0), d), (0, 1, 0))
        assert np.allclose(c.vector_to_node((0, 1, 0), d), (-1, 0, 0))
        assert np.allclose(c.vector_to_node((0, 0, 1), d), (0, 0, 1))

    def test_intersections(self):
        a = Node(name="A", parent=None)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        loc = (-1.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        intersections = b.intersections(loc, vec)
        points = np.array([x.point for x in intersections])
        assert np.allclose(points, ((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))

    def test_intersection_when_on_surface(self):
        """ Make sure we return intersection points even with zero distance from ray.
        """
        a = Node(name="A", parent=None)
        a.geometry = Sphere(radius=1.0)
        loc = (-1.0, 0.0, 0.0)
        vec = (1.0, 0.0, 0.0)
        intersections = a.intersections(loc, vec)
        points = np.array([x.point for x in intersections])
        expected = np.array([(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
        assert np.allclose(points, expected)
    
    def test_intersection_with_translation(self):
        a = Node(name="A", parent=None)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        b.translate((1.0, 0.0, 0.0))
        aloc = (-2.0, 0.0, 0.0)
        avec = (1.0, 0.0, 0.0)
        bloc = b.point_to_node(aloc, b)
        bvec = b.vector_to_node(avec, b)
        intersections = b.intersections(bloc, bvec)
        points = tuple(x.point for x in intersections)
        assert np.allclose(points, ((-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
        # In local frame of b sphere is at origin
        intersections = a.intersections(aloc, avec)
        points = np.array(tuple(x.to(a).point for x in intersections))
        expected = np.array(((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)))
        # In frame of a everything is shifed 1 along x
        assert np.allclose(points, expected)
    
    def test_is_entering_true(self):
        a = Node(name="A", parent=None)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        surface_point = (-1.0, 0.0, 0.0)
        entering_direction = (1.0, 0.0, 0.0)
        assert b.geometry.is_entering(surface_point, entering_direction) == True

    def test_is_entering_false(self):
        a = Node(name="A", parent=None)
        b = Node(name="B", parent=a)
        b.geometry = Sphere(radius=1.0)
        surface_point = (-1.0, 0.0, 0.0)
        entering_direction = (-1.0, 0.0, 0.0)
        assert b.geometry.is_entering(surface_point, entering_direction) == False

if __name__ == '__main__':
    pass
