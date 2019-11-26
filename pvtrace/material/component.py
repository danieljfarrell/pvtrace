from typing import Union, Tuple, List
from enum import Enum
from dataclasses import replace
import numpy as np
from pvtrace.material.distribution import Distribution
from pvtrace.material.utils import isotropic
import logging
logger = logging.getLogger(__name__)


class Component(object):
    """ Base class for all things that can be added to a host material.
    """
    def __init__(self, name="Component"):
        super(Component, self).__init__()
        self.name = name

    def is_radiative(self, ray):
        return False


class Scatterer(Component):
    """Describes a scatterer center with attenuation coefficient per unit length."""
    
    def __init__(self, coefficient, x=None, quantum_yield=1.0, phase_function=None, name="Scatterer"):
        super(Scatterer, self).__init__(name=name)
        
        # Make absorption/scattering spectrum distribution
        self._coefficient = coefficient
        if coefficient is None:
            raise ValueError("Coefficient must be specified.")
        elif isinstance(coefficient, (float, np.float)):
            self._abs_dist = Distribution(x=None, y=coefficient)
        elif isinstance(coefficient, np.ndarray):
            self._abs_dist = Distribution(x=coefficient[:, 0], y=coefficient[:, 1])
        elif isinstance(coefficient, (list, tuple)):
            if x is None:
                raise ValueError("Requires `x`.")
            self._abs_dist = Distribution.from_functions(x, coefficient)
            
        self.quantum_yield = quantum_yield
        self.phase_function = phase_function if phase_function is not None else isotropic

    def coefficient(self, wavelength):
        value = self._abs_dist(wavelength)
        return value

    def is_radiative(self, ray):
        """ Monte-Carlo sampling to determine of the event is radiative.
        """
        return np.random.uniform() < self.quantum_yield
    
    def emit(self, ray: "Ray") -> "Ray":
        """ Change ray direction or wavelength based on physics of the interaction.
        """
        direction = self.phase_function()
        ray = replace(
            ray,
            direction=direction,
            source=self
        )
        return ray


class Absorber(Scatterer):
    """ Absorption only.
    """
    
    def __init__(self, coefficient, x=None, name="Absorber"):
        super(Absorber, self).__init__(
            coefficient,
            x=x,
            quantum_yield=0.0,
            phase_function=None,
            name=name
        )

    def is_radiative(self, ray):
        return False


class Luminophore(Scatterer):
    """Describes molecule, nanocrystal or material which absorbs and emits light."""
    
    def __init__(
        self,
        coefficient,
        emission=None,
        x=None,
        quantum_yield=1.0,
        phase_function=None,
        name="Luminophore"
        ):
        super(Luminophore, self).__init__(
            coefficient,
            x=x,
            quantum_yield=quantum_yield,
            phase_function=phase_function,
            name=name
        )
        
        # Make emission spectrum distribution
        self._emission = emission
        if emission is None:
            self._ems_dist = Distribution.from_functions(
                x, [lambda x: gaussian(x, 1.0, 600.0, 40.0)]
            )
        elif isinstance(emission, np.ndarray):
            self._ems_dist = Distribution(x=emission[:, 0], y=emission[:, 1])
        elif isinstance(emission, (tuple, list)):
            if x is None:
                raise ValueError("Requires `x`.")
            self._ems_dist = Distribution.from_functions(x, emission)
        else:
            raise ValueError("Lumophore `emission` arg has wrong type.")

    def emit(self, ray: "Ray") -> "Ray":
        """ Change ray direction or wavelength based on physics of the interaction.
        """
        direction = self.phase_function()
        dist = self._ems_dist
        p1 = dist.lookup(ray.wavelength)
        p2 = 1.0
        gamma = np.random.uniform(p1, p2)
        wavelength = dist.sample(gamma)
        ray = replace(
            ray,
            direction=direction,
            wavelength=wavelength,
            source=self
        )
        return ray
