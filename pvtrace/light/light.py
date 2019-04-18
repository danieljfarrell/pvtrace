from typing import Optional, Sequence, Generator, Iterator
import numpy as np
from dataclasses import replace
from pvtrace.light.ray import Ray
import functools
import logging
logger = logging.getLogger(__name__)


class Light(object):
    """ Generic light source object which calls delegate functions to help generate rays that
    sample statistical distributions.
    
    Attributes (class)
    ------------------
    
    default_wavelength: callable
        Returns a null distribution with all rays having a wavelength of 555 nanometers.
    default_position: callable
        Returns a null distribution with zero variation in position.
    default_divergence: callable
        Returns a null distribution with zero variation in divergence.
    cone_divergence: callable
        A function which defines uniformly distributed directions in a cone of 
        solid angles defined by the half-angle of the code. Requires functools.partial
        to be used with the constructor (see examples).
    lambertian_divergence: callable
        A function which defined uniformly distributed directions in a hemisphere.
        This can be used directly with the constructor.
    square_mask: callable
        A function which uniformly positions rays over a square in the xy-plane. 
        Requires functools.partial to be used with the constructor (see examples).
    circular_mask: callable
        A function which uniformly positions rays over a circle in the xy-plane. 
        Requires functools.partial to be used with the constructor (see examples).
    
    Examples
    --------
    
    To generate divergent ray directions contained with a cone of solid angle with
    half-angle of pi/4 the class can be constructed using::

        Light(divergence_delegate=functools.partial(Light.cone_divergence, pi/4)

    To generate a Lambertian source::
    
        Light(divergence_delegate=Light.lamertian_divergence)
    
    To generate a square spatial distribution in the xy-plane with length and width
    of one unit::
    
        Light(position_delegate=functools.partial(Light.square_mask, 1, 1)

    To generate a circular spatial distribution in the xy-plane with radius one::
    
        Light(position_delegate=functools.partial(Light.circular_mask, 1)
    
    Any combination of spatial and divergence delegates can be used to generate the
    required distribution of rays.
    """
    default_wavelength = lambda: 555.0
    default_position = lambda: (0.0, 0.0, 0.0)
    default_divergence = lambda: (0.0, 0.0)

    def cone_divergence(phi_max):
        """ http://mathworld.wolfram.com/SpherePointPicking.html
            https://math.stackexchange.com/questions/56784/generate-a-random-direction-within-a-cone
        """
        theta = np.random.uniform(0, 2 * np.pi)
        phi = np.arccos(np.random.uniform(np.cos(phi_max), 1.0))
        return theta, phi
        
    def lambertian_divergence():
        """ https://simion.com/info/lambert_cosine.html
        """
        theta = np.random.uniform(0, 2 * np.pi)
        phi = np.arccos(np.sqrt(np.random.uniform()))
        return theta, phi

    square_mask = lambda X, Y: (np.random.uniform(-X, X),
                                np.random.uniform(-Y, Y),
                                0.0)

    def circular_mask(radius: float) -> Sequence[float]:
        rads = np.random.uniform(0, 2.0*np.pi)
        r = np.sqrt(np.random.uniform()) * radius
        x = r * np.cos(rads)
        y = r * np.sin(rads)
        return (x, y, 0.0)


    def __init__(self, wavelength_delegate=None, position_delegate=None, divergence_delegate=None):
        """
        Returns a light source emitting along the positive z direction of the coordinate system
        the light is attached to. Delegate functions can be used modify the wavelength, position 
        and direction of the emitted ray.

        Parameters
        ----------
        wavelength_delegate: callable
            A callable which returns the ray's wavelength. The callable should
            have the following signature `func() -> float` which returns the 
            wavelength in nanometers.
        position_delegate: callable
            A callable which returns the ray's position. The callable should
            have the following signature `func() -> (float, float, float)` which
            returns the (x, y, z) location of the ray in the attached node's 
            coordinate system.
        divergence_delegate: callable
            A callable which returns the ray's direction in spherical coordinates. 
            The callable should have the following signature `func() -> (float, float)`
            which returns the (theta, phi) angles with respect the the positive z
            axis.

        Note
        -----
        If delegate functions are not supplied the light source will emit monochromatic
        light for wavelength 555 nanometers from the origin of the node without any
        divergence of the beam.
        """
        self.wavelength_delegate = wavelength_delegate if wavelength_delegate is not None else Light.default_wavelength
        self.position_delegate = position_delegate if position_delegate is not None else Light.default_position
        self.divergence_delegate = divergence_delegate if divergence_delegate is not None else Light.default_divergence
        
    def emit(self, num_rays=None) -> Iterator[Ray]:
        """ Returns a ray with wavelength, position and divergence sampled from the
            delegates.
            
            Parameters
            ----------
            num_rays : int of None
                The maximum number of rays this light source will generate. If set to
            None then the light will generate until manually terminated.
        """
        count = 0
        while True:
            count += 1
            if num_rays is not None and count > num_rays:
                break
            nanometers = self.wavelength_delegate()
            position = self.position_delegate()
            direction = (0.0, 0.0, 1.0)
            divergence = self.divergence_delegate()
            if not np.allclose((0.0, 0.0), divergence):
                (theta, phi) = divergence
                x = np.sin(phi) * np.cos(theta)
                y = np.sin(phi) * np.sin(theta)
                z = np.cos(phi)
                direction = (x, y, z)
            ray = Ray(wavelength=nanometers,
                      position=position,
                      direction=direction,
                      is_alive=True
                )
            yield ray

