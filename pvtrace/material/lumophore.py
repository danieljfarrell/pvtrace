from pvtrace.material.material import Material, Decision
from pvtrace.material.properties import Refractive, Absorptive, Emissive
from pvtrace.material.mechanisms import Absorption, Emission, CrossInterface
from dataclasses import replace
from typing import Tuple
import numpy as np
import pandas as pd


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
            distance : float
        ):
        
        # Sample the exponential distribution and get a distance at which the
        # ray is absorbed.
        sampled_distance = self._path_mechanism.path_length(
            local_ray.wavelength, container_geometry.material
        )
        # If the sampled distance is less than the full distance the ray can travel
        # then the ray is absorbed.
        if sampled_distance < distance:
            # Apply the absorption transformation to the ray; this updates the rays
            # position to the absorption location.
            info = {"distance": sampled_distance}
            print("Sampled pathlength: {}".format(info))
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
    def make_constant(
        cls,
        x_range: Tuple[float, float],
        wavelength1: float,
        wavelength2: float,
        absorption_coefficient: float,
        quantum_yield: float,
    ):
        """ Returns a Lumophore material with spectral properties parameterised as::

                    Abs coef./     absorption     emission
                   emissivity        band           band
              alpha / 1 |-------------------------   +
                        |                         \ + +
                        |                          +\  +
                        |                         +   \ +
                      0 |________________________+______\+___________>
                        0                       w1       w2         oo (wavelength)

            This is mostly useful for testing and should not really be considered
            a feature that is commonly used.
        """

        def make_absorprtion_coefficient(x_range, absorption_coefficient, cutoff_range):
            wavelength1, wavelength2 = cutoff_range
            alpha = absorption_coefficient
            halfway = wavelength1 + 0.5 * (wavelength2 - wavelength1)
            x = [x_range[0], wavelength1, halfway, wavelength2, x_range[1]]
            y = [alpha, alpha, 0.5 * alpha, 0, 0]
            spectrum = np.column_stack((x, y))
            return spectrum

        def make_emission_spectrum(x_range, cutoff_range):
            wavelength1, wavelength2 = cutoff_range
            halfway = wavelength1 + 0.5 * (wavelength2 - wavelength1)
            x = [x_range[0], wavelength1, halfway, wavelength2, x_range[1]]
            y = [0.0, 0.0, 1.0, 0, 0]
            spectrum = np.column_stack((x, y))
            return spectrum

        cutoff_range = (wavelength1, wavelength2)
        absorption_coefficient = make_absorprtion_coefficient(
            x_range, absorption_coefficient, cutoff_range
        )
        emission_spectrum = make_emission_spectrum(x_range, cutoff_range)
        return cls(absorption_coefficient, emission_spectrum, quantum_yield)
