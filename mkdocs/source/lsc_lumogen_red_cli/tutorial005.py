import time
import sys
import functools
import numpy as np
from pvtrace import *
from pvtrace.data import lumogen_f_red_305


def make_scene():

    world = Node(
        name="world",
        geometry=Sphere(
            radius=100.0,
            material=Material(refractive_index=1.0),
        ),
    )

    x = np.arange(500, 1002, 2)  # wavelength, units: nm
    absorption_spectrum = lumogen_f_red_305.absorption(x)  # units: nm-1
    emission_spectrum = lumogen_f_red_305.emission(x)  # units: nm-1
    absorption_spectrum = absorption_spectrum / np.max(absorption_spectrum) * 5

    lsc = Node(
        name="lsc",
        geometry=Box(
            size=[5, 5, 1],
            material=Material(
                refractive_index=1.5,
                components=[
                    Luminophore(
                        coefficient=np.column_stack((x, absorption_spectrum)),
                        emission=np.column_stack((x, emission_spectrum)),
                        quantum_yield=0.98,
                        phase_function=isotropic,
                    )
                ],
            ),
        ),
        location=(0, 0, 0.5),
        parent=world,
    )

    green_laser = Node(
        name="green-laser",
        light=Light(
            direction=functools.partial(cone, np.radians(22.5)), name="green-laser"
        ),
        parent=world,
    )
    green_laser.location = (0, 0, 1.5)
    green_laser.look_at((0, 0, -1))

    return Scene(world)


# Change zmq_url here to be the address of your meshcat-server!
renderer = MeshcatRenderer(
    zmq_url="tcp://127.0.0.1:6000", wireframe=True, open_browser=True
)
scene = make_scene()
renderer.render(scene)
for ray in scene.emit(10):
    history = photon_tracer.follow(scene, ray)
    path, events = zip(*history)
    # renderer.add_ray_path(path)
    renderer.add_history(history)
    time.sleep(0.1)

# Wait for Ctrl-C to terminate the script; keep the window open
print("Ctrl-C to close")
while True:
    try:
        time.sleep(0.3)
    except KeyboardInterrupt:
        sys.exit()
