from __future__ import annotations
from pvtrace.scene.node import Node
from dataclasses import dataclass, replace
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Ray:
    """ A ray of light. Has the physical attributes of position, direction, time and 
    wavelength.
    
    Attributes
    ----------
    position : tuple of float
        The (x, y, z) position.
    direction : tuple of floats
        Direction unit vector (n_i, n_j, n_k).
    wavelength : float
        The wavelength in nanometers.
    is_alive : bool
        Indicates if the ray is not dead
    travelled : float
        Total propagation distance. This gets updated when when calling `propagate`.
    source: float
        Identifier of the light source of luminophore that emitted the ray.
    time: float
        Total time since Event.GENERATE
    """

    position: tuple
    direction: tuple
    wavelength: Optional[float]
    is_alive: bool = True
    travelled: float = 0.0
    source: Optional[str] = None
    time: float = 0.0

    def __repr__(self):
        position = "(" + ", ".join(["{:.2f}".format(x) for x in self.position]) + ")"
        direction = "(" + ", ".join(["{:.2f}".format(x) for x in self.direction]) + ")"
        wavelength = "{:.2f}".format(self.wavelength)
        time = "{:.2f}".format(self.time)
        is_alive = "True" if self.is_alive else "False"
        args = (position, direction, wavelength, is_alive, time)
        return "Ray(pos={}, dir={}, nm={}, alive={}, time={})".format(*args)
    
    def add_time(self, val):
        """ Returns a new ray with clock value incremented by 'val'
        
        Parameters
        ----------
        val : float
            time to add
        """
        if not self.is_alive:
            raise ValueError("Ray is not alive.")
        new_time = self.time + val
        new_ray = replace(
            self, time=new_time
        )
        return new_ray
        
    def set_time(self, val):
        """ Returns a new ray with clock value set to 'val'
        
        Parameters
        ----------
        val : float
            time to set
        """
        if not self.is_alive:
            raise ValueError("Ray is not alive.")
        new_ray = replace(
            self, time=val
        )
        return new_ray
    
    def propagate(self, distance: float) -> Ray:
        """ Returns a new ray which has been moved the specified distance along
        its direction.
        
        Parameters
        ----------
        distance : float
            The distance to move the ray. Can be negative in which case the new
        ray will be moved backwards.
        """
        if not self.is_alive:
            raise ValueError("Ray is not alive.")
        new_position = np.array(self.position) + np.array(self.direction) * distance
        new_position = tuple(new_position.tolist())
        new_ray = replace(
            self, position=new_position, travelled=self.travelled + distance
        )
        return new_ray

    def representation(self, from_node: Node, to_node: Node) -> Ray:
        """ Representation of the ray in another coordinate system.
        
        Parameters
        ----------
        from_node : Node
            The node which represents the ray's current coordinate system
        to_node : Node
            The node in which the new ray should be represented.
        
        Notes
        -----
        Use this method to express the ray location and direction as viewed in the 
        `to_node` coordinate system.
        """
        new_position = from_node.point_to_node(self.position, to_node)
        new_direction = from_node.vector_to_node(self.direction, to_node)
        new_ray = replace(self, position=new_position, direction=new_direction)
        return new_ray
