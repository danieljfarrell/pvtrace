# pvtrace is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# 
# pvtrace is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division
import numpy as np
import multiprocessing
from multiprocessing import Pool
cpu_count=multiprocessing.cpu_count()
from Geometry import *
from ConstructiveGeometry import *
from Materials import *
from Devices import *
from Visualise import Visualiser
import visual
from itertools import ifilter
import subprocess
import os
import external.pov
import sys
import PhotonDatabase
import external.transformations as tf
import pdb
from copy import copy
import logging

def remove_duplicates(the_list):
    l = list(the_list)
    return [x for x in l if l.count(x)==1]


class Photon (object):
    '''A generic photon class.'''
    
    def __init__(self, wavelength=555, position=[.0,.0,.0], direction=[.0,.0,1.], active=True, show_log=True):
        ''' 
        All arguments are optional because a photon is greated with default values. The possible arguments are:
        wavelength -- The photon wavelength in nanometers (float).
        position   -- The photon position in cartesian coordinates (3 elements) is array-like quantity in units of metres.
        direction  -- The photon Cartesian direction vector (3 elements), a normalised vector is array-like.
        phase      -- This is not yet implemented.
        active   -- Boolean indicating if the ray has or has not been lost (e.g. absorbed in a material)
        container  -- The geometrical object within which the ray is located.
        '''
        
        self.wavelength = wavelength
        self.ray = Ray(np.array(position), np.array(direction))
        self.active  = active
        self.killed = False
        self.container  = None
        self.exit_material = None
        self.exit_device = None
        self.__direction = self.ray.direction
        self.__position = self.ray.position
        self.scene = None
        self.propagate = False
        self.visualiser = None
        self.polarisation = None
        self.show_log = show_log
        self.reabs = 0
        self.id = 0
        self.source = None
        self.absorption_counter = 0
        self.intersection_counter = 0
        
        
    def __copy__(self):
        copy = Photon()
        copy.wavelength = self.wavelength
        copy.ray = Ray(direction=self.direction, position=self.position)
        copy.active = self.active
        copy.container = self.container
        copy.exit_material = self.exit_material
        copy.exit_device = self.exit_device
        copy.scene = self.scene
        copy.propagate = self.propagate
        copy.visualiser = self.visualiser
        copy.absorption_counter = self.absorption_counter
        copy.intersection_counter = self.intersection_counter
        return copy
    
    def __deepcopy__(self):
        return copy(self)
        
    def __str__(self):
        info = str(self.wavelength) + "nm " + str(self.ray.position) + " " + str(self.ray.direction) + " " + str(type(self.container))
        if self.active:
            info = info + " active "
        else:
            info = info + " inactive "
        return info
        
    def getPosition(self):
        """Returns the position of the photons rays"""
        return self.ray.position
        
    def getDirection(self):
        """Returns the direction of the photons rays"""
        return self.ray.direction
        
    def setPosition(self, position):
        self.ray.position = position
        # Define setter and getters as properties
    position = property(getPosition, setPosition)
        
    def setDirection(self, direction):
        self.ray.direction = direction
    direction = property(getDirection, setDirection)
     
    def trace(self):
        """The ray can trace its self through the scene."""

                
        assert self.scene != None, "The photon's scene variable is not set."
        
        intersection_points, intersection_objects = self.scene.intersection(self.ray)

        """
        #DIAGNOSTICS
        print "\nnew\n"
        print self.position, self.direction, "\n"
        print intersection_points, "\n"
        for i in range(0, len(intersection_objects)):
            print "Object: ", intersection_objects[i].name, " - Intersection: ", intersection_points[i]
        """
        
        assert intersection_points != None, "The ray must intersect with something in the scene to be traced."
        
        if self.container is None:
            self.container = self.scene.container(self)
        assert self.container != None, "Container of ray cannot be found."
            
        #import pdb; pdb.set_trace()
        #import pudb; pudb.set_trace()
        intersection_points, intersection_objects = Scene.sort(intersection_points, intersection_objects, self, container=self.container, show_log=self.show_log)
                        
        # find current intersection point and object -- should be zero if the list is sorted!
        intersection = closest_point(self.position, intersection_points)
        for i in range(0,len(intersection_points)):
            if list(intersection_points[i]) == list(intersection):
                index = i
                break
            
        #import pdb; pdb.set_trace()
        intersection_object = intersection_objects[index]
        assert intersection_object != None, "No intersection points can be found with the scene."
        
        
        """
        #DIAGNOSTICS
        print "\n", intersection, "\n"
        print intersection_object.name   
        """     
        
        
        # Reached scene boundaries?
        if intersection_object is self.scene.bounds:
            self.active = False
            self.previous_container = self.container
            self.container = self.scene.bounds
            return self


        # Reached a RayBin (kind of perfect absorber)?
        if isinstance(intersection_object, RayBin):
            self.active = False
            self.previous_container = self.container
            self.container = self.scene.bounds
            return self
        
        
        # Here we trace the ray through a Coating
        if isinstance(self.container, Coating):
            normal = intersection_object.shape.surface_normal(self.ray)
            self = self.container.material.trace(self, normal, separation(self.position, intersection))
            self.exit_device = self.container
            self.previous_container = self.container
            self.container = self.scene.container(self)
            return self
        
        
        # Here we determine if the Coating has been hit
        if isinstance(intersection_object, Coating) and intersection_object.shape.on_surface(self.position):
            self.previous_container = self.container
            self.container = intersection_object
            self.exit_device = intersection_object
            assert self.exit_device != self.scene.bounds, "The object the ray hit before hitting the bounds is the bounds, this can't be right."
            return self
        
        
        # Here we trace the ray through a Material
        self = self.container.material.trace(self, separation(self.position, intersection))
        
        
        # Lost in material?
        # Photon has been re-absorbed but NOT re-emitted, i.e. is inactive
        if not self.active:
            #01/04/10: Unification --> Next two lines came from older Trace version
            self.exit_device = self.container
            self.exit_material = self.container.material
            return self        
                
        # Reaches interface
        # Photon has been re-absorbed AND re-emitted, i.e. is still active
        ray_on_surface = intersection_object.shape.on_surface(self.position)
        if not ray_on_surface:            
            self.exit_device = self.container
            return self
            
        # Ray has reached a surface of some description, increment the intersection counter
        self.intersection_counter += 1
        
        # If we reach an reflective material then we don't need to follow 
        # this logic we can just return
        if ray_on_surface and isinstance(intersection_object, Coating):
            self.previous_container = self.container
            self.container = intersection_object
            self.exit_device = intersection_object
            return self
        
        # KARLG NEW CODE HERE
        #import pudb; pudb.set_trace()
        if isinstance(intersection_object, Face):
            self.exit_device = intersection_object
            
            # Now change the properties of the photon accoring to what your surface does
            random_number = np.random.random_sample()
            if random_number < intersection_object.reflectivity:
                # Reflected
                self.direction = reflect_vector(intersection_object.shape.surface_normal(self.ray), self.direction)
            elif random_number < intersection_object.reflectivity + intersection_object.transmittance:
                # Transmitted
                pass
            else:
                # Loss
                self.active = False
            return self
            
        # Fresnel details
        normal = intersection_object.shape.surface_normal(self.ray)
        rads = angle(normal, self.direction)
        
        # material-air or material-material interface
        # Are there duplicates intersection_points that are equal to the ray position?
        same_pt_indices = []
        for i in range(0,len(intersection_points)):
            if cmp_points(self.position, intersection_points[i]):
                same_pt_indices.append(i)
        assert len(same_pt_indices) < 3, "An interface can only have 2 or 0 common intersection points."
        
        initialised_internally = None
        
        if len(same_pt_indices) == 2:
            intersection_object = self.container
        
        if self.container == intersection_object:
            
            # hitting internal interface -- for the case we are at an material-material interface (i.e. not travelling through air)
            initialised_internally = True
            
            if len(same_pt_indices) == 2:
                
                for obj in intersection_objects:
                    if obj.shape.on_surface(intersection) and obj != self.container:
                    #if obj != self.container:
                        next_containing_object = obj
                        
                
            else:
                # hitting internal interface -- for the case we are not at an interface
                next_containing_object = self.scene.container(self)
            
            assert self.container != next_containing_object, "The current container cannot also be the next containing object after the ray is propagated."
            
            # Fresnel details
            normal = intersection_object.shape.surface_normal(self.ray)
            rads = angle(normal, self.direction)
            if self.polarisation == None:
                reflection = fresnel_reflection(rads, self.container.material.refractive_index, next_containing_object.material.refractive_index)
            else:
                reflection = fresnel_reflection_with_polarisation(normal, self.direction, self.polarisation, self.container.material.refractive_index, next_containing_object.material.refractive_index)
            
        else:
            # hitting external interface
            initialised_internally = False           
            
                        
            if len(same_pt_indices) == 2:
                for obj in intersection_objects:
                    if obj != self.container:
                        intersection_object = obj
                        next_containing_object = obj
            else:
                next_containing_object = intersection_object
            
            #import pdb; pdb.set_trace()
            normal = intersection_object.shape.surface_normal(self.ray)
            rads = angle(normal, self.direction)
            if self.polarisation == None:
                reflection = fresnel_reflection(rads, self.container.material.refractive_index, next_containing_object.material.refractive_index)
            else:
                reflection = fresnel_reflection_with_polarisation(normal, self.direction, self.polarisation, self.container.material.refractive_index, next_containing_object.material.refractive_index)
                
        if isinstance(next_containing_object, Collector):
            # If the photon hits an interface with e.g. a cell index-matched to it, then no reflection is to occur at this interface.
            reflection = 0.
        
        if np.random.random_sample() < reflection:
            # photon is reflected
            before = copy(self.direction)
            self.direction = reflect_vector(normal, self.direction)
            ang = angle(before, self.direction)
            
            if self.polarisation != None:
                    
                #import pdb; pdb.set_trace()
                if cmp_floats(ang, np.pi):
                    # Anti-parallel
                    self.polarisation = self.polarisation
                else:
                    # apply the rotation transformation the photon polarisation which aligns the before and after directions
                    R = rotation_matrix_from_vector_alignment(before, self.direction)
                    self.polarisation = transform_direction(self.polarisation, R)
                    
                assert cmp_floats(angle(self.direction, self.polarisation), np.pi/2), "Exit Pt. #1: Angle between photon direction and polarisation must be 90 degrees: theta=%s" % str(np.degrees(angle(self.direction, self.polarisation)))
            
            self.propagate = False
            self.exit_device = self.container
            
            # invert polaristaion if n1 < n2
            if self.container.material.refractive_index < next_containing_object.material.refractive_index:
                
                if self.polarisation != None:
                    
                    if cmp_floats(ang, np.pi):
                        # Anti-parallel
                        self.polarisation = self.polarisation * -1.
                    else:
                        # apply the rotation transformation the photon polarisation which aligns the before and after directions
                        R = rotation_matrix_from_vector_alignment(before, self.direction)
                        self.polarisation = transform_direction(self.polarisation, R)
                    
                    assert cmp_floats(angle(self.direction, self.polarisation), np.pi/2), "Exit Pt. #2: Angle between photon direction and polarisation must be 90 degrees: theta=%s" % str(angle(self.direction, self.polarisation))
                    
            if self.exit_device == self.scene.bounds or self.exit_device == None:
                self.exit_device = intersection_object
            assert self.exit_device != self.scene.bounds, "The object the ray hit before hitting the bounds is the bounds, this can't be right"
            return self
        else:
            # photon is refracted through interface
            self.propagate = True
            before = copy(self.direction)
            ang = angle(before, self.direction)
            if initialised_internally:
                if not isinstance(next_containing_object, Collector):
                    self.direction = fresnel_refraction(normal, self.direction, self.container.material.refractive_index, next_containing_object.material.refractive_index )
                    
                    if self.polarisation != None:
                        if cmp_floats(ang, np.pi):
                            # Anti-parallel
                            self.polarisation = self.polarisation
                        else:
                            # apply the rotation transformation the photon polarisation which aligns the before and after directions
                            R = rotation_matrix_from_vector_alignment(before, self.direction)
                            self.polarisation = transform_direction(self.polarisation, R)
                        assert cmp_floats(angle(self.direction, self.polarisation), np.pi/2), "Exit Pt. #3: Angle between photon direction and polarisation must be 90 degrees: theta=%s" % str(angle(self.direction, self.polarisation))
                        
                self.exit_device = self.container #LSC is the exit_device
                self.previous_container = self.container
                self.container = next_containing_object #Bounds is the container
                return self
            else:
                if not isinstance(next_containing_object, Collector):
                    self.direction = fresnel_refraction(normal, self.direction, self.container.material.refractive_index, intersection_object.material.refractive_index )
                    
                    if self.polarisation != None:
                        
                        if cmp_floats(ang, np.pi):
                            # Anti-parallel
                            self.polarisation = self.polarisation
                        else:
                        # apply the rotation transformation the photon polarisation which aligns the before and after directions
                            R = rotation_matrix_from_vector_alignment(before, self.direction)
                            self.polarisation = transform_direction(self.polarisation, R)
                            # apply the rotation transformation the photon polarisation which aligns the before and after directions

                        assert cmp_floats(angle(self.direction, self.polarisation), np.pi/2), "Exit Pt. #4: Angle between photon direction and polarisation must be 90 degrees: theta=%s" % str(angle(self.direction, self.polarisation))
                    
                # DJF 13.5.2010: This was crashing the statisical collection because it meant that an incident ray, hitting and transmitted, then lost would have bounds as the exit_device.
                #self.exit_device = self.container
                self.exit_device = intersection_object
                self.previous_container = self.container
                self.container = intersection_object
                return self
                

def povObj(obj, colour = None):
   print type(obj)
   try:
       T = obj.transform
       white = pov.Texture(pov.Pigment(color="White", transmit = 0.5)) if colour == None else colour
       M = "< %s >"%(", ".join(str(T[:3].transpose().flatten())[1:-1].replace("\n","").split()))    
   except:
       pass


   if type(obj) == Cylinder:
       return pov.Cylinder((0,0,0), (0,0, obj.length), obj.radius, white, matrix = M)
   if type(obj) == Box:
       return pov.Box(tuple(obj.origin), tuple(obj.extent), white, matrix = M)
   if type(obj) == Coating:
       return povObj(obj.shape)
   if type(obj) == LSC:
       maxindex = obj.material.emission.y.argmax()
       wavelength = obj.material.emission.x[maxindex]
       colour = wav2RGB(wavelength)
       print colour
       colour = pov.Pigment(color=(colour[0]/255,colour[1]/255,colour[2]/255))
       print "found lsc"
       return povObj(obj.shape, colour = colour)
   if type(obj) == Plane:
       return pov.Plane((0,0,1), 0, white, matrix = M)
   if type(obj) == FinitePlane:
       return pov.Box((0,0,0), (obj.length, obj.width, 0), white, matrix = M)
   if type(obj) == CSGsub:
       return pov.Difference(povObj(obj.SUBplus), povObj(obj.SUBminus))
   if type(obj) == CSGadd:
       return pov.Union(povObj(obj.ADDone), povObj(obj.ADDtwo))
   if type(obj) == CSGint:
       return pov.Intersection(povObj(obj.INTone), povObj(obj.INTtwo))




class Scene(object):
    """A collection of objects. All intersection points can be found or a ray can be traced through."""
    
    def pov_render(self, camera_position = (0,0,-10), camera_target = (0,0,0)):
        """Pov thing
        >>> S = Scene()
        >>> L, W, D = 1, 1, 1
        >>> box = Box(origin=(-L/2., -W/2.,-D/2.), extent=(L/2, W/2, D/2))
        >>> myCylinder = Cylinder(radius = 1)
        >>> #myCylinder.append_transform(tf.translation_matrix((0,-1,0)))
        >>> box.append_transform(tf.rotation_matrix(-np.pi/3,(0,1,0), point=(0,0,0)))
        >>> #S.add_object(CSGsub(myCylinder, box))
        >>> myPlane = FinitePlane()
        >>> #myPlane.append_transform(tf.translation_matrix((0,0,9.9)))
        >>> S.add_object(myPlane)
        >>> #S.add_object(box)
        >>> #S.add_object(myCylinder)
        >>> S.pov_render()
        """

        """
        f=pov.File("demo.pov","colors.inc","stones.inc")
        
        cam = pov.Camera(location=camera_position, sky=(1,0,1),look_at=camera_target)
        light = pov.LightSource( camera_position, color="White")
        
        povObjs = [cam, light]
        for obj in self.objects[1:]:
            # test coordinate transfroms
            # print M
            # vectors = np.array([[0,0,0,1], #origin
            #                     [1,0,0,1], # x
            #                     [0,1,0,1], # y
            #                     [0,0,1,1]]).transpose() # z
            # origin,x,y,z = (T*vectors).transpose()
            povObjs.append(povObj(obj))
        
        #print tuple(povObjs)
        f.write(*tuple(povObjs))
        f.close()
        #sphere1 = pov.Sphere( (1,1,2), 2, pov.Texture(pov.Pigment(color="Yellow")))
        #sphere2 = pov.Sphere( (0,1,2), 2, pov.Texture(pov.Pigment(color="Yellow")))
        # composite2 = None#pov.Difference(sphere1, sphere2)
        # 
        
        
        
        
        
        # f.write( cam, composite2, light )
        # f.close()
        subprocess.call("povray +H2400 +W3200 demo.pov", shell=True)
        os.system("open demo.png")
        """
        
    def __init__(self):
        super(Scene, self).__init__()
        self.bounds = Bounds()
        self.objects  = [self.bounds]
        
    def add_object(self, object):
        self.objects.append(object)
    
    def intersection(self, ray):
        """Returns a ray of intersection points and associated objects in no particular order."""
        
        points = []
        intersection_objects = []
        for obj in self.objects:
            intersection = obj.shape.intersection(ray)
            if intersection != None:
                for pt in intersection:
                    points.append(pt)
                    intersection_objects.append(obj)
        
        if len(points) == 0:
            return None, None
        return points, intersection_objects
    
    def sort(points, objects, ray, container=None, remove_ray_intersection=True, show_log=False):
        """
        Returns points and objects sorted by separation from the ray position.
        
        points : a list of intersection points as returned by scene.intersection(ray)
        objects : a list of objects as returned by scene.intersection(ray)
        ray : a ray with global coordinate frame
        remove_ray_intersection=True  (optional): if the ray is on an intersection points remove this point from both lists
        """
        
        # filter arrays for intersection points that are ahead of the ray's direction
        # also if the ray is on an intersection already remove it (optional)
        for i in range(0,len(points)):
            
            if remove_ray_intersection:
                if ray.ray.behind(points[i]) or cmp_points(ray.position, points[i]):
                    points[i] = None
                    objects[i] = None
            else:
                if ray.ray.behind(points[i]):
                    points[i] = None
                    objects[i] = None
        
        objects = filter(None, objects)
        points_copy = list(points)
        points = []
        
        for i in range(0,len(points_copy)):
            if points_copy[i] != None:
                points.append(points_copy[i])
            
        assert len(points) > 0, "No intersection points can be found with the scene."
        
        #import pdb; pdb.set_trace()
        # sort the intersection points arrays by separation from the ray's position
        separations = []
        for point in points:
            separations.append(separation(ray.position, point))
        sorted_indices = np.argsort(separations)
        separations.sort()
        
        # Sort accoring to sort_indices array
        points_copy = list(points)
        objects_copy = list(objects)
        for i in range(0,len(points)):
            points[i] = points_copy[sorted_indices[i]]
            objects[i] = objects_copy[sorted_indices[i]]
        del points_copy
        del objects_copy
        
        if show_log:
            print objects
            print points
        
        objects, points, separations = Scene.order_duplicates(objects, points, separations)
        
        # Now perform container check on ordered duplicates
        if container != None:
            if objects[0] != container and len(objects)>1:
                
                # The first object in the array must be the container so there is an order problem -- assumes container object is an index 1!
                obj = objects[1]
                objects[1] = objects[0]
                objects[0] = obj
                
                obj = points[1]
                points[1] = points[0]
                points[0] = obj
                
                obj = points[1]
                separations[1] = separations[0]
                separations[0] = obj
                
                trim_objs, trim_pts, trim_sep = Scene.order_duplicates(objects[1::], points[1::], separations[1::])
                objects[1::] = trim_objs
                points[1::] = trim_pts
                separations[1::] = trim_sep
                
        return points, objects
    
    sort = staticmethod(sort)
    
    def order_duplicates(objects, points, separations):
        """Subroutine which might be called recursively by the sort fuction when the first element 
        of the objects array is no the container objects after sorting."""
            
        # If two intersections occur at the same points then the 
        # sort order won't always be correct. We need to sort by
        # noticing the order of the points that could be sorted.
        # (e.g.) a thin-film from air could give [a {b a} b], this pattern, we know the first point is correct.
        # (e.g.) a thin-film from thin-film could give [{b a} b c], this pattern,  we know the middle is point correct.
        # (e.g.) another possible example when using CGS objects [a b {c b} d].
        # (e.g.) [a {b a} b c] --> [a a b b c]
        # (e.g.) need to make the sort algo always return [a a b b] or [a b b c].
        # Find indices of same-separation points
        #import pdb; pdb.set_trace()
        
        if (len(objects)) > 2:
            common = []
            for i in range(0, len(separations)-1):
                if cmp_floats(separations[i], separations[i+1]):
                    common.append(i)
            
            # If the order is incorrect then we swap two elements (as described above)
            for index in common:
                
                if not (objects[index+1] == objects[index+2]):
                    
                    # We have either [{b a} b c], or [{a b} b c]
                    obj = objects[index+1]
                    objects[index+1] = objects[index]
                    objects[index] = obj
                    
                    obj = points[index+1]
                    points[index+1] = points[index]
                    points[index] = obj
                    
                    obj = separations[index+1]
                    separations[index+1] = separations[index]
                    separations[index] = obj
                    
        return objects, points, separations
    
    order_duplicates = staticmethod(order_duplicates)
    
    def container(self, photon):
        '''Returns the inner most object that contains the photon.'''
        
        
        # Ask each object if it contains the photon, if multiple object say yes we filter by separation to find the inner container.
        containers = []
        for obj in self.objects:
           if obj.shape.contains(photon.position):
               containers.append(obj)
           
        if len(containers) == 0:
           raise ValueError("The photon is not located inside the scene bounding box.")
        elif len(containers) == 1:
           return containers[0]
        else:
            # We cast the ray forward and make intersections with the possible containers, the inner container has the closest intersection point
            separations = []
            for obj in containers:
                intersection_point = obj.shape.intersection(photon)
                assert len(intersection_point) == 1, "A primative containing object can only have one intersection point with a line when the origin of the test ray is contained by the object."
                separations.append(separation(photon.position, intersection_point[0]))
            min_index = np.array(separations).argmin()
            return containers[min_index]

class Tracer(object):
    """An object that will fire multiple photons through the scene."""
    def __init__(self, scene=None, source=None, throws=1, steps=50, seed=None, use_visualiser=True, show_log=True, background=(0.957, 0.957, 1), ambient=0.5):
        super(Tracer, self).__init__()
        self.scene = scene
        from LightSources import SimpleSource, PlanarSource, CylindricalSource, PointSource, RadialSource
        self.source = source
        self.throws = throws
        self.steps = steps
        self.totalsteps = 0
        self.seed = seed
        self.killed = 0
        self.database = PhotonDatabase.PhotonDatabase()
        self.stats = dict()
        self.show_log = show_log
        np.random.seed(self.seed)
        if not use_visualiser:
            Visualiser.VISUALISER_ON = False
        else:
            Visualiser.VISUALISER_ON = True
        self.visualiser = Visualiser(background=background, ambient=ambient)
        
        for obj in scene.objects:
            if obj != scene.bounds:
                if not isinstance(obj.shape, CSGadd) and not isinstance(obj.shape, CSGint) and not isinstance(obj.shape, CSGsub):
                
                    if isinstance(obj.material, SimpleMaterial):
                        wavelength = obj.material.bandgap
                    else:
                        
                        if not hasattr(obj.material, 'all_absorption_coefficients'):
                            maxindex = obj.material.emission_data.y.argmax()
                            wavelength = obj.material.emission_data.x[maxindex]
                            colour = wav2RGB(wavelength)
                        else:
                            # It is possible to processes the most likley colour of a spectrum in a better way than this!
                            colour = [0.1,0.1,0.1]
                        
                        if colour[0] == np.nan or colour[1] == np.nan or colour[2] == np.nan:
                            colour = [0.1,0.1,0.1]
                        
                        self.visualiser.addObject(obj.shape, colour=colour)
                        
        self.show_lines = True#False
        self.show_exit = True
        self.show_path = True#False
        self.show_start = True
        
        
    def start(self):
        
        logged = 0
        
        for throw in range(0, self.throws):
            
            # Delete last ray from visualiser
            if Visualiser.VISUALISER_ON:
                for obj in self.visualiser.display.objects:
                    if obj.__class__ is visual.cylinder: # can say either box or 'box'
                        if obj.radius < 0.001:
                            obj.visible = False
                
            if self.show_log:
                print "Photon number:", throw
            else:
                print "Photon number:", throw, "\r",
                sys.stdout.flush()
            
            photon = self.source.photon()
            photon.visualiser = self.visualiser
            photon.scene = self.scene
            photon.material = self.source
            photon.show_log = self.show_log
            
            a = list(photon.position)
            if self.show_start:
                self.visualiser.addSmallSphere(a)
            
            step = 0
            while photon.active and step < self.steps:
                
                if photon.exit_device is not None:
                    
                    # The exit
                    if photon.exit_device.shape.on_surface(photon.position):
                        
                        # Is the ray heading towards or out of a surface?
                        normal = photon.exit_device.shape.surface_normal(photon.ray, acute=False)
                        rads = angle(normal, photon.ray.direction)
                        #print photon.exit_device.shape.surface_identifier(photon.position), 'normal', normal, 'ray dir', photon.direction, 'angle' , np.degrees(rads)
                        if rads < np.pi/2:
                            bound = "Out"
                            #print "OUT"
                        else:
                            bound = "In"
                            #print "IN"
                        
                        self.database.log(photon, surface_normal=photon.exit_device.shape.surface_normal(photon), surface_id=photon.exit_device.shape.surface_identifier(photon.position), ray_direction_bound=bound)
                        
                else:
                    self.database.log(photon)
                
                #import pdb; pdb.set_trace()
                wavelength = photon.wavelength
                #photon.visualiser.addPhoton(photon)
                photon = photon.trace()
                
                if step == 0:
                    # The ray has hit the first object. 
                    # Cache this for later use. If the ray is not 
                    # killed then log data.
                    #import pdb; pdb.set_trace()
                    entering_photon = copy(photon)
                
                #print "Step number:", step
                b = list(photon.position)                
                
                if self.show_lines and photon.active == True:
                    self.visualiser.addLine(a,b, colour=wav2RGB(photon.wavelength))
                
                if self.show_path and photon.active == True:
                    self.visualiser.addSmallSphere(b)
                
                #import pdb; pdb.set_trace()
                
                if photon.active == False and photon.container == self.scene.bounds:
                    
                    if self.show_exit:
                        self.visualiser.addSmallSphere(a, colour=[.33,.33,.33])
                        self.visualiser.addLine(a, a + 0.01*photon.direction, colour=wav2RGB(wavelength))
                    
                    # Record photon that has made it to the bounds
                    if step == 0:
                        if self.show_log: print "   * Photon hit scene bounds without previous intersections *"
                    else:
                        if self.show_log: print "   * Reached Bounds *"
                        photon.exit_device.log(photon)
                        #self.database.log(photon)
                        
                    #entering_photon.exit_device.log(entering_photon)
                    #assert logged == throw, "Logged (%s) and thorw (%s) not equal" % (str(logged), str(throw))
                    logged = logged + 1
                    
                elif photon.active == False:                    
                    #print photon.exit_device.name
                    photon.exit_device = photon.container
                    photon.container.log(photon)
                    self.database.log(photon)
                    if entering_photon.container == photon.scene.bounds:
                        if self.show_log: print "   * Photon hit scene bounds without previous intersections *"
                    else:
                        #try:
                        entering_photon.container.log(entering_photon)
                        #self.database.log(photon)
                        #except:
                        #    entering_photon.container.log_in_volume(entering_photon)
                    #assert logged == throw, "Logged (%s) and thorw (%s) not equal" % (str(logged), str(throw))
                    logged = logged + 1
                
                
                a = b
                step = step + 1
                self.totalsteps = self.totalsteps + 1
                if step >= self.steps:
                    # We need to kill the photon because it is bouncing around in a locked path
                    self.killed = self.killed + 1
                    photon.killed = True
                    self.database.log(photon)
                    if self.show_log: 
                        print "   * Reached Max Steps *"


if __name__ == "__main__":
    import doctest
    doctest.testmod()

