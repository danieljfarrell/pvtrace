from pvtrace import *
import numpy as np
import functools
import time


class LSC(object):
    """Abstraction of a luminescent solar concentrator.
    
       This is intended to be a high-level API to easy use.
    """
    def __init__(self, size, n0=1.0, n1=1.5, x=np.linspace(400.0, 800.0)):
        super(LSC, self).__init__()
        self.size = size  # centimetres
        self.n0 = n0
        self.n1 = n1
        self.x = x  # wavelengths in nanometers
        
        self._luminophores = self._make_default_luminophores()
        self._lights = self._make_default_lights()
        self._scene = self._make_scene()
        self._renderer = None
        self._store = None

    def _make_default_luminophores(self):
        """ Default LSC contains Lumogen F Red 305. With concentration such that
            the absorption coefficient at peak is 10 cm-1.
        """
        x = self.x
        absorption_spectrum = lumogen_f_red_305.absorption(x) * 10.0  # cm-1
        emission_spectrum = lumogen_f_red_305.emission(x) 
        lumogen_red = Luminophore(
            coefficient=np.column_stack((x, absorption_spectrum)),
            emission=np.column_stack((x, emission_spectrum)),
            quantum_yield=1.0,
            phase_function=isotropic
        )
        background = Absorber(
            coefficient=0.01  # cm-1
        )
        return [lumogen_red, background]

    def _make_default_lights(self):
        """ Default light is a spotlight (cone of 20-deg) of single wavelength 555nm.
        """
        light = Light(direction=functools.partial(cone, np.radians(20)))
        position = (0.0, 0.0, self.size[-1]*5)
        rotation = (np.radians(180), (1, 0, 0))
        return [(light, position, rotation)]

    
    def _make_scene(self):
        """ Creates the scene based on configuration values.
        """
        (l, w, d) = self.size
        world = Node(
            name = "World",
            geometry = Box(
                (l*100, w*100, d*100),
                material=Material(refractive_index=self.n0),
            )
        )
        
        lsc = Node(
            name = "LSC",
            geometry = Box(
                (l, w, d),
                material = Material(
                    refractive_index = self.n1,
                    components = self._luminophores
                ),
            ),
            parent=world
        )
        
        for idx, (light, location, rotation) in enumerate(self._lights):
            light = Node(
                name = "Light {idx+1}",
                light = light,
                parent=world
            )
            light.location = location
            light.rotate(*rotation)

        self._scene = Scene(world)

    # Simulate

    def show(self, wireframe=True):
        if self._scene is None:
            self._make_scene()

        self._renderer = MeshcatRenderer(
            open_browser=True,
            transparency=False,
            opacity=0.5,
            wireframe=wireframe,
            max_histories=50
        )
        self._renderer.render(self._scene)
        time.sleep(1.0)

    def simulate(self, n, progress=None, emit_method='kT'):
        if self._scene is None:
            self._make_scene()
        scene = self._scene

        store = {'entrance_rays': [], 'exit_rays': []}
        vis = self._renderer 
        count = 0
        for ray in scene.emit(n):
            history = photon_tracer.follow(
                scene,
                ray,
                emit_method=emit_method
            )
            rays, events = zip(*history)
            store['entrance_rays'].append(rays[0])
            if events[-1] in (photon_tracer.Event.ABSORB, photon_tracer.Event.KILL):
                # final event is a lost store path information at final event
                store['exit_rays'].append(rays[-1])  
            elif events[-1] == photon_tracer.Event.EXIT:
                # final event hits the world node. Store path information at
                # penultimate location
                store['exit_rays'].append(rays[-2])
        
            # Update visualiser
            if vis:
                vis.add_history(
                    history,
                    baubles=True,
                    world_segment='short',
                    short_length=self.size[-1],
                    bauble_radius=self.size[-1]/12
                )
                    
            
            # Progress callback
            if progress:
                count += 1
                progress(count)
        
        self._store = store
    
    def stats(self):
        pass

if __name__ == '__main__':
    
    lsc = LSC((1.0, 1.0, 0.1))
    lsc.show()
    lsc.simulate(1000)
    print(lsc.stats())
    
