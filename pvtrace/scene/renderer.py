import numpy as np
import os
import time
import io
from typing import Tuple
from contextlib import contextmanager
from collections import deque
from anytree import LevelOrderIter, PostOrderIter
from pvtrace.geometry.sphere import Sphere
from pvtrace.geometry.cylinder import Cylinder
from pvtrace.geometry.mesh import Mesh
from pvtrace.light.ray import Ray
from pvtrace.light.utils import wavelength_to_rgb, rgb_to_hex_int, wavelength_to_hex_int
from pvtrace.light.event import Event
import trimesh
import meshcat
import meshcat.geometry as g
import meshcat.transformations as tf
import logging

logger = logging.getLogger(__name__)


class MeshcatRenderer(object):
    """Renders a scene nodes structure."""

    def __init__(
        self,
        zmq_url=None,
        max_histories=10000,
        open_browser=False,
        wireframe=False,
        transparency=True,
        opacity=0.5,
        reflectivity=1.0,
    ):
        super(MeshcatRenderer, self).__init__()
        self.vis = meshcat.Visualizer(zmq_url=zmq_url)
        if open_browser:
            self.vis.open()
        self.ray_histories = deque(maxlen=max_histories)
        self.max_histories = max_histories
        self.added_index = 0
        self.wireframe = wireframe
        self.transparency = transparency
        self.opacity = opacity
        self.reflectivity = reflectivity

    def render(self, scene, show_root=False):
        """
        """
        vis = self.vis
        for node in LevelOrderIter(scene.root):
            if node == scene.root:
                continue
            self.add_node(node)

    def add_node(self, node):
        # Using a dot here as a quick fix to _avoid_ Meshcat automatically
        # transforming the parent coordinate system. If you use `"/"` then
        # you would get that behaviour.
        pathname = " | ".join([x.name for x in node.path])
        if node.geometry is not None:
            # Transforming everything to global
            self.add_geometry(
                node.geometry, pathname, node.transformation_to(node.root)
            )

    def add_geometry(self, geometry, pathname, transform):
        vis = self.vis
        material = g.MeshBasicMaterial(
            reflectivity=self.reflectivity, sides=0, wireframe=self.wireframe
        )
        material.transparency = self.transparency
        material.opacity = self.opacity

        if isinstance(geometry, Sphere):
            sphere = geometry
            vis[pathname].set_object(g.Sphere(sphere.radius), material)
            vis[pathname].set_transform(transform)

        elif isinstance(geometry, Cylinder):
            cyl = geometry
            vis[pathname].set_object(g.Cylinder(cyl.length, cyl.radius), material)
            # meshcat cylinder is aligned along y-axis. Align along z then apply the
            # node's transform as normal.
            transform = np.copy(transform)
            # Change basic XYZ -> XZY
            transform[:, [1, 2]] = transform[:, [2, 1]]
            vis[pathname].set_transform(transform)

        elif isinstance(geometry, Mesh):
            obj = meshcat.geometry.StlMeshGeometry.from_stream(
                io.BytesIO(trimesh.exchange.stl.export_stl(geometry.trimesh))
            )
            vis[pathname].set_object(obj, material)
            vis[pathname].set_transform(transform)
        else:
            raise NotImplementedError(
                "Cannot yet add {} to visualiser".format(type(geometry))
            )

    def remove(self, scene):
        vis = self.vis
        vis.delete()

    def get_next_identifer(self):
        self.added_index += 1
        return "rays/{}".format(str(self.added_index))

    def add_line_segment(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        colour=0xFFFFFF,
    ) -> str:
        """ Add a line segment to the scene and return the identifier.
        
            Parameters
            ----------
            start : tuple
                The starting point of the line as (x, y, z) coordinates.
            end : tuple
                The ending point of the line as (x, y, z) coordinates.
            colour : int (optional)
                An optional colour specified as a hex integer. The default colour is
                white.

            Returns
            -------
            identifier : str
                The string identifier used to add the line to the scene.
        """
        vis = self.vis
        line = (start, end)
        self._will_add_expendable_to_scene(line)
        vertices = np.column_stack(line)
        assert vertices.shape[0] == 3  # easy to get this wrong
        identifier = self.get_next_identifer()
        vis[identifier].set_object(
            g.Line(
                g.PointsGeometry(vertices),
                g.MeshBasicMaterial(color=colour, transparency=False, opacity=1),
            )
        )
        self._did_add_expendable_to_scene(identifier)
        return identifier

    def add_path(
        self, vertices: Tuple[Tuple[float, float, float]], colour=0xFFFFFF
    ) -> str:
        """ Add a line to the scene and return the identifier. The line is made from 
            multiple line segments. The line will be drawn with a single colour.
        
            Parameters
            ----------
            vertices : tuple of tuple of float
                The starting point of the line as (x, y, z) coordinates.
            colour : int (optional)
                An optional colour specified as a hex integer. The default colour is
                white.

            See also
            --------
            add_ray_path : Draws the line using individual line segments. Use this 
            method when each line segment needs to be drawn with a different colour.
        
            Returns
            -------
            identifier : str
                The string identifier used to add the line to the scene.
        """
        vis = self.vis
        self._will_add_expendable_to_scene(vertices)
        vertices = np.array(vertices)
        assert vertices.shape[0] == 3  # easy to get this wrong
        identifier = self.get_next_identifer()
        vis[identifier].set_object(
            g.Line(
                g.PointsGeometry(vertices),
                g.MeshBasicMaterial(color=colour, transparency=False, opacity=1.0),
            )
        )
        self._did_add_expendable_to_scene(identifier)
        return identifier

    def add_ray(self, ray: Ray, length: float) -> str:
        """ Add the ray path as a single connected line and return an identifier. 
        
            Parameters
            ----------
            ray : Ray
                The ray to add to the scene.

            Notes
            -----
            Internally the line is drawn using `add_line_segment` because the colour of
            each segment could be unique. If this proves too inefficiency use 
            `add_path`.

            See also
            --------
            add_ray_path : Adds multiple rays to the scene.

            Returns
            -------
            identifier : str
                The string identifier used to add the object to the scene.
        """
        nanometers = ray.wavelength
        start = ray.position
        end = np.array(start) + np.array(ray.direction) * length
        colour = wavelength_to_hex_int(nanometers)
        identifier = self.add_line_segment(start, end, colour=colour)
        return identifier

    def add_ray_path(self, rays: [Ray]) -> str:
        """ Add the ray path as a single connected line and return an identifier. 
        
            Parameters
            ----------
            rays : list of Ray
                List of ray objects.
            length : float
                The length of the line to render. Default to 1000.

            See also
            --------
            add_path : Draws the line in more efficient way than `add_ray_path` but
                limits the line to be a single colour.

            Returns
            -------
            identifier : str
                The string identifier used to add the line to the scene.
        """
        vis = self.vis
        if len(rays) < 2:
            raise AppError("Need at least two points to render a line.")
        ids = []
        for (start_ray, end_ray) in zip(rays[:-1], rays[1:]):
            nanometers = start_ray.wavelength
            start = start_ray.position
            end = end_ray.position
            colour = wavelength_to_hex_int(nanometers)
            ids.append(self.add_line_segment(start, end, colour=colour))
        return ids

    def add_history(
        self,
        history: Tuple,
        baubles: bool = True,
        world_segment: str = "short",
        short_length: float = 1.0,
        bauble_radius: float = 0.01,
    ):
        """ Similar to `add_ray_path` but with improved visualisation options.
    
            Parameters
            ----------
            history: tuple
                Tuple of rays and events as returned from `photon_tracer.follow`
            baubles: bool (optional)
                Default is True. Draws baubles at exit location.
            world_segment: str (optional)
                Opt-out (`'exclude'`) or draw short (`'short`) path segments to the
                world node.
            short_length: float
                The length of the final path segment when `world_segment='short'`.
            bauble_radius: float
                The bauble radius when `baubles=True`.
        """
        vis = self.vis
        if not world_segment in {"exclude", "short"}:
            raise ValueError(
                "`world_segment` should be either `'exclude'` or `'short'`."
            )

        if world_segment == "exclude":
            rays, events = zip(*history)
            try:
                idx = events.index(Event.EXIT)
                history = history[0:idx]
                if len(history) < 2:
                    # nothing left to render
                    return
            except ValueError:
                pass

        if len(history) < 2:
            raise AppError("Need at least two points to render a line.")

        ids = []
        rays, events = zip(*history)
        for (start_part, end_part) in zip(history[:-1], history[1:]):
            start_ray, end_ray = start_part[0], end_part[0]
            nanometers = start_ray.wavelength
            start = start_ray.position
            end = end_ray.position
            if world_segment == "short":
                if end_ray == history[-1][0]:
                    end = (
                        np.array(start_ray.position)
                        + np.array(start_ray.direction) * short_length
                    )
            colour = wavelength_to_hex_int(nanometers)
            ids.append(self.add_line_segment(start, end, colour=colour))

            if baubles:
                event = start_part[1]
                if event in {Event.TRANSMIT}:
                    baubid = self.get_next_identifer()
                    vis[f"exit/{baubid}"].set_object(
                        g.Sphere(bauble_radius),
                        g.MeshBasicMaterial(
                            color=colour, transparency=False, opacity=1
                        ),
                    )
                    vis[f"exit/{baubid}"].set_transform(tf.translation_matrix(start))

                    ids.append(baubid)
        return ids

    def remove_object(self, identifier):
        """ Remove object by its identifier.
        """
        vis = self.vis
        vis[identifier].delete()

    def _will_add_expendable_to_scene(self, item):
        """ Private method used to notify buffer that a line or ray object will be
            added to the scene.
        
            Notes
            -----
            This is used to manage the buffer size and will remove the oldest object
            to keep the scene size constant.
        """
        if len(self.ray_histories) == self.max_histories:
            self.remove_object(self.ray_histories.popleft())

    def _did_add_expendable_to_scene(self, identifier):
        """ Private method use to notify the buffer that an expendable object has been
            added to the scene. 
        
            Notes
            -----
            The identifier is used to remove the object when it is becomes the oldest
            item in the buffer.
        """
        self.ray_histories.append(identifier)
