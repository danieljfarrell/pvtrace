from ipywidgets import interact
from pvtrace import Ray, photon_tracer
import numpy as np

def interact_ray(scene, vis):

    ray_ids = []
    
    def move_ray(x=0.0, y=0.0, z=0.0, theta=0.0, phi=0.0, nanometers=555.0):
        # Clear old objects
        [vis.remove_object(_id) for _id in ray_ids]
    
        # Create new array with position from the interact UI
        ray = Ray(
            position=(x, y, z),
            direction=(
                np.sin(np.radians(theta)) * np.cos(np.radians(phi)),
                np.sin(np.radians(theta)) * np.sin(np.radians(phi)),
                np.cos(np.radians(theta))
            ),
            wavelength=nanometers
        )
    
        # Re-create the scene with the new ray but reuse the renderers
        steps = photon_tracer.follow(scene, ray, maxsteps=10)
        path, events = zip(*steps)
        vis.render(scene)
    
        # Remove old rays; add new rays
        ray_ids.clear()
        ray_ids.extend(vis.add_ray_path(path))

    return interact(
        move_ray,
        x=(-0.6, 0.6, 0.01),
        y=(-0.6, 0.6, 0.01),
        z=(-0.6, 0.6, 0.01),
        theta=(0, 180, 1),
        phi=(0, 360, 1),
        nanometers=(300, 800, 1)
    )


