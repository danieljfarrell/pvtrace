import numpy as np
from pvtrace.geometry.utils import flip

# Fresnel


def fresnel_reflectivity(angle, n1, n2):
    # Catch TIR case
    if n2 < n1 and angle > np.arcsin(n2 / n1):
        return 1.0
    c = np.cos(angle)
    s = np.sin(angle)
    k = np.sqrt(1 - (n1 / n2 * s) ** 2)
    Rs1 = n1 * c - n2 * k
    Rs2 = n1 * c + n2 * k
    Rs = (Rs1 / Rs2) ** 2
    Rp1 = n1 * k - n2 * c
    Rp2 = n1 * k + n2 * c
    Rp = (Rp1 / Rp2) ** 2
    r = 0.5 * (Rs + Rp)
    return r


def specular_reflection(direction, normal):
    direction = np.array(direction)
    normal = np.array(normal)
    if np.dot(normal, direction) < 0.0:
        normal = flip(normal)
    d = np.dot(normal, direction)
    reflected_direction = direction - 2 * d * normal
    return reflected_direction


def fresnel_refraction(direction, normal, n1, n2):
    vector = np.array(direction)
    normal = np.array(normal)
    n = n1 / n2
    dot = np.dot(vector, normal)
    c = np.sqrt(1 - n ** 2 * (1 - dot ** 2))
    sign = 1
    if dot < 0.0:
        sign = -1
    refracted_direction = n * vector + sign * (c - sign * n * dot) * normal
    return refracted_direction


# Lineshape


def gaussian(x, c1, c2, c3):
    return c1 * np.exp(-(((c2 - x) / c3) ** 2))


def bandgap(x, cutoff, alpha):
    return (1 - np.heaviside(x - cutoff, 0.5)) * alpha


def simple_convert_spectum(spec):
    """ Change spectrum x-axis only.
    """
    h = 6.62607015e-34  # J s
    c = 299792458.0  # m s-1
    q = 1.60217662e-19  # C
    kb = 1.38064852e-23  # K K-1
    conversion_constant = h * c / q * 1e9
    xp = conversion_constant / spec[:, 0]
    _spec = np.array(spec)
    _spec[:, 0] = xp
    return _spec


def thermodynamic_emission(abs_spec, T=300, mu=0.5):
    h = 6.62607015e-34  # J s
    c = 299792458.0  # m s-1
    q = 1.60217662e-19  # C
    kb = 1.38064852e-23  # J K-1
    conversion_constant = h * c / q * 1e9
    energy_spec = simple_convert_spectum(abs_spec)
    x, y = energy_spec[:, 0], energy_spec[:, 1]
    ems_energy = (
        y * 2 * x ** 2 / (c ** 2 * (h / q) ** 3) / np.expm1((x - mu) / ((kb / q) * T))
    )
    ems_energy /= np.max(ems_energy)
    ems_wavelength = simple_convert_spectum(np.column_stack((x, ems_energy)))
    return ems_wavelength


# Coordinates


def spherical_to_cart(theta, phi, r=1):
    x = r * np.sin(theta) * np.cos(phi)
    y = r * np.sin(theta) * np.sin(phi)
    z = r * np.cos(theta)
    cart = np.column_stack((x, y, z))
    if cart.size == 3:
        return cart[0, :]
    return cart


#  Volume scattering


def isotropic():
    """ Isotropic phase function.
    """
    g1, g2 = np.random.uniform(0, 1, 2)
    phi = 2 * np.pi * g1
    mu = 2 * g2 - 1  # mu = cos(theta)
    theta = np.arccos(mu)
    coords = spherical_to_cart(theta, phi)
    return coords


def henyey_greenstein(g=0.0):
    """ Henyey-Greenstein phase function.
    """
    # https://www.astro.umd.edu/~jph/HG_note.pdf
    p = np.random.uniform(0, 1)
    s = 2 * p - 1
    mu = 1 / (2 * g) * (1 + g ** 2 - ((1 - g ** 2) / (1 + g * s)) ** 2)
    # Inverse is not defined at g=0 but in the limit
    # tends to the isotropic case.
    if close_to_zero(g):
        return isotropic()
    phi = 2 * np.pi * np.random.uniform()
    theta = np.arccos(mu)
    coords = spherical_to_cart(theta, phi)
    return coords


# Light source /surface scattering


def cone(theta_max):
    """ Samples directions within a cone of solid angle defined by `theta_max`.
    
        Notes
        -----
        Derived as follows using sympy::
    
            from sympy import *
            theta, theta_max, p = symbols('theta theta_max p')
            f = cos(theta) * sin(theta)
            cdf = integrate(f, (theta, 0, theta))
            pdf = cdf / cdf.subs({theta: theta_max})
            inv_pdf = solve(Eq(pdf, p), theta)[-1]
    """
    if np.isclose(theta_max, 0.0) or theta_max > np.pi / 2:
        raise ValueError("Expected 0 < theta_max <= pi/2")
    p1, p2 = np.random.uniform(0, 1, 2)
    theta = np.arcsin(np.sqrt(p1) * np.sin(theta_max))
    phi = 2 * np.pi * p2
    coords = spherical_to_cart(theta, phi)
    return coords


def lambertian():
    """ Samples the Lambertian directions emitted from a surface with normal
        pointing along the positive z-direction.
        
        This never produces directions in the negative z-direction.
    """
    p1, p2 = np.random.uniform(0, 1, 2)
    theta = np.arcsin(np.sqrt(p1))
    phi = 2 * np.pi * p2
    coords = spherical_to_cart(theta, phi)
    return coords
