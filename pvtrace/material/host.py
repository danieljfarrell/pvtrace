from pvtrace.material.material import Material, Decision
from pvtrace.material.lumophore import Lumophore
from pvtrace.material.properties import Refractive, Blend
from pvtrace.material.mechanisms import (
    FresnelRefraction, FresnelReflection, TravelPath, Absorption, Emission, CrossInterface
)
from pvtrace.geometry.utils import flip, angle_between
from typing import Tuple
from dataclasses import replace
import numpy as np
import logging
logger = logging.getLogger(__name__)

# fixme: problem here is that a host is, strickly speaking, not absorpive nor
# emissive. It cannot implement the required methods as if because it needs to 
# know which of it's hosted materials is the interaction material. This is evident
# in the __init__ method of Host which does a lot of bending over backwards to use
# the data and force the same API. 
#
# A possible solution is to have a new mixin property Blend which is like an effective 
# medium. It is initialised with a list of lumophores. The blend can implemented 
# `get_interaction_material` and returns the lumophore which was hit. _That_ Lumophore 
# is absorptive and emissive.
#
# Possible problems here is that 
#     isinstance(host, Emissive) 
#     isinstance(host, Absorptive) 
# will return False because the host is just a container! So we need to make sure that
# this is not relied on. The important thing from the ray tracer perspective is that 
# they implement `trace_surface` and `trace_path`.


class Host(Refractive, Blend, Material):
    """ A material with a refractive index that can host a single or multiple
        Lumophores.
    """

    def __init__(self, refractive_index: np.ndarray, lumophores: [Lumophore]):
        super(Host, self).__init__(
            refractive_index=refractive_index,
            lumophores=lumophores
        )
        self._transit_mechanism = FresnelRefraction()
        self._return_mechanism = FresnelReflection()
        self._path_mechanism = Absorption()
        self._emit_mechanism = Emission()

    def select_lumophore(self, nanometers: float) -> Lumophore:
        """ Selects, at random, one of the lumophores from the list.
        
            Parameters
            ----------
            nanometers : float
                The wavelength of the interacting photon in nanometers.

            Returns
            -------
            Lumophore
                The lumophore which absorbed the photon.

            Notes
            -----
            The selection is weighted by the relative absorption strength of all
            materials at the given wavelength.
        """
        absorptions = [l.absorption_coefficient(nanometers) for l in self.lumophores]
        count = len(self.lumophores)
        bins = list(range(0, count + 1))
        cdf = np.cumsum(absorptions)
        pdf = cdf / max(cdf)
        pdf = np.hstack([0, pdf[:]])
        pdfinv_lookup = np.interp(np.random.uniform(), pdf, bins)
        absorber_index = int(np.floor(pdfinv_lookup))
        lumophore = self.lumophores[absorber_index]
        return lumophore

    def trace_surface(
        self,
        local_ray: "Ray",
        container_geometry: "Geometry",
        to_geometry: "Geometry",
        surface_geometry: "Geometry",
    ) -> Tuple[Decision, dict]:
        """ 
        """
        # Ray both materials need a refractive index to compute Frensel reflection;
        # if they are not the both refractive then just let ray cross the interface.
        try:
            normal = surface_geometry.normal(local_ray.position)
        except Exception:
            import pdb; pdb.set_trace() 
        if not all([isinstance(x, Refractive) for x in (container_geometry.material, to_geometry.material)]):
            new_ray = CrossInterface().transform(local_ray, {"normal": normal})
            yield new_ray, Decision.TRANSIT
            return

        # Get reflectivity for the ray
        n1 = container_geometry.material.refractive_index(local_ray.wavelength)
        n2 = to_geometry.material.refractive_index(local_ray.wavelength)
        # Be flexible with how the normal is defined
        if np.dot(normal, local_ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(local_ray.direction))
        if angle < 0.0 or angle > 0.5 * np.pi:
            raise TraceError("The incident angle must be between 0 and pi/2.")
        incident = local_ray.direction
        reflectivity = self._return_mechanism.reflectivity(angle, n1, n2)
        #print("Reflectivity: {}, n1: {}, n2: {}, angle: {}".format(reflectivity, n1, n2, angle))
        gamma = np.random.uniform()
        info = {"normal": normal, "n1": n1, "n2": n2}
        # Pick between reflection (return) and transmission (transit)
        if gamma < reflectivity:
            new_ray = self._return_mechanism.transform(local_ray, info)
            decision = Decision.RETURN
            yield new_ray, decision
        else:
            new_ray = self._transit_mechanism.transform(local_ray, info)
            decision = Decision.TRANSIT
            yield new_ray, decision

    def trace_path(
            self, 
            local_ray: "Ray",
            container_geometry: "Geometry",
            distance: float
    ) -> Tuple[Decision, dict]:
                
        # Which of the host's materials captured the ray
        material = self.select_lumophore(local_ray.wavelength)
        # Sample the exponential distribution and get a distance at which the
        # ray is absorbed.
        sampled_distance = self._path_mechanism.path_length(
            local_ray.wavelength, material
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
            qy = material.quantum_yield
            # If the random number is less than the quantum yield then emission occurs.
            if np.random.uniform() < qy:
                # If ray is re-emitted generate two events: ABSORB and EMIT
                yield new_ray, Decision.ABSORB
                # Emission occurred
                new_ray = self._emit_mechanism.transform(new_ray, {"material": material})
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
    def from_dataframe(cls, df):
        """ Returns a Host instance initialised with data from the dataframe.
        
            Parameters
            ----------
                df : pandas.DataFrame
            The dataframe must start with the following columns (an index column is 
            fine and will be ignored),
                - *wavelength <anything>*, the wavelength in nanometers
                - *refractive index <anything>*, the real part of the refractive index
            Then the subsequent columns must be absorption coefficient, emission
            spectrum, and quantum yield pairs for the individual lumophores that are
            added to the host,
                - *absorption coefficient <anything>*, the absorption coefficient of the
                lumophore in units of 1/cm
                - *emission spectrum <anything>*, the emission spectrum of lumophore in
                arbitrary units (just the shape is important).
                - *quantum yield <anything>*, the quantum yield of the lumophore. Note
                that the wavelength dependence of the quantum yield is *not* used. The
                first value in the column is used as the quantum yield.
            To validate the dataframe only the start of the column names are checked
            so anything after the required part is ignored and can be what you like
            so that you can organise your data.
        """
        columns = df.columns.tolist()
        if tuple(columns[0:2]) != ("wavelength", "refractive index"):
            raise AppError(
                "Data frame is wrong format. The first two column names "
                "be 'wavelength' and 'refractive index'."
            )
        wavelength = df["wavelength"].values
        ior = df["refractive index"].values

        col_err_msg = (
            "Column {} in data frame has incorrect name. Got {} and "
            "expected it to start with {}."
        )
        lumo_cols = columns[2:]
        for idx, name in enumerate(lumo_cols):
            name = name.lower()
            col_idx = idx + 2
            if idx % 3 == 0:
                expected = "absorption coefficient"
                if not name.startswith(expected):
                    raise AppError(col_err_msg.format(col_idx, name, expected))
            elif idx % 3 == 1:
                expected = "emission spectrum"
                if not name.startswith(expected):
                    raise AppError(col_err_msg.format(col_idx, name, expected))
            elif idx % 3 == 2:
                expected = "quantum yield"
                if not name.startswith(expected):
                    raise AppError(col_err_msg.format(col_idx, name, expected))

        if len(lumo_cols) % 3 != 0:
            raise AppError(
                "Data column(s) missing. Columns after the first two should "
                "be groups like (absorption coefficient, emission_spectrum "
                ", quantum_yield)."
            )
        refractive_index = np.column_stack((wavelength, ior))
        from itertools import zip_longest

        def grouper(iterable):
            args = [iter(iterable)] * 3
            return zip_longest(*args)

        lumophores = []
        for (alpha_name, emission_name, qy_name) in grouper(lumo_cols):
            absorption_coefficient = np.column_stack(
                (wavelength, df[alpha_name].values)
            )
            emission_spectrum = np.column_stack((wavelength, df[emission_name].values))
            quantum_yield = df[qy_name].values[0]
            lumo = Lumophore(absorption_coefficient, emission_spectrum, quantum_yield)
            logger.debug(
                "Making lumophore with max absorption coefficient {}".format(
                    np.max(absorption_coefficient[:, 1])
                )
            )
            lumophores.append(lumo)

        host = cls(refractive_index, lumophores)
        return host
