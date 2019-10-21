import collections
import traceback
from typing import Union
from dataclasses import replace
import numpy as np
from pvtrace.geometry.utils import (
    distance_between, close_to_zero, points_equal, flip, angle_between
)
import logging
logger = logging.getLogger(__name__)


def isotropic():
    g1, g2 = np.random.uniform(0, 1, 2)
    phi = 2 * np.pi * g1
    mu = 2 * np.pi * g2 - 1 # mu = cos(theta)
    theta = np.arccos(mu)
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(theta)
    return (x, y, z)


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
    print("Reflection", (direction, normal))
    
    vec = np.array(direction)
    normal = np.array(normal)
    if np.dot(normal, direction) < 0.0:
        normal = flip(normal)
    d = np.dot(normal, vec)
    reflected_direction = vec - 2 * d * normal
    return reflected_direction


def fresnel_refraction(direction, normal, n1, n2):
    print("Refraction", (direction, normal, n1, n2))
    vector = np.array(direction)
    normal = np.array(normal)
    if np.dot(normal, direction) < 0.0:
        normal = flip(normal)
    n = n1/n2
    dot = np.dot(vector, normal)
    c = np.sqrt(1 - n**2 * (1 - dot**2))
    sign = 1
    if dot < 0.0:
        sign = -1
    refracted_direction = n * vector + sign*(c - sign*n*dot) * normal
    return refracted_direction


class Surface(object):
    """ Surface of a geometry which handles details of reflection at an interface.
    """

    def is_reflected(self, ray, geometry, container, adjacent):
        """ Monte-Carlo sampling. Default is to transmit.
        """
        return False

    def reflect(self, ray, geometry, container, adjacent):
        """ Specular reflection.
        """
        normal = geometry.normal(ray.position)
        direction = ray.direction
        print("Incident ray", direction)
        reflected_direction = specular_reflection(direction, normal)
        print("Reflected ray", reflected_direction)
        ray = replace(
            ray,
            position=ray.position, 
            direction=tuple(reflected_direction.tolist())
        )
        return ray

    def transmit(self, ray, geometry, container, adjacent):
        """ Simply propgate."""
        return ray


class FresnelSurface(Surface):
    """ Implements reflection and refraction at an interface of two dielectrics.
    """
    
    def is_reflected(self, ray, geometry, container, adjacent):
        """ Monte-Carlo sampling. Default is to transmit.
        """
        # to-do: express ray in local coordinate system
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        angle = angle_between(normal, np.array(ray.direction))
        gamma = np.random.uniform()
        return gamma < fresnel_reflectivity(angle, n1, n2)

    def transmit(self, ray, geometry, container, adjacent):
        """ Refract through the interface.
        """
        # to-do: express ray in local coordinate system
        n1 = container.geometry.material.refractive_index
        n2 = adjacent.geometry.material.refractive_index
        # Be tolerance with definition of surface normal
        normal = geometry.normal(ray.position)
        if np.dot(normal, ray.direction) < 0.0:
            normal = flip(normal)
        refracted_direction = fresnel_refraction(ray.direction, normal, n1, n2)
        ray = replace(
            ray,
            position=ray.position, 
            direction=tuple(refracted_direction.tolist())
        )
        return ray


class Hit(object):
    """ Describes the hit location of a ray.
    """
    def __init__(self, node, position, distance):
        #: The node that has been hit
        self.node = node
        #: The hit point on node's surface
        self.position = position 
        #: Distance the ray tracelled to reach the point
        self.distance = distance


class Component(object):
    """ Base class for all things that can be added to a host material.
    """
    def __init__(self, *args, **kwargs):
        super(Component, self).__init__(*args, **kwargs)
    
    def is_radiative(self, ray):
        return False


class Scatterer(Component):
    """Describes a scatterer center with attenuation coefficient per unit length."""
    
    def __init__(self, coefficient, *args, quantum_yield=1.0, phase_function=None, **kwargs):
        super(Scatterer, self).__init__(*args, **kwargs)
        self.coefficient = coefficient
        self.quantum_yield = quantum_yield
        self.phase_function = isotropic if phase_function is None else phase_function

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


class Luminophore(Component):
    """Describes molecule, nanocrystal or material which absorbs and emits light."""
    
    def __init__(self, coefficient, lineshape, quantum_yield=1.0, phase_function=None):
        super(Luminophore, object).__init__(
            coefficient, *args, 
            quantum_yield=quantum_yield, phase_function=phase_function, **kwargs
        )
        
        self.lineshape = lineshape
        if isinstance(lineshape, np.ndarray)
            self._emission_dist = Distribution(
                x=lineshape[:, 0],
                y=lineshape[:, 1]
            )
    def emit(self, ray: "Ray") -> "Ray":
        """ Change ray direction or wavelength based on physics of the interaction.
        """
        direction = self.phase_function()
        dist = self._emission_dist
        p1 = dist.lookup(ray.wavelength)
        p2 = 1.0
        max_wavelength = dist.sample(1.0)
        gamma = np.random.uniform(p1, p2)
        wavelength = dist.sample(gamma)
        ray = replace(
            ray,
            direction=tuple(direction.tolist()),
            wavelength=wavelength
        )
        return ray
    

class Material(object):
    
    def __init__(self, refractive_index: float, components=None):
        self.refractive_index = refractive_index
        self.components = [] if components is None else components

    # Cache this function!
    def total_attenutation_coefficient(self, wavelength: float) -> float:
        coefs = [x.coefficient for x in self.components]
        alpha = np.sum(coefs)
        return alpha

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
        coefs = [x.coefficient for x in self.components]
        count = len(self.components)
        bins = list(range(0, count + 1))
        cdf = np.cumsum(coefs)
        pdf = cdf / max(cdf)
        pdf = np.hstack([0, pdf[:]])
        pdfinv_lookup = np.interp(np.random.uniform(), pdf, bins)
        index = int(np.floor(pdfinv_lookup))
        component = self.components[index]
        return component


def find_container(intersections):
    # Find container node that has two properties:
    # 1. only appears in the intersection list once
    # 2. of the above is the has closest intersection to ray position
    if len(intersections) == 1:
        return intersections[0].hit
    count = collections.Counter([x.hit for x in intersections]).most_common()
    candidates = [x[0] for x in count if x[1] == 1]
    pairs = []
    for intersection in intersections:
        node = intersection.hit
        if node in candidates:
            pairs.append((node, intersection.distance))
    # [(node, dist), (node, dist)... ]
    pairs = sorted(pairs, key=lambda tup: tup[1])
    containers, _ = zip(*pairs)
    container = containers[0]
    return container


def next_hit(scene, ray):
    intersections = scene.intersections(ray.position, ray.direction)
    # Remove on surface intersections
    intersections = \
        [x for x in intersections if not close_to_zero(x.distance)]

    # Node which owns the surface
    if len(intersections) == 0:
        return None

    # The surface being hit
    hit = intersections[0]
    if len(intersections) == 1:
        hit_node = hit.hit
        return hit_node, (hit_node, None), hit.point, hit.distance
    
    container = find_container(intersections)
    hit = intersections[0]
    # Intersection point and distance from ray
    point = hit.point
    hit_node = hit.hit
    distance = distance_between(ray.position, point)
    if container == hit_node:
        adjacent = intersections[1].hit
    else:
        adjacent = hit_node
    return hit_node, (container, adjacent), point, distance


def trace(scene, ray, maxsteps=20):
    count = 0
    history = [ray]
    while True:
        count += 1
        if count > maxsteps:
            print("Max count reached.")
            break

        info = next_hit(scene, ray)
        print("Info: ", info)
        if info is None:
            print("[1] Exit.")
            break

        hit, (container, adjacent), point, full_distance = info
        print("interface: {}|{}".format(container, adjacent))
        if hit is scene.root:
            print("[2] Exit.")
            break

        material = container.geometry.material
        travelled_distance = material.penetration_depth(ray)
        if travelled_distance < full_distance:
            ray = ray.propagate(travelled_distance)
            component = material.component(ray)
            if component.is_radiative(ray):
                ray = component.emit(ray)
                history.append(ray)
                print("Step", ray)
                continue
            else:
                history.append(ray)
                print("[3] Exit.")
                break
        else:
            ray = ray.propagate(full_distance)
            surface = hit.geometry.surface
            if surface.is_reflected(ray, hit.geometry, container, adjacent):
                ray = surface.reflect(ray, hit.geometry, container, adjacent)
                history.append(ray)
                print("REFLECT", ray)
                continue
            else:
                ray = surface.transmit(ray, hit.geometry, container, adjacent)
                history.append(ray)
                print("TRANSMIT", ray)
                continue
    return history


if __name__ == '__main__':
    from pvtrace.scene.scene import Scene
    from pvtrace.scene.node import Node
    from pvtrace.light.ray import Ray
    from pvtrace.geometry.sphere import Sphere
    import numpy as np
    np.random.seed(2)
    air = Material(refractive_index=1.0)
    plastic = Material(
        refractive_index=1.5,
        components=[
            Scatterer(coefficient=2.0)
        ]
    )
    world = Node(
        name="world",
        geometry=Sphere(
            radius=10,
            material=air,
            surface=Surface()
        )
    )
    ball = Node(
        name="ball",
        parent=world,
        geometry=Sphere(
            radius=1,
            material=plastic,
            surface=FresnelSurface()
        )
    )
    ray = Ray(position=(0, 0., 2), direction=(0, 0, -1), wavelength=555)
    scene = Scene(root=world)
    history = trace(scene, ray)
    for r in history:
        print(r)
