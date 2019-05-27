from pvtrace.material.material import Material, Decision
from pvtrace.material.properties import Refractive, Absorptive, Emissive
from pvtrace.material.mechanisms import Absorption, Emission, CrossInterface
from dataclasses import replace
from typing import Tuple
import numpy as np
import pandas as pd
import logging
logger = logging.getLogger(__name__)


def lumogen_f_red_abs(x):
    """ Fit to Lumogen F Red absorption coefficient spectrum using five Gaussians.
    
        Parameters
        ----------
        x : numpy.array
            Wavelength array in nanometers. This should take values in the optical 
            range between 200 and 900.

        Returns
        -------
        numpy.array
            The spectrum normalised to peak value of 1.0.

        Notes
        -----
        This fit is "good enough" for getting sensible answers but for research purposes
        you should be using your own data as this might not be exactly the same 
        spectrum as your materials.

        Example
        -------
        To make a absorption coefficient spectrum in the range 300 to 800 nanometers
        containing 200 points::

            spectrum = lumogen_f_red(np.linspace(300, 800, 200))
    """
    spec = 0.9454846839252642*np.exp(-((578.6167306868869 - x)/22.6976093987002)**2) + \
           0.6430326869158796*np.exp(-((535.1850303736512 - x)/28.63029894331116)**2) +\
           0.1243340609168971*np.exp(-((494.5721783546976 - x)/13.98438275367119)**2) +\
           0.3651471532322375*np.exp(-((440.4679754085741 - x)/34.91923613222621)**2) +\
           0.7042787252835550*np.exp(-((336.0548556730901 - x)/34.24136755250487)**2)
    spec = spec/np.max(spec)
    return spec


def lumogen_f_red_ems(x):
    """ Fit to Lumogen F Red emission spectrum using five Gaussians.

        Parameters
        ----------
        x : numpy.array
            Wavelength array in nanometers. This should take values in the optical 
            range between 200 and 900.

        Returns
        -------
        numpy.array
            The spectrum normalised to peak value of 1.0

        Notes
        -----
        This fit is "good enough" for getting sensible answers but for research purposes
        you should be using your own data as this might not be exactly the same 
        spectrum as your materials.

        Example
        -------
        To make a emission spectrum in the range 300 to 800 nanometers containing 200 
        points::

            spectrum = lumogen_f_red(np.linspace(300, 800, 200))
    """
    spec = 1.0*np.exp(-((600.0 - x)/38.60)**2)
    return spec


class Lumophore(Absorptive, Emissive, Material):
    """ A material that absorbs and emits light.

        Notes
        -----
        This can be used to model a luminescent dye or nanocrystal for luminescent
        concentrators. This material does not have a refractive index. This is 
        because it is common to want to blend multiple Lumophore together in a host
        matrix. The host is usually a plastic and the refractive index of the material
        is dominated by this material and not the lumophores.

    """

    def __init__(
        self,
        absorption_coefficient: np.ndarray,
        emission_spectrum: np.ndarray,
        quantum_yield: float,
    ):
        super(Lumophore, self).__init__(
            absorption_coefficient=absorption_coefficient,
            emission_spectrum=emission_spectrum,
            quantum_yield=quantum_yield,
        )
        self._transit_mechanism = CrossInterface()  # Only transmits at interfaces
        self._return_mechanism = None  # Never reflects at interfaces
        self._path_mechanism = Absorption()
        self._emit_mechanism = Emission()


    def trace_path(
            self, 
            local_ray: "Ray",
            container_geometry: "Geometry",
            distance: float
    ) -> Tuple[Decision, dict]:
        
        # Sample the exponential distribution and get a distance at which the
        # ray is absorbed.
        sampled_distance = self._path_mechanism.path_length(
            local_ray.wavelength, container_geometry.material
        )
        logger.debug("Host.trace_path args: {}".format((local_ray, container_geometry, distance)))
        # If the sampled distance is less than the full distance the ray can travel
        # then the ray is absorbed.
        if sampled_distance < distance:
            # Apply the absorption transformation to the ray; this updates the rays
            # position to the absorption location.
            info = {"distance": sampled_distance}
            #print("Sampled pathlength: {}".format(info))
            new_ray = self._path_mechanism.transform(local_ray, info)
            # Test if ray is reemitted by comparing a random number to the quantum yield
            qy = self.quantum_yield
            # If the random number is less than the quantum yield then emission occurs.
            if np.random.uniform() < qy:
                # If ray is re-emitted generate two events: ABSORB and EMIT
                yield new_ray, Decision.ABSORB
                # Emission occurred
                new_ray = self._emit_mechanism.transform(new_ray, {"material": self})
                yield new_ray, Decision.EMIT
            else:
                # If the ray is not emitted generate one event: ABSORB
                # Non-radiative absorption occurred
                new_ray = replace(new_ray, is_alive=False)
                yield new_ray, Decision.ABSORB
        else:
            # If not absorbed travel the full distance
            info = {"distance": distance}
            new_ray = self._path_mechanism.transform(local_ray, info)
            yield new_ray, Decision.TRAVEL

    @classmethod
    def make_lumogen_f_red(
        cls,
        x: np.ndarray,
        absorption_coefficient: float,
        quantum_yield: float
        ):
        """ Returns a Lumophore material with spectral properties like Lumogen F Red 300.
        """
        absorption_spec = np.column_stack(
            [x, lumogen_f_red_abs(x) * absorption_coefficient]
        )
        emission_spec = np.column_stack(
            [x, lumogen_f_red_ems(x)]
        )
        return cls(absorption_spec, emission_spec, quantum_yield)

    @classmethod
    def make_linear_background(
        cls,
        x: np.array,
        absorption_coefficient: float
        ):
        """ Returns an Lumophore with quantum yield *zero* and flat panchromatic 
            absorption.
        """
        absorption_spec = np.column_stack(
            [x, np.ones(x.shape) * absorption_coefficient]
        )
        emission_spec = np.column_stack(
            [x, np.zeros(x.shape)]
        )
        return cls(absorption_spec, emission_spec, 0.0)
