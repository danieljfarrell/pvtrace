""" Components can be added to Material objects to change the optical properties of the
volume include: absorption, scattering and luminescence (absorption and reemission).
"""
from dataclasses import replace
from typing import Union, Optional, Callable
import numpy as np
from pvtrace.material.distribution import Distribution
from pvtrace.material.utils import isotropic, gaussian
from pvtrace.light.ray import Ray
import logging

logger = logging.getLogger(__name__)

q = 1.60217662e-19  # C
kB = 1.380649e-23 / q  # eV K-1


class Component(object):
    """ Base class for all things that can be added to a host material.
    """

    def __init__(self, name: str = "Component"):
        super(Component, self).__init__()
        self.name = name

    def is_radiative(self, ray):
        return False

    def nonradiative_absorb(self, ray):
        return ray


class Scatterer(Component):
    """Describes a scatterer centre with attenuation coefficient per unit length.
    
        Examples
        --------
        Create `Scatterer` with isotropic and constant probability of scattering::

            Scattering(1.0)

        With spectrally varying scattering probability using a numpy array::

            arr = numpy.column_stack((x, y))
            Scatterer(arr)

        With spectrally varying scattering probability using `x` lists::

            Scatterer(y, x=x)
    """

    def __init__(
        self,
        coefficient: Union[float, list, tuple, np.ndarray],
        x: Union[None, list, tuple, np.ndarray] = None,
        quantum_yield: Optional[float] = 1.0,
        tau_rad: Optional[float] = None,
        tau_nr: Optional[float] = None,
        phase_function: Optional[Callable] = None,
        hist: bool = False,
        name: str = "Scatterer",
    ):
        """ 
        Parameters
        ----------
        coefficient: float, list, tuple or numpy.ndarray
            Specifies the scattering coefficient per unit length. Constant values
            can be supplied or a spectrum per nanometer per unit length. 
        x: list, tuple of numpy.ndarray (optional)
            Wavelength values in nanometers. Required when specifying a the
            `coefficient` with an list or tuple.
        quantum_yield: float (optional)
            Default value is 1.0. To include non-radiative scattering use values
            between less than 1.0.
        tau_rad: float (optional)
            The single exponential time constant for radiative recombination in seconds.
        tau_nr: float (optional)
            The single exponential time constant for non-radiative recombination in seconds.
        phase_function callable (optional)
            Determines the direction of scattering. If None is supplied scattering
            is isotropic.
        hist: Bool
            Specifies how the coefficient spectrum is sampled. If `True` the values
            are treated as a histogram. If `False` the values are linearly 
            interpolated.
        name: str
            A user-defined identifier string
        
        Notes
        -----
        By default, scattering event are radiative; they do not remove rays from the
        simulation.
        
        Non-radiative scattering is possible by setting the `quantum_yield`
        parameter to a value less than 1.

        Alternativley, set `tau_rad` and the `tau_nr` values and the quantum yield 
        will be calculated as,

            (1/rau_rad) / (1/tau_rad + 1/tau_nr) = tau_nr / (tau_nr + tau_rad)
        
        This also enabled time-resolved mode which keeps track of duration of all events.
        """
        super(Scatterer, self).__init__(name=name)

        # Make absorption/scattering spectrum distribution
        self._coefficient = coefficient
        if coefficient is None:
            raise ValueError("Coefficient must be specified.")
        elif isinstance(coefficient, float):
            self._abs_dist = Distribution(x=None, y=coefficient, hist=hist)
        elif isinstance(coefficient, np.ndarray):
            self._abs_dist = Distribution(
                x=coefficient[:, 0], y=coefficient[:, 1], hist=hist
            )
        elif isinstance(coefficient, (list, tuple)):
            if x is None:
                raise ValueError("Requires `x`.")
            self._abs_dist = Distribution.from_functions(x, coefficient, hist=hist)

        # Force specification of either `quantum_yield` or both `tau_rad` and `tau_nr`
        qy = np.nan
        if tau_rad is not None and tau_nr is not None:
            qy = tau_nr / (tau_nr + tau_rad)
        elif quantum_yield is not None:
            qy = quantum_yield

        # Final check we could calculate a sensible quantum yield
        if not np.isfinite(qy):
            raise ValueError(
                "Specify either `quantum yield` or both `tau_rad` and `tau_nr`"
            )

        self.quantum_yield = qy
        self.tau_rad = tau_rad
        self.tau_nr = tau_nr
        self.phase_function = (
            phase_function if phase_function is not None else isotropic
        )

    def coefficient(self, wavelength):
        """ Returns the scattering coefficient at `wavelength`.
        """
        value = self._abs_dist(wavelength)
        return value

    def is_radiative(self, ray):
        """ Monte-Carlo sampling to determine of the event is radiative.
        """
        return np.random.uniform() < self.quantum_yield

    def nonradiative_absorb(self, ray: Ray) -> Ray:
        """ Returns a ray which has been non-radiatively absorbed.

            If `nonradiaitive_lifetime` has been specified the ray's internal
            clock is updated with a time sampled from a single exponential
            distribution. Otherwise the input ray is returned.
        """
        if self.tau_nr:
            delay = -np.log(1 - np.random.uniform()) * self.tau_nr
            return replace(ray, duration=ray.duration + delay)
        return ray

    def emit(self, ray: Ray, **kwargs) -> Ray:
        """ Change ray direction or wavelength based on physics of the interaction.
        """
        direction = self.phase_function()
        ray = replace(ray, direction=direction, source=self.name)
        return ray


class Absorber(Scatterer):
    """ A component that attenuates light by non-radiative absorption.
    
        Examples
        --------
        Create `Absorber` with isotropic and constant scattering coefficient::

            Absorber(1.0)

        With spectrally varying scattering coefficient using a numpy array::

            arr = numpy.column_stack((x, y))
            Absorber(arr)

        With spectrally varying scattering coefficient using `x` lists::

            Absorber(y, x=x)
    """

    def __init__(self, coefficient, x=None, tau_nr=None, name="Absorber", hist=False):
        """ coefficient: float, list, tuple or numpy.ndarray
                Specifies the absorption coefficient per unit length. Constant values
                can be supplied or a spectrum per nanometer per unit length. 
                
                If using a list of tuple you should also specify the wavelengths using
                the `x` keyword.

                If using a numpy array use `column_stack` to supply a single array with 
                a wavelength and coefficient values::

            x: list, tuple of numpy.ndarray (optional)
                Wavelength values in nanometers. Required when specifying a the
                `coefficient` with an list or tuple.
            tau_nr: float (optional)
                The single exponential time constant for non-radiative recombination in seconds.
            hist: Bool
                Specifies how the coefficient spectrum is sampled. If `True` the values
                are treated as a histogram. If `False` the values are linearly 
                interpolated.
            name: str
                A user-defined identifier string
        """

        super(Absorber, self).__init__(
            coefficient,
            x=x,
            quantum_yield=0.0,
            tau_nr=tau_nr,
            tau_rad=0.0,
            phase_function=None,
            hist=hist,
            name=name,
        )

    def is_radiative(self, ray):
        """ Returns `False` (overridden superclass method).
        """
        return False


class Reactor(Absorber):
    """Describes a reaction mixture: photon absorbed cause photochemical transformation.

        Examples
        --------
        Create `Reactor` with isotropic and constant probability of scattering::

            Reactor(1.0)
    """

    def __init__(self, coefficient, x=None, name="Reactor", hist=False):
        """ coefficient: float, list, tuple or numpy.ndarray
                Specifies the absorption coefficient per unit length. Constant values
                can be supplied or a spectrum per nanometer per unit length.

                If using a list of tuple you should also specify the wavelengths using
                the `x` keyword.

                If using a numpy array use `column_stack` to supply a single array with
                a wavelength and coefficient values::

            x: list, tuple of numpy.ndarray (optional)
                Wavelength values in nanometers. Required when specifying a the
                `coefficient` with an list or tuple.
            name: str
                A user-defined identifier string
            hist: Bool
                Specifies how the coefficient spectrum is sampled. If `True` the values
                are treated as a histogram. If `False` the values are linearly
                interpolated.

        """

        super(Reactor, self).__init__(
            coefficient,
            x=x,
            hist=hist,
            name=name,
        )


class Luminophore(Scatterer):
    """ Describes molecule, nanocrystal or material which absorbs and emits light.

        Examples
        --------
        Create `Luminophore` with absorption coefficient and emission spectrum.
        Emission will be isotropic and the quantum yield is unity::
            
            absorption_spectrum = np.column_stack((x_abs, y_abs))
            emission_spectrum = np.column_stack((x_ems, y_ems))
            Luminophore(
                coefficient=absorption_spectrum,
                emission=emission_spectrum,
                quantum_yield=1.0
            )
        
        If input data are histograms rather than continuous spectrum use `hist=True`.
    
            absorption_histogram = np.column_stack((x_abs, y_abs))
            emission_histogram = np.column_stack((x_ems, y_ems))
            Luminophore(
                coefficient=absorption_histogram,
                emission=emission_histogram,
                quantum_yield=1.0,
                hist=True
            )
        
        This prevent `pvtrace` from using interpolation on the data set which will
        preserve any discontinuities in the emission or absorption data.
    """

    def __init__(
        self,
        coefficient,
        emission=None,
        x=None,
        hist=False,
        quantum_yield=1.0,
        tau_rad=None,
        tau_nr=None,
        phase_function=None,
        name="Luminophore",
    ):
        """ coefficient: float, list, tuple or numpy.ndarray
                Specifies the absorption coefficient per unit length. Constant values
                can be supplied or a spectrum per nanometer per unit length. 
                
                If using a list of tuple you should also specify the wavelengths using
                the `x` keyword.

                If using a numpy array use `column_stack` to supply a single array with 
                a wavelength and coefficient values.

            emission: float, list, tuple or numpy.ndarray (optional)
                Specifies the emission line-shape per nanometer.
        
                If `None` will use a Gaussian centred at 600nm.
        
                If using a list of tuple you should also specify the wavelengths using
                the `x` keyword.
    
                If using a numpy array use `column_stack` to supply a single array with 
                a wavelength and coefficient values.

            x: list, tuple of numpy.ndarray (optional)
                Wavelength values in nanometers. Required when specifying a the
                `coefficient` with an list or tuple.
            quantum_yield: float (optional)
                The probability of re-emitting a ray.
            tau_rad: float (optional)
                The single exponential time constant for radiative recombination in seconds.
            tau_nr: float (optional)
                The single exponential time constant for non-radiative recombination in seconds.
            phase_function callable (optional)
                Specifies the direction of emitted rays.
            hist: Bool
                Specifies how the absorption and emission spectra are sampled. If `True`
                the values are treated as a histogram. If `False` the values are 
                linearly interpolated.
            name: str
                A user-defined identifier string
        """
        super(Luminophore, self).__init__(
            coefficient,
            x=x,
            quantum_yield=quantum_yield,
            tau_rad=tau_rad,
            tau_nr=tau_nr,
            phase_function=phase_function,
            hist=hist,
            name=name,
        )

        # Make emission spectrum distribution
        self._emission = emission
        if emission is None:
            self._ems_dist = Distribution.from_functions(
                x, [lambda x: gaussian(x, 1.0, 600.0, 40.0)], hist=hist
            )
        elif isinstance(emission, np.ndarray):
            self._ems_dist = Distribution(x=emission[:, 0], y=emission[:, 1], hist=hist)
        elif isinstance(emission, (tuple, list)):
            if x is None:
                raise ValueError("Requires `x`.")
            self._ems_dist = Distribution.from_functions(x, emission, hist=hist)
        else:
            raise ValueError("Luminophore `emission` arg has wrong type.")

    def emit(self, ray: Ray, method="kT", T=300.0, **kwargs) -> Ray:
        """ Change ray direction or wavelength based on physics of the interaction.
            
            Parameters
            ----------
            ray: Ray
                The ray when it was absorbed.
            method: str
                Either `'kT'`, `'redshift'` or `'full'`.
            
                `'kT'` option allowed emitted rays to have a wavelength
                within 3kT of the absorbed value.
        
                `'redshift'` option ensures the emitted ray has a longer of equal
                wavelength.
        
                `'full'` option samples the full emission spectrum allowing the emitted
                ray to take any value.
            T: float
                The temperature to use in the `'kT'` method.
        """
        direction = self.phase_function()
        dist = self._ems_dist
        nm = ray.wavelength
        # Different ways of sampling the emission distribution.
        if method == "kT":
            # Known issue: this can blue shift outside simulation range!
            # Emission energy can be within 3kT above current value. Simple bolzmann.
            eV = 1240.0 / nm
            eV = eV + 3 / 2 * kB * T  # Assumes 3 dimensional degrees of freedom
            nm = 1240.0 / eV
            p1 = dist.lookup(nm)
        elif method == "boltzmann":
            # Convolve the emission spectrum with a bolzmann factor centered at
            # the current photon energy. This will allow the energy to go up via
            # the tail in the distribution but will favor lower energy states.
            raise NotImplementedError()
        elif method == "redshift":
            # Emission energy must always redshift
            p1 = dist.lookup(nm)
        elif method == "full":
            # Emission energy is sampled from full distribution
            p1 = 0.0
        p2 = 1.0
        gamma = np.random.uniform(p1, p2)
        wavelength = dist.sample(gamma)

        # Delay emission using the radiative lifetime
        emission_delay = 0.0
        if self.tau_rad:
            emission_delay = -np.log(1 - np.random.uniform()) * self.tau_rad

        ray = replace(
            ray,
            direction=direction,
            wavelength=wavelength,
            source=self.name,
            duration=ray.duration + emission_delay,
        )
        return ray
