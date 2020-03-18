from pvtrace.material.component import Absorber, Luminophore
from pvtrace.light.light import Light
from pvtrace.light.event import Event
from pvtrace.scene.node import Node
from pvtrace.material.material import Material
from pvtrace.material.utils import isotropic, cone
from pvtrace.scene.scene import Scene
from pvtrace.geometry.box import Box
from pvtrace.geometry.utils import EPS_ZERO
from pvtrace.data import lumogen_f_red_305
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.material.surface import Surface, FresnelSurfaceDelegate
from pvtrace.algorithm import photon_tracer
from dataclasses import asdict
import numpy as np
import pandas as pd
import functools
import time


class CustomSurfaces(FresnelSurfaceDelegate):
    """ A delegate adds a perfect specular mirror to the bottom surface and 
        perfectly absorbing solar cells to the edge.
    """
    
    def __init__(self, lsc):
        super(CustomSurfaces, self).__init__()
        self.lsc = lsc

    def reflectivity(self, surface, ray, geometry, container, adjacent):
        normal = geometry.normal(ray.position)
        # find bottom facet, it has normal (0, 0, -1)
        cell_locations = self.lsc._solar_cell_surfaces
        back_surface_mirror = self.lsc._back_surface_mirror
        
        if np.allclose((0, 0, -1), normal) and back_surface_mirror:
            return 1.0  # perfect mirror
        elif np.allclose((-1, 0, 0), normal) and 'left' in cell_locations: # left
            return 0.0
        elif np.allclose((1, 0, 0), normal) and 'right' in cell_locations:  # right
            return 0.0
        elif np.allclose((0, -1, 0), normal) and 'near' in cell_locations:  # near
            return 0.0
        elif np.allclose((0, 1, 0), normal) and 'far' in cell_locations:  # far
            return 0.0
        return super(CustomSurfaces, self).reflectivity(surface, ray, geometry, container, adjacent)  # opt-out of handling custom reflection

    def transmitted_direction(self, surface, ray, geometry, container, adjacent):
        cell_locations = self.lsc._solar_cell_surfaces
        normal = geometry.normal(ray.position)
        if (np.allclose((-1, 0, 0), normal) and 'left' in cell_locations) \
            or (np.allclose((1, 0, 0), normal) and 'right' in cell_locations) \
            or (np.allclose((0, -1, 0), normal) and 'near' in cell_locations) \
            or (np.allclose((0, 1, 0), normal) and 'far' in cell_locations):
            return ray.direction #  solar cell is perfectly index matched
        return super(CustomSurfaces, self).transmitted_direction(surface, ray, geometry, container, adjacent)  # opt-out of handling custom reflection


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
        
        self._solar_cell_surfaces = set()
        self._back_surface_mirror = False
        self._luminophores = self._make_default_luminophores()
        self._lights = self._make_default_lights()
        self._scene = self._make_scene()
        self._renderer = None
        self._store = None
        self._df = None
        self._counts = None

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
            phase_function=isotropic,
            name="Lumogen F Red 305"
        )
        background = Absorber(coefficient=0.1, name="Background")  # cm-1
        return [lumogen_red, background]

    def _make_default_lights(self):
        """ Default light is a spotlight (cone of 20-deg) of single wavelength 555nm.
        """
        light = Light(direction=functools.partial(cone, np.radians(20)))
        position = (0.0, 0.0, self.size[-1] * 5)
        rotation = (np.radians(180), (1, 0, 0))
        return [(light, position, rotation)]

    def _make_scene(self):
        """ Creates the scene based on configuration values.
        """
        (l, w, d) = self.size
        world = Node(
            name="World",
            geometry=Box(
                (l * 100, w * 100, d * 100),
                material=Material(refractive_index=self.n0),
            ),
        )

        lsc = Node(
            name="LSC",
            geometry=Box(
                (l, w, d),
                material=Material(
                    refractive_index=self.n1, components=self._luminophores,
                    surface=Surface(delegate=CustomSurfaces(self))
                ),
            ),
            parent=world,
        )

        for idx, (light, location, rotation) in enumerate(self._lights):
            name = f"Light {idx+1}"
            light.name = name
            light_node = Node(name=name, light=light, parent=world)
            light_node.location = location
            light_node.rotate(*rotation)

        self._scene = Scene(world)

    def add_solar_cell(self, facet):
        allowed = {'left', 'near', 'far', 'right'}
        if not (facet in allowed):
            raise ValueError('Solar cell have allowed surfaces', allowed)
        
        self._solar_cell_surfaces = set([facet]).union(self._solar_cell_surfaces)

    def remove_solar_cell(self, facet):
        allowed = {'left', 'near', 'far', 'right'}
        if not (facet in allowed):
            raise ValueError('Solar cell have allowed surfaces', allowed)

        try:
            self._solar_cell_surfaces.pop(facet)
        except:
            pass
    
    def add_back_surface_mirror(self):
        self._back_surface_mirror = True

    def remove_back_surface_mirror(self):
        self._back_surface_mirror = False

    # Simulate

    def show(
        self,
        wireframe=True,
        baubles=True,
        bauble_radius=None,
        world_segment="short",
        short_length=None,
    ):

        if bauble_radius is None:
            bauble_radius = np.min(self.size) * 0.05

        if short_length is None:
            short_length = np.min(self.size) * 0.1

        self._add_history_kwargs = {
            "bauble_radius": bauble_radius,
            "baubles": baubles,
            "world_segment": world_segment,
            "short_length": short_length,
        }

        if self._scene is None:
            self._make_scene()

        self._renderer = MeshcatRenderer(
            open_browser=True,
            transparency=False,
            opacity=0.5,
            wireframe=wireframe,
            max_histories=50,
        )
        self._renderer.render(self._scene)
        time.sleep(1.0)

    def simulate(self, n, progress=None, emit_method="kT"):
        if self._scene is None:
            self._make_scene()
        scene = self._scene

        store = {"entrance_rays": [], "exit_rays": []}
        vis = self._renderer
        count = 0
        for ray in scene.emit(n):
            history = photon_tracer.follow(scene, ray, emit_method=emit_method)
            rays, events = zip(*history)
            store["entrance_rays"].append((rays[1], events[1]))
            if events[-1] in (Event.ABSORB, Event.KILL):
                # final event is a lost store path information at final event
                store["exit_rays"].append((rays[-1], events[-1]))
            elif events[-1] == Event.EXIT:
                # final event hits the world node. Store path information at
                # penultimate location
                store["exit_rays"].append((rays[-2], events[-2]))

            # Update visualiser
            if vis:
                vis.add_history(history, **self._add_history_kwargs)

            # Progress callback
            if progress:
                count += 1
                progress(count)

        self._store = store

    def _make_dataframe(self):
        df = pd.DataFrame()

        # Rays entering the scene
        for ray, event in self._store['entrance_rays']:
            rep = asdict(ray)
            rep['kind'] = 'entrance'
            rep['event'] = event.name
            df = df.append(rep, ignore_index=True)
    
        # Rays exiting the scene
        for ray, event in self._store['exit_rays']:
            rep = asdict(ray)
            rep['kind'] = 'exit'
            rep['event'] = event.name
            df = df.append(rep, ignore_index=True)
        
        self._df = df
        return df
    
    def expand_coords(self, df, column):
        """ Returns a dataframe with coordinate column expanded into components.
    
            Parameters
            ----------
            df : pandas.DataFrame
                The dataframe
            column : str
                The column label
        
            Returns
            -------
            df : pandas.DataFrame
                The dataframe with the column expanded.
        
            Example
            -------
            Given the dataframe::
        
                df = pd.DataFrame({'position': [(1,2,3)]})
        
            the function will return a new dataframe::
        
                edf = expand_coords(df, 'position')
                edf == pd.DataFrame({'position_x': [1], 'position_y': [2], 'position_z': [3]})
        
        """
        coords = np.stack(df[column].values)
        df['{}_x'.format(column)] = coords[:, 0]
        df['{}_y'.format(column)] = coords[:, 1]
        df['{}_z'.format(column)] = coords[:, 2]
        df.drop(columns=column, inplace=True)
        return df

    def label_facets(self, df, length, width, height):
        """ Label rows with facet names for a box LSC.
    
            Notes
            -----
            This function only works if the coordinates in the dataframe
            are in the local frame of the box. If the coordinates are in the
            world frame then this will still work provided the box is axis
            aligned with the world node and centred at the origin.
        """
        xmin, xmax = -0.5*length, 0.5*length
        ymin, ymax = -0.5*width, 0.5*width
        zmin, zmax = -0.5*height, 0.5*height
        df.loc[(np.isclose(df['position_x'], xmin, atol=EPS_ZERO)), 'facet'] = '-x'
        df.loc[(np.isclose(df['position_x'], xmax, atol=EPS_ZERO)), 'facet'] = '+x'
        df.loc[(np.isclose(df['position_y'], ymin, atol=EPS_ZERO)), 'facet'] = '-y'
        df.loc[(np.isclose(df['position_y'], ymax, atol=EPS_ZERO)), 'facet'] = '+y'
        df.loc[(np.isclose(df['position_z'], zmin, atol=EPS_ZERO)), 'facet'] = '-z'
        df.loc[(np.isclose(df['position_z'], zmax, atol=EPS_ZERO)), 'facet'] = '+z'
        return df

    def _make_counts(self, df):
        
        if self._counts is not None:
            return self._counts

        components = self._scene.component_nodes
        lights = self._scene.light_nodes
        is_exit = (df['kind']=='exit')
        is_entrance = (df['kind']=='entrance')
        is_reflected = (df['event']=='REFLECT')
        is_transmitted = (df['event']=='TRANSMIT')
        is_luminescent = df['source'].isin([component.name for component in components])
        is_light = df['source'].isin([light.name for light in lights])
        is_left_facet = (df['facet']=='-x')
        is_right_facet = (df['facet']=='+x')
        is_far_facet = (df['facet']=='-y')
        is_near_facet = (df['facet']=='+y')
        is_bottom_facet = (df['facet']=='-z')
        is_top_facet = (df['facet']=='+z')

        # Count luminescent (or scattered) photons exiting
        luminescent_exit_counts = dict()
        luminescent_exit_counts['left'] = \
            df.loc[is_exit & is_luminescent & is_transmitted & is_left_facet].shape[0]
        luminescent_exit_counts['right'] = \
            df.loc[is_exit & is_luminescent & is_transmitted & is_right_facet].shape[0]
        luminescent_exit_counts['far'] = \
            df.loc[is_exit & is_luminescent & is_transmitted & is_far_facet].shape[0]
        luminescent_exit_counts['near'] = \
            df.loc[is_exit & is_luminescent & is_transmitted & is_near_facet].shape[0]
        luminescent_exit_counts['bottom'] = \
            df.loc[is_exit & is_luminescent & is_transmitted &  is_bottom_facet].shape[0]
        luminescent_exit_counts['top'] = \
            df.loc[is_exit & is_luminescent & is_transmitted & is_top_facet].shape[0]

        # Count solar photons entering
        solar_entrance_counts = dict()
        solar_entrance_counts['left'] = \
            df.loc[is_entrance & is_light & is_left_facet].shape[0]
        solar_entrance_counts['right'] = \
            df.loc[is_entrance & is_light & is_right_facet].shape[0]
        solar_entrance_counts['far'] = \
            df.loc[is_entrance & is_light & is_far_facet].shape[0]
        solar_entrance_counts['near'] = \
            df.loc[is_entrance & is_light & is_near_facet].shape[0]
        solar_entrance_counts['bottom'] = \
            df.loc[is_entrance & is_light & is_bottom_facet].shape[0]
        solar_entrance_counts['top'] = \
            df.loc[is_entrance & is_light & is_top_facet].shape[0]

        # Count solar photons exiting
        solar_exit_counts = dict()
        solar_exit_counts['left'] = \
            df.loc[is_exit & is_light & is_left_facet].shape[0]
        solar_exit_counts['right'] = \
            df.loc[is_exit & is_light & is_right_facet].shape[0]
        solar_exit_counts['far'] = \
            df.loc[is_exit & is_light & is_far_facet].shape[0]
        solar_exit_counts['near'] = \
            df.loc[is_exit & is_light & is_near_facet].shape[0]
        solar_exit_counts['bottom'] = \
            df.loc[is_exit & is_light & is_bottom_facet].shape[0]
        solar_exit_counts['top'] = \
            df.loc[is_exit & is_light & is_top_facet].shape[0]

        counts = {
            'luminescent_exit': pd.Series(luminescent_exit_counts),
            'solar_exit': pd.Series(solar_exit_counts),
            'solar_entrance': pd.Series(solar_entrance_counts)
        }
        self._counts = counts
        return counts

    def stats(self):
        if self._df is None:
            df = self._make_dataframe()
        df = self.expand_coords(df, 'direction')
        df = self.expand_coords(df, 'position')
        df = self.label_facets(df, *self.size)
        counts = self._make_counts(df)
        print(counts)
        
        luminescent_exit = counts['luminescent_exit']
        solar_exit = counts['solar_exit']
        solar_entrance = counts['solar_entrance']

        incident = solar_entrance['top']
        transmitted = incident - solar_exit['top']
        reflected = solar_exit['top']
        lum_edges = \
            luminescent_exit['left'] + \
            luminescent_exit['right'] + \
            luminescent_exit['near'] + \
            luminescent_exit['far']
        lum_escaping = luminescent_exit['top'] + luminescent_exit['bottom']
        
        optical_efficiency = lum_edges / incident
        waveguide_efficiency = lum_edges / (lum_edges + lum_escaping)
        
        (l, w, d) = self.size
        a1 = w * l
        a2 = 2*l*d + 2*w*d
        Cg = a1/a2
        n = self.n1
        s = {
            "eta_opt": optical_efficiency,
            "eta_wave": waveguide_efficiency,
            "Cg": Cg,
            "n":n,
            "eta_wave_estimate": (n**2/(Cg+n**2))
        }
        return s


if __name__ == "__main__":
    lsc = LSC((5.0, 5.0, 1.0))
    lsc.add_back_surface_mirror()
    lsc.add_solar_cell('left')
    lsc.add_solar_cell('right')
    lsc.add_solar_cell('near')
    lsc.add_solar_cell('far')
    lsc.show()
    lsc.simulate(100)
    print(lsc.stats())
