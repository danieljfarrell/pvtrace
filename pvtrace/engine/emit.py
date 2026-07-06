"""Vectorized ray emission for the compiled engine.

`scene.emit` calls Python delegate functions once per ray, which
dominates the run time once tracing itself is native. For the built-in
delegate types (everything the YAML spec can express) this module
samples whole bundles with numpy instead; unrecognised delegates fall
back to the per-ray Python path, so custom light sources keep working.
"""
import numpy as np

from pvtrace.light import light as light_module
from pvtrace.material.utils import Cone, HenyeyGreenstein, isotropic, lambertian


def _sphere_directions(theta, phi):
    sin_theta = np.sin(theta)
    return np.column_stack(
        (sin_theta * np.cos(phi), sin_theta * np.sin(phi), np.cos(theta))
    )


def _sample_wavelengths(delegate, n):
    if delegate is light_module.default_wavelength or isinstance(
        delegate, light_module.DefaultWavelength
    ):
        return np.full(n, 555.0)
    if isinstance(delegate, light_module.ConstantWavelengthMask):
        return np.full(n, delegate.nanometers)
    if isinstance(delegate, light_module.SpectrumWavelengthMask):
        return np.asarray(
            delegate.distribution.sample(np.random.uniform(0, 1, n)), dtype=float
        )
    return None


def _sample_positions(delegate, n):
    if delegate is light_module.default_position or isinstance(
        delegate, light_module.DefaultPosition
    ):
        return np.zeros((n, 3))
    if isinstance(delegate, light_module.RectangularMask):
        return np.column_stack((
            np.random.uniform(-delegate.x, delegate.x, n),
            np.random.uniform(-delegate.y, delegate.y, n),
            np.zeros(n),
        ))
    if isinstance(delegate, light_module.CircularMask):
        angle = np.random.uniform(0, 2 * np.pi, n)
        radius = np.sqrt(np.random.uniform(0, 1, n)) * delegate.radius
        return np.column_stack(
            (radius * np.cos(angle), radius * np.sin(angle), np.zeros(n))
        )
    if isinstance(delegate, light_module.CubeMask):
        return np.column_stack((
            np.random.uniform(-delegate.x, delegate.x, n),
            np.random.uniform(-delegate.y, delegate.y, n),
            np.random.uniform(-delegate.z, delegate.z, n),
        ))
    return None


def _sample_directions(delegate, n):
    if delegate is light_module.default_direction or isinstance(
        delegate, light_module.DefaultDirection
    ):
        return np.tile((0.0, 0.0, 1.0), (n, 1))
    if isinstance(delegate, Cone):
        theta = np.arcsin(
            np.sqrt(np.random.uniform(0, 1, n)) * np.sin(delegate.theta_max)
        )
        phi = 2 * np.pi * np.random.uniform(0, 1, n)
        return _sphere_directions(theta, phi)
    if delegate is isotropic:
        phi = 2 * np.pi * np.random.uniform(0, 1, n)
        theta = np.arccos(2 * np.random.uniform(0, 1, n) - 1)
        return _sphere_directions(theta, phi)
    if delegate is lambertian:
        theta = np.arcsin(np.sqrt(np.random.uniform(0, 1, n)))
        phi = 2 * np.pi * np.random.uniform(0, 1, n)
        return _sphere_directions(theta, phi)
    if isinstance(delegate, HenyeyGreenstein):
        g = delegate.g
        if abs(g) < 1e-12:
            return _sample_directions(isotropic, n)
        s = 2 * np.random.uniform(0, 1, n) - 1
        mu = (1 + g * g - ((1 - g * g) / (1 + g * s)) ** 2) / (2 * g)
        phi = 2 * np.pi * np.random.uniform(0, 1, n)
        return _sphere_directions(np.arccos(mu), phi)
    return None


def emit_bundle(scene, num_rays):
    """Emit `num_rays` from the scene's lights as world-frame arrays.

    Returns (positions, directions, wavelengths, sources). Lights with
    built-in delegates are sampled with numpy; others fall back to the
    per-ray Python generator. Rays cycle between lights exactly like
    `scene.emit`.
    """
    lights = scene.light_nodes
    positions = np.zeros((num_rays, 3))
    directions = np.zeros((num_rays, 3))
    wavelengths = np.zeros(num_rays)
    sources = np.empty(num_rays, dtype=object)

    for index, node in enumerate(lights):
        rows = np.arange(index, num_rays, len(lights))
        n = rows.size
        if n == 0:
            continue
        light = node.light
        wav = _sample_wavelengths(light.wavelength, n)
        pos = _sample_positions(light.position, n)
        direction = _sample_directions(light.direction, n)

        if wav is None or pos is None or direction is None:
            # Unknown delegate: per-ray Python fallback for this light
            for row, ray in zip(rows, node.emit(n)):
                world = ray.representation(node, scene.root)
                positions[row] = world.position
                directions[row] = world.direction
                wavelengths[row] = world.wavelength
                sources[row] = world.source
            continue

        matrix = np.asarray(node.transformation_to(scene.root))
        rotation = matrix[:3, :3]
        translation = matrix[:3, 3]
        positions[rows] = pos @ rotation.T + translation
        directions[rows] = direction @ rotation.T
        wavelengths[rows] = wav
        sources[rows] = light.name

    return positions, directions, wavelengths, sources.tolist()
