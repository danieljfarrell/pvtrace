"""
This module provides a defined set of optical properties such as a refractive index
property from the `Refractive` mixin or an absorption coefficient from the `Absorption`
mixin. As already mentioned, these objects are intended to be used as mixin to make
Material objects.
"""

import traceback
import sys
import numpy as np
from pvtrace.material.distribution import Distribution
from pvtrace.common.errors import TraceError
from scipy.interpolate import interp1d
from typing import Union, Tuple
import numpy as np
import logging
logger = logging.getLogger(__name__)


def check_spectrum_like(arr):
    if not isinstance(arr, np.ndarray):
        raise ValueError("Must be an numpy.ndarray.")
    if arr.shape[1] != 2:
        raise ValueError("Must only have two columns.")


class Refractive(object):
    """A material mix-in providing a refractive index characteristic.
    """
    
    def __init__(self, refractive_index, *args, **kwargs):
        """ Parameters
            ----------
            refractive_index : nd.array
                The spectrally varying refractive index as a numpy array with shape
                (n, 2), where n can be any length. The first column must be the
                wavelength in units of nanometers and the second column must be the
                real part of the refractive index.
        
            Notes
            -----
            The real part of the refractive index must be supplied. To include
            absorption use the Absorbative mix-in.
        """
        super(Refractive, self).__init__(*args, **kwargs)
        check_spectrum_like(refractive_index)
        self._refractive_index = interp1d(
            refractive_index[:, 0], refractive_index[:, 1], bounds_error=True
        )

    def refractive_index(self, nanometers: Union[float, int, np.ndarray]) -> Union[float, np.ndarray]:
        """ Returns the refractive index at the wavelength specified in nanometers.
        """
        values = self._refractive_index(nanometers)
        if values.size == 1:
            values = values.tolist()
        return values


class Absorptive(object):
    """ A material mix-in providing an absorption coefficient characteristic.
    """
    
    # To-do: At some point we will need to specify blends of materials with
    # different absorption coefficients. To do this we should supply a numpy array
    # with a common x column and multiple y columns.
    def __init__(self, absorption_coefficient, *args, **kwargs):
        """ Parameters
            ----------
            absorption_coefficient : nd.array
                The spectrally varying refractive index as a numpy array with shape
                (n, 2), where n can be any length. The first column must be the
                wavelength in units of nanometers and the second column must be the 
                absorption coefficient in units of 1/cm.
        """
        super(Absorptive, self).__init__(*args, **kwargs)
        check_spectrum_like(absorption_coefficient)
        self._absorption_coefficient = interp1d(
            absorption_coefficient[:, 0], absorption_coefficient[:, 1], bounds_error=True
        )
    
    def absorption_coefficient(self, nanometers: Union[float, int, np.ndarray]) -> Union[float, np.ndarray]:
        """ Returns the refractive index at the wavelength specified in nanometers.
        """
        values = self._absorption_coefficient(nanometers)
        if values.size == 1:
            values = values.tolist()
        return values


class Emissive(object):
    """ A material mix-in providing an emission spectrum characteristic.
    """
    def __init__(self, emission_spectrum, quantum_yield, *args, **kwargs):
        super(Emissive, self).__init__(*args, **kwargs)
        check_spectrum_like(emission_spectrum)
        self._emission_dist = Distribution(
            x=emission_spectrum[:, 0],
            y=emission_spectrum[:, 1]
        )
        self._quantum_yield = quantum_yield

    def redshift_wavelength(self, wavelength) -> float:
        """ Returns a new wavelength sampled from the emission spectrum which is 
            guaranteed to be at a longer wavelength.
        """
        dist = self._emission_dist
        p1 = dist.lookup(wavelength)
        p2 = 1.0
        max_wavelength = dist.sample(1.0)
        logger.debug("current wavelength is {}".format(wavelength))
        logger.debug("max wavelength is {}".format(max_wavelength))
        gamma = np.random.uniform(p1, p2)
        logger.debug("p1={}, p2={}, gamma={}".format(p1, p2, gamma))
        new_wavelength = dist.sample(gamma)
        if np.isclose(new_wavelength, max_wavelength):
            import pdb; pdb.set_trace()
            raise TraceError("Monte-carlo is sampling ends of distribution")
        return new_wavelength

    def emission_direction(self) -> Tuple[float, float, float]:
        """ Return a new isotropic emission direction.
        
            Notes
            -----
            The emission direction is sampled uniformly on the surface of a sphere [1].
        
            References
            ----------
            [1] http://mathworld.wolfram.com/SpherePointPicking.html
        """
        theta = np.random.uniform(0, 2 * np.pi)
        phi = np.arccos(2 * np.random.uniform(0.0, 1.0) - 1)
        x = np.sin(phi) * np.cos(theta)
        y = np.sin(phi) * np.sin(theta)
        z = np.cos(phi)
        return (x, y, z)

    def emission_spectrum(self, nanometers: Union[float, int, np.ndarray]) -> Union[float, np.ndarray]:
        """ Returns the refractive index at the wavelength specified in nanometers.
        """
        values = self._emission_dist(nanometers)
        return values
    
    @property
    def quantum_yield(self) -> float:
        """ Returns the quantum yield.

            Notes
            -----
            The quantum yield is a constant for the whole Lumophore and does not
            take a wavelength argument like other attributes.
        """
        return self._quantum_yield

