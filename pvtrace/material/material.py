class Component(object):
    """ Base class for all things that can be added to a host material.
    """
    def __init__(self):
        super(Component, self).__init__()

    def is_radiative(self, ray):
        return False


class Scatterer(Component):
    """Describes a scatterer center with attenuation coefficient per unit length."""
    
    def __init__(self, coefficient, x=None, quantum_yield=1.0, phase_function=None):
        super(Scatterer, self).__init__()
        
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
        if value < 0:
            import pdb; pdb.set_trace()
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
            direction=direction
        )
        return ray


class Absorber(Scatterer):
    """ Absorption only.
    """
    
    def __init__(self, coefficient, x=None):
        super(Absorber, self).__init__(coefficient, x=x, quantum_yield=0.0, phase_function=None)

    def is_radiative(self, ray):
        return False


class Luminophore(Scatterer):
    """Describes molecule, nanocrystal or material which absorbs and emits light."""
    
    def __init__(self, coefficient, emission=None, x=None, quantum_yield=1.0, phase_function=None):
        super(Luminophore, self).__init__(
            coefficient,
            x=x,
            quantum_yield=quantum_yield,
            phase_function=phase_function
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
        theta = np.random.uniform(0, 2 * np.pi)
        phi = np.arccos(2 * np.random.uniform(0.0, 1.0) - 1)
        x = np.sin(phi) * np.cos(theta)
        y = np.sin(phi) * np.sin(theta)
        z = np.cos(phi)
        direction = (x, y, z)
        dist = self._ems_dist
        p1 = dist.lookup(ray.wavelength)
        p2 = 1.0
        max_wavelength = dist.sample(1.0)
        gamma = np.random.uniform(p1, p2)
        wavelength = dist.sample(gamma)
        ray = replace(
            ray,
            direction=direction,
            wavelength=wavelength
        )
        return ray
    

class Material(object):
    
    def __init__(self, refractive_index: float, components=None):
        self.refractive_index = refractive_index
        self.components = [] if components is None else components

    # Cache this function!
    def total_attenutation_coefficient(self, wavelength: float) -> float:
        coefs = [x.coefficient(wavelength) for x in self.components]
        print(coefs)
        alpha = np.sum(coefs)
        return alpha

    def is_absorbed(self, ray, full_distance) -> Tuple[bool, float]:
        distance = self.penetration_depth(ray.wavelength)
        return (distance < full_distance, distance)

    def penetration_depth(self, wavelength: float) -> float:
        """ Monte-Carlo sampling to find penetration depth of ray due to total
            attenuation coefficient of the material.
        
            Arguments
            --------
            wavelength: float
                The ray wavelength in nanometers.

            Returns
            -------
            depth: float
                The penetration depth in centimetres or `float('inf')`.
        """
        alpha = self.total_attenutation_coefficient(wavelength)
        logger.info('Got alpha({}) = {}'.format(wavelength, alpha))
        if np.isclose(alpha, 0.0):
            return float('inf')
        elif not np.isfinite(alpha):
            return 0.0
        # Sample exponential distribution
        depth = -np.log(1 - np.random.uniform())/alpha
        return depth

    def component(self, wavelength: float) -> Union[Scatterer, Luminophore]:
        """ Monte-Carlo sampling to find which component captures the ray.
        """
        coefs = [x.coefficient(wavelength) for x in self.components]
        if np.any(coefs < 0.0):
            raise ValueError("Must be positive.")
        count = len(self.components)
        bins = list(range(0, count + 1))
        cdf = np.cumsum(coefs)
        pdf = cdf / max(cdf)
        pdf = np.hstack([0, pdf[:]])
        pdfinv_lookup = np.interp(np.random.uniform(), pdf, bins)
        index = int(np.floor(pdfinv_lookup))
        component = self.components[index]
        return component
