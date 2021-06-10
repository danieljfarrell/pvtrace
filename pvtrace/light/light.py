from typing import Optional, Sequence, Generator, Iterator
import numpy as np
from dataclasses import replace
from pvtrace.light.ray import Ray
import functools
import logging

logger = logging.getLogger(__name__)

"""
Modules Callables
-----------------

default_wavelength: callable
    Returns a null distribution with all rays having a wavelength of 555 nanometers.

DefaultWavelength: object
    An object which when called behaves like default_wavelength

default_position: callable
    Returns a null distribution with zero variation in position.

DefaultPosition: object
    An object which when called behaves like default_position

default_direction: callable
    Returns a null distribution with zero variation in divergence.

DefaultDirection: object
    An object which when called behaves like default_direction

rectangular_mask: callable
    A function which uniformly positions rays over a square in the xy-plane. 
    Requires functools.partial to be used with the constructor (see examples).

RetangularMask: object
    An object which when called behaves like rectangular_mask

circular_mask: callable
    A function which uniformly positions rays over a circle in the xy-plane. 
    Requires functools.partial to be used with the constructor (see examples).

CircularMask: object
    An object which when called behaves like circular_mask
"""


def default_wavelength():
    return 555.0


def default_position():
    return (0.0, 0.0, 0.0)


def default_direction():
    return (0.0, 0.0, 1.0)


def rectangular_mask(X, Y):
    return (np.random.uniform(-X, X), np.random.uniform(-Y, Y), 0.0)


def circular_mask(radius: float) -> Sequence[float]:
    rads = np.random.uniform(0, 2.0 * np.pi)
    r = np.sqrt(np.random.uniform()) * radius
    x = r * np.cos(rads)
    y = r * np.sin(rads)
    return (x, y, 0.0)


def cube_mask(X, Y, Z):
    return (
        np.random.uniform(-X, X),
        np.random.uniform(-Y, Y),
        np.random.uniform(-Z, Z),
    )


class DefaultWavelength(object):
    """Helper object to generate 555nm wavelength rays."""

    def __call__(self):
        return default_wavelength()


class DefaultPosition(object):
    """Helper object to generate rays from origin of coordinate system."""

    def __call__(self):
        return default_position()


class DefaultDirection(object):
    """Helper object to generate rays travelling along +z direction"""

    def __call__(self):
        return default_direction()


class ConstantWavelengthMask(object):
    """Helper object which generates a constant wavelength"""

    def __init__(self, nanometers):
        self.nanometers = float(nanometers)

    def __call__(self):
        return self.nanometers


class SpectrumWavelengthMask(object):
    """Helper object which generates wavelengths according to spectral
    distribution.
    """

    def __init__(self, distribution):
        self.distribution = distribution

    def __call__(self):
        return self.distribution.sample(np.random.uniform(0, 1))


class RectangularMask(object):
    """Helper object which generates rays uniformally on an xy-plane."""

    def __init__(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def __call__(self):
        x = self.x
        y = self.y
        return rectangular_mask(x, y)


class CircularMask(object):
    """Helper object which generates rays uniformally inside a circle."""

    def __init__(self, radius):
        self.radius = radius

    def __call__(self):
        return circular_mask(self.radius)


class CubeMask(object):
    """Helper object which generates rays uniformly inside a cube."""

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __call__(self):
        dims = self.x, self.y, self.z
        return cube_mask(*dims)


class Light(object):
    """Generic light source object which calls delegate functions to help generate rays that
    sample statistical distributions.

    Examples
    --------

    Light of 555nm from the origin or the light's node along direction (0, 0, 1)::

        Light()

    Light with isotropic direction::

        from pvtrace.material.utils import isotropic
        Light(direction=isotropic)

    Light emitted within solid-angle of half-angle pi/8 rads::

        import functools
        from pvtrace.material.utils import cone
        Light(direction=functools.partial(cone, np.pi/8))

    To generate a Lambertian source::

        import functools
        from pvtrace.material.utils import lambertian
        Light(direction=lambertian)

    To generate a square spatial distribution in the xy-plane with length and width
    of one unit::

        import functools
        Light(position=functools.partial(rectangular_mask, 1, 1)

    To generate a circular spatial distribution in the xy-plane with radius one::

        import functools
        Light(position=functools.partial(circular_mask, 1)

    Any combination of spatial and divergence delegates can be used to generate the
    required distribution of rays.
    """

    def __init__(self, wavelength=None, position=None, direction=None, name="Light"):
        """
        Returns a light source emitting along the positive z direction of the coordinate system
        the light is attached to. Delegate functions can be used modify the wavelength, position
        and direction of the emitted ray.

        Parameters
        ----------
        wavelength: callable or None
            A callable which returns the ray's wavelength. The callable should
            have the following signature `func() -> float` which returns the
            wavelength in nanometers.
        position: callable or None
            A callable which returns the ray's position. The callable should
            have the following signature `func() -> (float, float, float)` which
            returns the (x, y, z) location of the ray in the attached node's
            coordinate system.
        direction: callable or None
            A callable which returns the ray's direction in Cartesian coordinates.
            The callable should have the following signature
            `func() -> (float, float, float)`.

        Note
        -----
        If delegate functions are not supplied the light source will emit monochromatic
        light for wavelength 555 nanometers from the origin of the node along the
        positive z-direction.
        """
        self.wavelength = wavelength if wavelength is not None else default_wavelength
        self.position = position if position is not None else default_position
        self.direction = direction if direction is not None else default_direction
        self.name = name

    def emit(self, num_rays=None) -> Iterator[Ray]:
        """Returns a ray with wavelength, position and divergence sampled from the
        delegates.

        Parameters
        ----------
        num_rays : int of None
            The maximum number of rays this light source will generate. If set to
        None then the light will generate until manually terminated.
        """
        if num_rays is None or num_rays == 0:
            return
        count = 0
        while True:
            count += 1
            if num_rays is not None and count > num_rays:
                break

            try:
                ray = Ray(
                    wavelength=self.wavelength(),
                    position=self.position(),
                    direction=self.direction(),
                    source=self.name,
                )
            except Exception:
                raise
            yield ray
