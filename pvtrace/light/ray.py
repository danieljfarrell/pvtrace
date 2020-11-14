from __future__ import annotations
from pvtrace.scene.node import Node
from dataclasses import dataclass, replace
from typing import Optional
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Don't like forcing units! This makes the distance units
# in pvtrace centimetres.
speed_of_light_cm_per_s = 299792458.0 * 100.0


@dataclass(frozen=True)
class Ray:
    """A ray of light. Has the physical attributes of position, direction and
    wavelength.

    Attributes
    ----------
    position : tuple of float
        The (x, y, z) position.
    direction : tuple of floats
        Direction unit vector (n_i, n_j, n_k).
    wavelength : float
        The wavelength in nanometers.
    travelled : float
        Total propagation distance. This gets updated when calling `propagate`.
    duration: float
        Total time the ray has been propagating. Unlike travelled this includes the
        radiative lifetime of emissive states. This gets updated when calling
        `propagate`.
    source: float
        Identifier of the light source of luminophore that emitted the ray.
    """

    position: tuple
    direction: tuple
    wavelength: Optional[float]
    travelled: float = 0.0
    duration: float = 0.0
    source: Optional[str] = None

    def __repr__(self):
        position = "(" + ", ".join(["{:.2f}".format(x) for x in self.position]) + ")"
        direction = "(" + ", ".join(["{:.2f}".format(x) for x in self.direction]) + ")"
        wavelength = "{:.2f}".format(self.wavelength)
        args = (position, direction, wavelength)
        return "Ray(pos={}, dir={}, nm={})".format(*args)

    def propagate(self, distance: float, refractive_index: float) -> Ray:
        """Returns a new ray which has been moved the specified distance along
        its direction.

        Parameters
        ----------
        distance : float
            The distance to move the ray. Can be negative in which case the new
            ray will be moved backwards.
        refractive_index: float
            The refractive index of material in which the ray is propagating. This
            is used to calculate the time to travel the distance.

        """
        new_position = np.array(self.position) + np.array(self.direction) * distance
        new_position = tuple(new_position.tolist())
        new_ray = replace(
            self,
            position=new_position,
            travelled=self.travelled + distance,
            duration=self.duration
            + 1 / (speed_of_light_cm_per_s / refractive_index / distance),
        )
        return new_ray

    def representation(self, from_node: Node, to_node: Node) -> Ray:
        """Representation of the ray in another coordinate system.

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
