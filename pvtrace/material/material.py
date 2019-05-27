from __future__ import annotations
import sys
import numpy as np
from typing import Tuple
from dataclasses import replace
from pvtrace.common.errors import AppError
from pvtrace.geometry.utils import flip, angle_between
from pvtrace.material.properties import Refractive, Absorptive, Emissive
from pvtrace.material.mechanisms import (
    FresnelRefraction,
    FresnelReflection,
    Absorption,
    Emission,
    TravelPath,
    CrossInterface,
    KillRay,
)
import logging
logger = logging.getLogger(__name__)


from enum import Enum, unique


@unique
class Decision(Enum):
    """ Description of events that can occur when rays interact with 
        materials.
    """

    TRANSIT = 1
    """ Specifies that the ray crosses an interface boundary and 
        enters the next material.
    """

    RETURN = 2
    """ Specifies that the ray does not cross the boundary and remains
        in the original material.
    """

    ABSORB = 3
    """ Specifies that the ray has been absorbed along it's path length.
    """

    EMIT = 4
    """ Specifies that the ray has been emitted.
    """

    TRAVEL = 5
    """ Specifies that the ray did not interact with anything along it's path length.
    """

    KILL = 6
    """ Specifies that the ray has been killed because it reach the scene boundary
        of because something went wrong in the tracing algorithm.
    """


class Material(object):
    """ Base class for materials.
    
        Notes
        -----

        Material are built using mixins to have a defined set of properties. The 
        available properties live in `pvtrace.material.properties`. For example,
        to have a material with a refractive index and does not absorb or emit
        light the material should using the `Refractive` mixin::
        
            class Dielectric(Refractive, Material):
                pass

    """

    _transit_mechanism = None
    """ A mechanism which transforms the ray across an interface. For 
        example, this could be Fresnel refraction for refractive
        materials.
    """

    _return_mechanism = None
    """ A mechanism which transforms the ray by denying it access to
        cross an interace; returning it to the original material. For
        example, this could be Fresnel reflection for refractive
        materials.
    """

    _path_mechanism = None
    """ A mechanism which transforms the ray when travelling along 
        a path length in the material. This could be optical 
        absorption of volume scatter events.
    """

    _emit_mechanism = None
    """ A mechanism which transforms the ray by re-emission. This
        mechanism is conditional and called if the material can
        re-emit rays after an absorption event has occurred.
    """

    @property
    def transit_mechanism(self):
        """ The mechanism which transforms the ray across the interface.
        """
        return self._transit_mechanism

    @property
    def return_mechanism(self):
        """ The mechanism which transforms the ray by denying it to 
            cross the interface.
        """
        return self._return_mechanism

    @property
    def path_mechanism(self):
        """ The mechanism which transforms the ray along it's path.
        """
        self._path_mechanism

    @property
    def path_mechanism(self):
        """ The mechanism which transforms the ray along it's path.
        """
        self._emit_mechanism

    def trace_surface(
        self,
        local_ray: "Ray",
        from_geometry: "Geometry",
        to_geometry: "Geometry",
        surface_geometry: "Geometry",
    ) -> Tuple[Decision, dict]:
        """ Performs calculations to determine what happens to 
            the ray when it hits an interface. 
    
            Return
            ------
            and returns a decision and 
        """
        normal = surface_geometry.normal(local_ray.position)
        new_ray = CrossInterface().transform(local_ray, {"normal": normal})
        yield new_ray, Decision.TRANSIT

    def trace_path(
        self, local_ray: "Ray",
        container_geometry: "Geometry",
        distance: float
    ) -> Tuple[Decision, dict]:
        """ Dielectric material does not have any absorption; this moves ray full dist.
        """
        logger.debug("Material.trace_path args: {}".format((local_ray, container_geometry, distance)))
        new_ray = TravelPath().transform(local_ray, {"distance": distance})
        yield new_ray, Decision.TRAVEL

