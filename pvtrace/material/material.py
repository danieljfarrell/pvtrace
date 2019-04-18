from __future__ import annotations
import sys
import numpy as np
from pvtrace.common.errors import AppError
from pvtrace.material.properties import Refractive, Absorptive, Emissive
import logging
logger = logging.getLogger(__name__)


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
    


class Dielectric(Refractive, Material):
    """ A material with a refractive index.
    
        Notes
        -----
        The material is unphysical in the sense that it does not absorb or emit light. 
        But it is useful in development and testing to have material which just 
        interacts with ray without in a purely refractive way.

    """
    def __init__(self, refractive_index):
        super(Dielectric, self).__init__(refractive_index)

    @classmethod
    def make_constant(cls, x_range: Tuple[float, float], refractive_index: float):
        """ Returns a dielectric material with spectrally constant refractive index.

        """
        refractive_index=np.column_stack(
            (x_range, [refractive_index, refractive_index]))
        return cls(refractive_index)
    
    @classmethod
    def air(cls, x_range: Tuple[float, float] = (300.0, 4000.0)):
        """ Returns a dielectric material with constant refractive index of 1.0 in
            default range.

        """
        return cls.make_constant(x_range=x_range, refractive_index=1.0)

    @classmethod
    def glass(cls, x_range: Tuple[float, float] = (300.0, 4000.0)):
        """ Returns a dielectric material with constant refractive index of 1.5 in
            default range.

        """
        return cls.make_constant(x_range=x_range, refractive_index=1.5)


class LossyDielectric(Refractive, Absorptive, Material):
    """ A material with a refractive index that also attenuates light.
    
        Notes
        -----
        This can be used to model a most material such as plastic for luminescent
        concentrators or difference classes when ray tracing lenses.

    """
    def __init__(self, refractive_index: np.ndarray, absorption_coefficient: np.ndarray):
        super(LossyDielectric, self).__init__(
            refractive_index,
            absorption_coefficient
        )
    

    @classmethod
    def make_constant(cls, x_range: Tuple[float, float], refractive_index: float, absorption_coefficient: float):
        """ Returns a dielectric material with spectrally constant refractive index.

        """
        refractive_index=np.column_stack(
            (x_range, [refractive_index, refractive_index])
        )
        absorption_coefficient=np.column_stack(
            (x_range, [absorption_coefficient, absorption_coefficient])
        )
        return cls(refractive_index, absorption_coefficient)

    def get_interaction_material(self, wavelength: float) -> Material:
        """ This method is needed to distinguish between multiple lumophores objects
            when they are used with the Host material type.
        """
        return self


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
        self, absorption_coefficient: np.ndarray, emission_spectrum: np.ndarray, quantum_yield: float
    ):
        super(Lumophore, self).__init__(
            absorption_coefficient=absorption_coefficient,
            emission_spectrum=emission_spectrum,
            quantum_yield=quantum_yield
        )

    def get_interaction_material(self, wavelength: float) -> Material:
        """ This method is needed to distinguish between multiple lumophores objects
            when they are used with the Host material type.
        """
        return self

    @classmethod
    def make_constant(cls, x_range: Tuple[float, float], wavelength1: float, wavelength2: float, absorption_coefficient: float, quantum_yield: float):
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


class Host(Refractive, Absorptive, Emissive, Material):
    """ A material with a refractive index that can host a single or multiple
        Lumophores.
    """

    def __init__(
        self, refractive_index: np.ndarray, lumophores: [Lumophore]
    ):
        # We need an absorption_coefficient, emission_spectrum and quantum_yield to 
        # be able to intialise the super class. We will use this information in 
        # a way that makes a bit more sense that simply shown here.
        self.lumophores = lumophores
        wavelength = refractive_index[:, 0]
        absorption_coefficient = np.sum(
            np.column_stack(
                [l.absorption_coefficient(wavelength) for l in lumophores]
                ),
            axis=1
        )
        absorption_coefficient = np.column_stack((wavelength, absorption_coefficient))

        emission_spectrum = np.sum(
            np.column_stack(
                [l.emission_spectrum(wavelength) for l in lumophores]
                ),
            axis=1
        )
        emission_spectrum = np.column_stack((wavelength, emission_spectrum))
        
        quantum_yield = float(np.mean([l.quantum_yield for l in lumophores]))

        super(Host, self).__init__(
            refractive_index=refractive_index,
            absorption_coefficient=absorption_coefficient,
            emission_spectrum=emission_spectrum,
            quantum_yield=quantum_yield
        )
    
    def get_interaction_material(self, nanometers: float) -> Material:
        """ Returns which lumophore absorbed the ray.
        """
        absorptions = [l.absorption_coefficient(nanometers) for l in self.lumophores]
        count = len(self.lumophores)
        bins = list(range(0, count+1))
        cdf  = np.cumsum(absorptions)
        pdf  = cdf/max(cdf)
        pdf  = np.hstack([0, pdf[:]])
        pdfinv_lookup = np.interp(np.random.uniform(), pdf, bins)
        absorber_index = int(np.floor(pdfinv_lookup))
        lumophore = self.lumophores[absorber_index]
        return lumophore
    
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
            raise AppError("Data frame is wrong format. The first two column names "
                           "be 'wavelength' and 'refractive index'.")
        wavelength = df['wavelength'].values
        ior = df['refractive index'].values

        col_err_msg = ("Column {} in data frame has incorrect name. Got {} and "
                       "expected it to start with {}.")
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
            raise AppError("Data column(s) missing. Columns after the first two should "
                           "be groups like (absorption coefficient, emission_spectrum "
                           ", quantum_yield).")
        refractive_index = np.column_stack((wavelength, ior))
        from itertools import zip_longest
        def grouper(iterable):
            args = [iter(iterable)] * 3
            return zip_longest(*args)
    
        lumophores = []
        for (alpha_name, emission_name, qy_name) in grouper(lumo_cols):
            absorption_coefficient = np.column_stack((wavelength, df[alpha_name].values))
            emission_spectrum = np.column_stack((wavelength, df[emission_name].values))
            quantum_yield = df[qy_name].values[0]
            lumo = Lumophore(absorption_coefficient, emission_spectrum, quantum_yield)
            logger.debug("Making lumophore with max absorption coefficient {}".format(np.max(absorption_coefficient[:, 1])))
            lumophores.append(lumo)
        
        host = cls(refractive_index, lumophores)
        return host

