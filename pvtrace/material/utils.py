import numpy as np
from pvtrace.geometry.utils import (
    flip,
    angle_between
)
# Fresnel

def fresnel_reflectivity(angle, n1, n2):
    # Catch TIR case
    if n2 < n1 and angle > np.arcsin(n2/n1):
        return 1.0
    c = np.cos(angle)
    s = np.sin(angle)
    k = np.sqrt(1 - (n1/n2 * s)**2)
    Rs1 = n1 * c - n2 * k
    Rs2 = n1 * c + n2 * k
    Rs = (Rs1/Rs2)**2
    Rp1 = n1 * k - n2 * c
    Rp2 = n1 * k + n2 * c
    Rp = (Rp1/Rp2)**2
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
    # print("Refraction", (direction, normal, n1, n2))
    vector = np.array(direction)
    normal = np.array(normal)
    if np.dot(normal, vector) < 0.0:
        normal = flip(normal)
    n = n1/n2
    dot = np.dot(vector, normal)
    c = np.sqrt(1 - n**2 * (1 - dot**2))
    sign = 1
    if dot < 0.0:
        sign = -1
    refracted_direction = n * vector + sign*(c - sign*n*dot) * normal
    return refracted_direction


# Lineshape

gaussian = lambda x, c1, c2, c3: c1*np.exp(-((c2 - x)/c3)**2)

bandgap = lambda x, cutoff, alpha: (1 - np.heaviside(x-cutoff, 0.5)) * alpha


# Scattering

def isotropic():
    g1, g2 = np.random.uniform(0, 1, 2)
    phi = 2 * np.pi * g1
    mu = 2 * g2 - 1 # mu = cos(theta)
    theta = np.arccos(mu)
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = mu
    return norm([x, y, z])


def henyey_greenstein(g=0.0):
    # https://www.astro.umd.edu/~jph/HG_note.pdf
    p = np.random.uniform(0, 1)
    s = 2 * p - 1
    mu = 1/(2*g) * (1 + g**2 - ((1 - g**2)/(1 + g*s))**2)
    # Inverse is not defined at g=0 but in the limit 
    # tends to the isotropic case.
    if close_to_zero(g):
        return isotropic()
    phi = 2 * np.pi * np.random.uniform()
    theta = np.arccos(mu)
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = mu
    return (x, y, z)


