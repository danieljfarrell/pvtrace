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

from  __future__ import division
import numpy as np
import scipy as sp
import scipy.linalg
from external.transformations import translation_matrix, rotation_matrix
import external.transformations as tf
from external.quickhull import qhull3d
import logging
import pdb

#logging.basicConfig(filename="/tmp/geom-debug.txt", level=logging.DEBUG, filemode="w")

def cmp_floats(a,b):
    abs_diff = abs(a-b)
    if abs_diff < 1e-12:
        return True
    else:
        return False

def cmp_floats_range(a,b):
    if cmp_floats(a,b):
        return 0
    elif a < b:
        return -1
    else:
        return 1

def intervalcheck(a,b,c):
    """
    Returns whether a <= b <= c is True or False
    """
    if cmp_floats(a,b) == True or cmp_floats(b,c) == True:
        return True
    if a<b and b<c:
        return True
    else:
        return False

def intervalcheckstrict(a,b,c):
    """
    Returns whether a < b < c is True or False
    """
    if a<b and b<c:
        return True
    else:
        return False

def smallerequalto(a,b):
    """
    Returns whether a<=b is True or False
    """
    if cmp_floats(a,b) == True:
        return True
    if a<b:
        return True
    else:
        return False

def round_zero_elements(point):
    for i in range(0,len(point)):
        if cmp_floats(0.0, point[i]):
            point[i] = 0.0
    return point

def cmp_points(a,b):
    if a is None:
        return False
    if b is None:
        return False
    
    al = list(a)
    bl = list(b)
    for e1, e2 in zip(al, bl):
        ans = cmp_floats(e1,e2)
        if ans is False:
            return False
    return True

def flatten(l, ltypes=(list, tuple)):
    ltype = type(l)
    l = list(l)
    i = 0
    while i < len(l):
        while isinstance(l[i], ltypes):
            if not l[i]:
                l.pop(i)
                i -= 1
                break
            else:
                l[i:i + 1] = l[i]
        i += 1
    return ltype(l)
            
def separation(beginning, end):
   return magnitude(np.array(end)-np.array(beginning))

def magnitude(vector):
   return np.sqrt(np.dot(np.array(vector),np.array(vector)))

def norm(vector):
   return np.array(vector)/magnitude(np.array(vector))

def angle(normal, vector):
    assert cmp_floats(magnitude(normal), 1.0), "The normal vector is not normalised."
    dot = np.dot(normal, vector)
    return np.arccos(dot / magnitude(vector))

def reflect_vector(normal, vector):
    d = np.dot(normal, vector)
    return vector - 2 * d * normal

def closest_point(reference, point_list):
    """Return the closest point in the list of reference points."""
    separations = []
    for point in point_list:
        t = separation(reference, point)
        separations.append(t)
    sort_index = np.array(separations).argsort()
    return point_list[sort_index[0]]
    
def transform_point(point, transform):
    return np.array(np.dot(transform, np.matrix(np.concatenate((point, [1.]))).transpose()).transpose()[0,0:3]).squeeze()
    
def transform_direction(direction, transform):
    angle, axis, point = tf.rotation_from_matrix(transform)
    rotation_transform = tf.rotation_matrix(angle, axis)
    return np.array(np.dot(rotation_transform, np.matrix(np.concatenate((direction, [1.]))).transpose()).transpose()[0,0:3]).squeeze()

def rotation_matrix_from_vector_alignment(before, after):
    """
    >>> # General input/output test
    >>> V1 = norm(np.random.random(3))
    >>> V2 = norm([1,1,1])
    >>> R = rotation_matrix_from_vector_alignment(V1, V2)
    >>> V3 = transform_direction(V1, R)
    >>> cmp_points(V2, V3)
    True
    >>> # Catch the special case in which we cannot take the cross product
    >>> V1 = [0,0,1]
    >>> V2 = [0,0,-1]
    >>> R = rotation_matrix_from_vector_alignment(V1, V2)
    >>> V3 = transform_direction(V1, R)
    >>> cmp_points(V2, V3)
    True
    """
    # The angle between the vectors must not be 0 or 180 (i.e. so we can take a cross product)
    thedot = np.dot(before, after)
    if cmp_floats(thedot, 1.) == True:
        # Vectors are parallel
        return tf.identity_matrix()
        
    if cmp_floats(thedot, -1.) == True:
        # Vectors are anti-parallel
        print "Vectors are anti-parallel this might crash."
        
    axis = np.cross(before, after)            # get the axis of rotation
    angle = np.arccos(np.dot(before, after))  # get the rotation angle
    return rotation_matrix(angle, axis)
    

class Ray(object):
    """A ray in the global cartesian frame."""
    def __init__(self, position=[0.,0.,0.], direction=[0.,0.,1.]):
        self.__position = np.array(position)
        self.__direction = np.array(direction)/np.sqrt(np.dot(direction,np.array(direction).conj()))
    
    def getPosition(self):
        return self.__position
    
    def setPosition(self, position):
        self.__position = round_zero_elements(position)
        
    def getDirection(self):
        return self.__direction
       
    def setDirection(self, direction):
        self.__direction = np.array(direction)/np.sqrt(np.dot(direction,np.array(direction).conj()))
    
    def stepForward(self, distance):
        self.position = self.position + distance * self.direction
    
    def behind(self, point):
        # Create vector from position to point, if the angle is 
        # greater than 90 degrees then the point is behind the ray.
        v = np.array(point) - np.array(self.position)
        if cmp_points([0,0,0], v):
            # The ray is at the point
            return False
        if angle(self.direction, v) > np.pi*.5:
            return True
        return False
        
    # Define properties
    direction = property(getDirection, setDirection)
    position = property(getPosition, setPosition)

class Intersection(object):
    """Defines the intersection between a ray and a geometrical objects."""
    def __init__(self, ray, point, receiver):
        """An intersection is defined as the point that a ray and receiver meet. This class is simiply a wapper for these deatils. Intersection objects can be sorted with respect to their separations (distance from the ray.position to the point of intersection), this length is returned with intersection_obj.separation."""
        super(Intersection, self).__init__()
        self.ray = ray
        self.point = point
        self.receiver = receiver
        self.separation = separation(point, ray.position)
        
    def __str__(self):
        return str(' point ' + str(self.point) + ' receiver ' +  str(self.receiver))
        
    def __cmp__(self, other):
       return cmp(self.separation, other.separation)


class Plane(object):
    """A infinite plane going though the origin point along the positive z axis. At 4x4 transformation matrix can be applied to the generated other planes."""
    def __init__(self, transform=None):
        '''Transform is a 4x4 transformation matrix that rotates and translates the plane into the global frame (a plane in the xy plane point with normal along (+ve) z).'''
        super(Plane, self).__init__()
        
        self.transform = transform
        if self.transform == None:
            self.transform = tf.identity_matrix()
    
    def append_transform(self, new_transform):
        self.transform = np.dot(self.transform, new_transform)
    
    def contains(self, point):
        return False
    
    def on_surface(self, point):
        """Returns True is the point is on the plane's surface and false otherwise."""
        inv_transform = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, inv_transform)
        if cmp_floats(rpos, 0.):
            return True
        return False
    
    def surface_identifier(self, surface_point, assert_on_surface = True):
        raise 'planarsurf'
    
    def surface_normal(self, ray, acute=True):
        normal = transform_direction((0,0,1), self.transform)
        if acute:
            if angle(normal, rdir) > np.pi/2:
                normal = normal * -1.0
        return normal
    
    def intersection(self, ray):
        """
        Returns the intersection point of the ray with the plane. If no intersection occurs None is returned.
        
        >>> ray = Ray(position=[0.5, 0.5, -0.5], direction=[0,0,1])
        >>> plane = Plane()
        >>> plane.intersection(ray)
        [array([ 0.5,  0.5,  0. ])]
        
        >>> ray = Ray(position=[0.5, 0.5, -0.5], direction=[0,0,1])
        >>> plane = Plane()
        >>> plane.transform = tf.translation_matrix([0,0,1])
        >>> plane.intersection(ray)
        [array([ 0.5,  0.5,  1. ])]
        
        >>> ray = Ray(position=[0.5, 0.5, -0.5], direction=[0,0,1])
        >>> plane = Plane()
        >>> plane.append_transform(tf.translation_matrix([0,0,1]))
        >>> plane.append_transform(tf.rotation_matrix(np.pi,[1,0,0]))
        >>> plane.intersection(ray)
        [array([ 0.5,  0.5,  1. ])]
        
        """
         # We need apply the anti-transform of the plane to the ray. This gets the ray in the local frame of the plane.
        inv_transform = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, inv_transform)
        rdir = transform_direction(ray.direction, inv_transform)
        
        # Ray is in parallel to the plane -- there is no intersection
        if rdir[2] == 0.0:
            return None
        t = -rpos[2]/rdir[2]
        
        # Intersection point is behind the ray
        if t < 0.0:
            return None
        
        # Convert local frame to world frame
        point = rpos + t*rdir
        return [transform_point(point, self.transform)]


class FinitePlane(Plane):
    """A subclass of Plane but that has a finite size. The size of the plane 
    is specified as the the plane was sitting in the xy-plane of a Cartesian 
    system. The transformations are used dor the positioning.
    
    >>> fp = FinitePlane(length=1, width=1)
    >>> fp.intersection(Ray(position=(0,0,1), direction=(0,0,-1)))
    [array([ 0.,  0.,  0.])]
    
    >>> fp = FinitePlane(length=1, width=1)

    >>> fp.intersection(Ray(position=(0,0,1), direction=(.5,.25,-1)))
    [array([ 0.5 ,  0.25,  0.  ])]
    
    >>> fp = FinitePlane(length=1, width=1)
    >>> fp.append_transform(translation_matrix((2,0,0)))
    >>> fp.intersection(Ray(position=(0,0,1), direction=(0,0,-1)))
    """
    
    def __init__(self, length=1, width=1):
        super(FinitePlane, self).__init__()
        self.length = length
        self.width = width
    
    def append_transform(self, new_transform):
        super(FinitePlane, self).append_transform(new_transform)
    
    def on_surface(self, point):
        """Returns True if the point is on the plane's surface and false otherwise."""
        inv_transform = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, inv_transform)
        if cmp_floats(rpos, 0.) and (0. < rpos[0] <= self.length ) and (0. < rpos[1] <= self.width):
            return True
        return False
    
    def intersection(self, ray):
        """Returns a intersection point with a ray and the finte plane."""
        points = super(FinitePlane, self).intersection(ray)
        # Is point in the finite plane bounds
        local_point = transform_point(points[0], self.transform)
        if (0. <= local_point[0] <= self.length ) and (0. <= local_point[1] <= self.width):
            return points
        return None



class Polygon(object):
    """
    A (2D) Polygon with n (>2) points
    Only konvex polygons are allowed! Order of points is of course important!
    """
    
    def __init__(self, points):
        super(Polygon, self).__init__()
        self.pts = points
        #check if points are in one plane
        assert len(self.pts) >= 3, "You need at least 3 points to build a Polygon"
        if len(self.pts) > 3:
            x_0 = np.array(self.pts[0])
            for i in range(1,len(self.pts)-2):
                #the determinant of the vectors (volume) must always be 0
                x_i = np.array(self.pts[i])
                x_i1 = np.array(self.pts[i+1])
                x_i2 = np.array(self.pts[i+2])
                det = np.linalg.det([x_0-x_i, x_0-x_i1, x_0-x_i2])
                assert cmp_floats( det, 0.0 ), "Points must be in a plane to create a Polygon"
                

    def on_surface(self, point):
        """Returns True if the point is on the polygon's surface and false otherwise."""
        n = len(self.pts)
        anglesum = 0
        p = np.array(point)

        for i in range(n):
            v1 = np.array(self.pts[i]) - p
            v2 = np.array(self.pts[(i+1)%n]) - p

            m1 = magnitude(v1)
            m2 = magnitude(v2)

            if cmp_floats( m1*m2 , 0. ):
                return True #point is one of the nodes
            else:
                # angle(normal, vector)
                costheta = np.dot(v1,v2)/(m1*m2)
            anglesum = anglesum + np.arccos(costheta)
        return cmp_floats( anglesum , 2*np.pi )


    def contains(self, point):
        return False


    def surface_identifier(self, surface_point, assert_on_surface = True):
        return "polygon"


    def surface_normal(self, ray, acute=False):
        vec1 = np.array(self.pts[0])-np.array(self.pts[1])
        vec2 = np.array(self.pts[0])-np.array(self.pts[2])
        normal = norm( np.cross(vec1,vec2) )
        return normal


    def intersection(self, ray):
        """Returns a intersection point with a ray and the polygon."""
        n = self.surface_normal(ray)

        #Ray is parallel to the polygon
        if cmp_floats( np.dot( np.array(ray.direction), n ), 0. ):
            return None
 
        t = 1/(np.dot(np.array(ray.direction),n)) * ( np.dot(n,np.array(self.pts[0])) - np.dot(n,np.array(ray.position)) )
        
        #Intersection point is behind the ray
        if t < 0.0:
            return None

        #Calculate intersection point
        point = np.array(ray.position) + t*np.array(ray.direction)
        
        #Check if intersection point is really in the polygon or only on the (infinite) plane
        if self.on_surface(point):
            return [list(point)]

        return None


    
class Box(object):
    """An axis aligned box defined by an minimum and extend points (array/list like values)."""
    
    def __init__(self, origin=(0,0,0), extent=(1,1,1)):
        super(Box, self).__init__()
        self.origin = np.array(origin)
        self.extent = np.array(extent)
        self.points = [origin, extent]
        self.transform = tf.identity_matrix()
    
    def append_transform(self, new_transform):
        self.transform = tf.concatenate_matrices(new_transform, self.transform)
    
    def contains(self, point):
        """Returns True is the point is inside the box or False if it is not or is on the surface.
        
        >>> box = Box([1,1,1], [2,2,2])
        >>> box.contains([2,2,2])
        False
        >>> box = Box([1,1,1], [2,2,2])
        >>> box.contains([3,3,3])
        False
        >>> # This point is not the surface within rounding errors
        >>> box = Box([0,0,0], [1,1,1])
        >>> box.contains([ 0.04223342,  0.99999999999999989  ,  0.35692177])
        False
        >>> box = Box([0,0,0], [1,1,1])
        >>> box.contains([ 0.04223342,  0.5        ,  0.35692177])
        True
        """
        #local_point = transform_point(point, tf.inverse_matrix(self.transform))
        #for pair in zip((self.origin, local_point, self.extent)):
        #    if not pair[0] < pair[1] < pair[2]:
        #        return False
        #return True
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        for i in range(0,3):
            #if not (self.origin[i] < local_point[i] < self.extent[i]):
            # Want to make this comparison: self.origin[i] < local_point[i] < self.extent[i]
            c1 = cmp_floats_range(self.origin[i], local_point[i])
            #print self.origin[i], " is less than ", local_point[i]
            if c1 == -1:
                b1 = True
            else:
                b1 = False
            #print b1
            
            c2 = cmp_floats_range(local_point[i], self.extent[i])
            #print local_point[i], " is less than ", self.extent[i]
            if c2 == -1:
                b2 = True
            else:
                b2 = False
            #print b2
            
            if not (b1 and b2):
                return False
                
        return True
        

        """ # Alternatively:
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        def_points = np.concatenate((np.array(self.origin), np.array(self.extent)))

        containbool = True
        
        for i in range(0,3):
            if intervalcheckstrict(def_points[i],local_point[i],def_points[i+3]) == False:
                containbool = False

        return containbool
        """   
        
    
    def surface_identifier(self, surface_point, assert_on_surface = True):
        """
        Returns an unique identifier that specifies the surface which holds the surface_points.
        self.on_surface(surface_point) must return True, otherwise an assert error is thrown.
        Example, for a Box with origin=(X,Y,Z), and size=(L,W,H) has the identifiers:
        "left":(X,y,z)
        "right":(X+L,y,z)
        "near":(x,Y,z)
        "far":(x,Y+W,z)
        "bottom":(x,y,H)
        "top":(x,y,Z+H)
        """
        
        # Get an axis-aligned point... then this is really easy.
        local_point = transform_point(surface_point, tf.inverse_matrix(self.transform))
        # the local point must have at least one common point with the surface definition points
        def_points = np.concatenate((np.array(self.origin), np.array(self.extent)))
                 
        #surface_id[0]=0 => left
        #surface_id[1]=0 => near
        #surface_id[2]=0 => bottom
        #surface_id[3]=0 => right
        #surface_id[4]=0 => far
        #surface_id[5]=0 => top
        
        #import pdb; pdb.set_trace()
        surface_id_array = [0,0,0,0,0,0]
        boolarray = [False, False, False]
          
        for i in range(0,3):
            if cmp_floats(def_points[i], local_point[i]):
                for j in range(0,3):
                    if intervalcheck(def_points[j],local_point[j],def_points[j+3]):
                        surface_id_array[i] = 1
                        boolarray[j] = True
                        
                   
            if cmp_floats(def_points[i+3], local_point[i]):
                for j in range(0,3):
                    if intervalcheck(def_points[j],local_point[j],def_points[j+3]):
                        surface_id_array[i+3] = 1                        
                        boolarray[j] = True          
                    
        if assert_on_surface == True:                                        
            assert boolarray[0] == boolarray[1] == boolarray[2] == True 
           
        surface_name = []
        
        if surface_id_array[0] == 1:
            surface_name.append('left')
        if surface_id_array[1] == 1:
            surface_name.append('near')
        if surface_id_array[2] == 1:
            surface_name.append('bottom')
        if surface_id_array[3] == 1:
            surface_name.append('right')
        if surface_id_array[4] == 1:
            surface_name.append('far')
        if surface_id_array[5] == 1:
            surface_name.append('top')
        

        """
        The following helps to specify if the local_point is located on a corner
        or edge of the box. If that is not desired, simply return surface_name[0].
        """

        # return surface_name[0]
        
        return_id = ''
        
        for j in range(len(surface_name)):
            return_id = return_id + surface_name[j] + ''
            
        return return_id
    
                
    def on_surface(self, point):
        """Returns True if the point is on the surface False otherwise.
        >>> box = Box([1,1,1], [2,2,2])
        >>> box.on_surface([2,2,2])
        True
        >>> box = Box([1,1,1], [2,2,2])
        >>> box.on_surface([4,4,4])
        False
        >>> box = Box(origin=(0, 0, 1.1000000000000001), extent=np.array([ 1. ,  1. ,  2.1]))
        >>> ray = Ray(position=(.5,.5, 2.1), direction=(0,0,1))
        >>> box.on_surface(ray.position)
        True
        """

        if self.contains(point) == True:
            return False
        
        # Get an axis-aligned point... then this is really easy.
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        # the local point must have at least one common point with the surface definition points
        def_points = np.concatenate((np.array(self.origin), np.array(self.extent)))

                
        bool1 = False
        bool2 = False
        bool3 = False
        boolarray = [bool1, bool2, bool3]
        
        for i in range(0,3):
            if cmp_floats(def_points[i], local_point[i]):
                for j in range(0,3):
                    if intervalcheck(def_points[j],local_point[j],def_points[j+3]):
                        boolarray[j] = True
                   
            if cmp_floats(def_points[i+3], local_point[i]):
                for j in range(0,3):
                    if intervalcheck(def_points[j],local_point[j],def_points[j+3]):
                        boolarray[j] = True                        
                                                 
        if boolarray[0] == boolarray[1] == boolarray[2] == True:
            return True

        return False
                            
             
    def surface_normal(self, ray, acute=True):
        """
        Returns the normalised vector of which is the acute surface normal (0<~ theta <~ 90) 
        with respect to ray direction. If acute=False is specified the reflex
        normal is returned (0<~ theta < 360) The ray must be on the surface 
        otherwise an error is raised.
        
        >>> box = Box([0,0,0], [1,1,1])
        >>> ray = Ray([0.5,0.5,1], [0,0,1])
        >>> box.surface_normal(ray)
        array([ 0.,  0.,  1.])
        
        >>> box = Box([1,1,1], [2,2,2])
        >>> ray = Ray([1.5,1.5,2], [0,0,1])
        >>> box.surface_normal(ray)
        array([ 0.,  0.,  1.])
        """
        
        #pdb.set_trace()
        assert self.on_surface(ray.position), "The point is not on the surface of the box."
        invtrans = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, invtrans)
        rdir = transform_direction(ray.direction, invtrans)
        
        # To define a flat surface, 3 points are needed.
        common_index = None
        exit = False
        reference_point = list(self.origin)
        for ref in reference_point:
            if not exit:
                for val in rpos:
                    #logging.debug(str((ref,val)))
                    if cmp_floats(ref,val):
                        #logging.debug("Common value found, " + str(val) + " at index" + str(list(rpos).index(val)))
                        common_index = list(rpos).index(val)
                        exit = True
                        break
        
        exit = False
        if common_index == None:
            reference_point = list(self.extent)
            for ref in reference_point:
                if not exit:
                    for val in rpos:
                        #logging.debug(str((ref,val)))
                        if cmp_floats(ref,val):
                            #logging.debug("Common value found, " + str(val) + " at index" + str(list(rpos).index(val)))
                            common_index = list(rpos).index(val)
                            exit = True
                            break
        
        assert common_index != None, "The intersection point %s doesn't share an element with either the origin %s or extent points %s (all points transformed into local frame)." % (rpos, self.origin, self.extent)
        
        normal = np.zeros(3)
        if list(self.origin) == list(reference_point):
            normal[common_index] = -1.
        else:
            normal[common_index] = 1.
        
        if acute:
            if angle(normal, rdir) > np.pi/2:
                normal = normal * -1.0
                assert 0 <= angle(normal, rdir) <= np.pi/2, "The normal vector needs to be pointing in the same direction quadrant as the ray, so the angle between them is between 0 and 90"
            
        # remove signed zeros this just makes the doctest work. Signed zeros shouldn't really effect the maths but makes things neat.
        for i in range(0,3):
            if normal[i] == 0.0:
                normal[i] = 0.0
        return transform_direction(normal, self.transform)
        
    def intersection(self, ray):
        '''Returns an array intersection points with the ray and box. If no intersection occurs
        this function returns None.
        
        # Inside-out single intersection
        >>> ray = Ray(position=[0.5,0.5,0.5], direction=[0,0,1])
        >>> box = Box()
        >>> box.intersection(ray)
        [array([ 0.5,  0.5,  1. ])]
        
        # Inside-out single intersection with translation
        >>> ray = Ray(position=[0.5,0.5,0.5], direction=[0,0,1])
        >>> box = Box()
        >>> box.transform = tf.translation_matrix([0,0,1])
        >>> box.intersection(ray)
        [array([ 0.5,  0.5,  1. ]), array([ 0.5,  0.5,  2. ])]
        
        >>> ray = Ray(position=[0.5,0.5,0.5], direction=[0,0,1])
        >>> box = Box()
        >>> box.append_transform(tf.rotation_matrix(2*np.pi, [0,0,1]))
        >>> box.intersection(ray)
        [array([ 0.5,  0.5,  1. ])]
        
        >>> ray = Ray(position=[0.5,0.5,0.5], direction=[0,0,1])
        >>> box = Box()
        >>> box.append_transform(tf.rotation_matrix(2*np.pi, norm([1,1,0])))
        >>> box.append_transform(tf.translation_matrix([0,0,1]))
        >>> box.intersection(ray)
        [array([ 0.5,  0.5,  1. ]), array([ 0.5,  0.5,  2. ])]
        
        Here I am using the the work of Amy Williams, Steve Barrus, R. Keith Morley, and 
        Peter Shirley, "An Efficient and Robust Ray-Box Intersection Algorithm" Journal of 
        graphics tools, 10(1):49-54, 2005'''
        
        invtrans = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, invtrans)
        rdir = transform_direction(ray.direction, invtrans)
        #pts = [transform_point(self.points[0], self.transform), transform_point(self.points[1], self.transform)]
        pts = [np.array(self.points[0]), np.array(self.points[1])]
        
        rinvd = [1.0/rdir[0], 1.0/rdir[1], 1.0/rdir[2]]
        rsgn = [1.0/rinvd[0] < 0.0, 1.0/rinvd[1] < 0.0, 1.0/rinvd[2] < 0.0]
        tmin = (pts[rsgn[0]][0] - rpos[0]) * rinvd[0]
        tmax = (pts[1-rsgn[0]][0] - rpos[0]) * rinvd[0]
        tymin = (pts[rsgn[1]][1] - rpos[1]) * rinvd[1]
        tymax = (pts[1-rsgn[1]][1] - rpos[1]) * rinvd[1]
        
        #Bug here: this is the exit point with bug1.py
        if (tmin > tymax) or (tymin > tmax): 
            return None
            
        if tymin > tmin:
            tmin = tymin
            
        if tymax < tmax:
            tmax = tymax
            
        tzmin = (pts[rsgn[2]][2] - rpos[2]) * rinvd[2]
        tzmax = (pts[1-rsgn[2]][2] - rpos[2]) * rinvd[2]
        
        if (tmin > tzmax) or  (tzmin > tmax): 
            return None
            
        if tzmin > tmin:
            tmin = tzmin
            
        if tzmax < tmax:
            tmax = tzmax
        
        # Calculate the hit coordinates then if the solution is in the forward direction append to the hit list.
        hit_coordinates = []
        pt1 = rpos + tmin * rdir
        pt2 = rpos + tmax * rdir
        
        #pt1_sign = np.dot(pt1, rdir)
        #pt2_sign = np.dot(pt2, rdir)
        #print "tmin", tmin, "tmax", tmax
        if tmin >= 0.0:
            hit_coordinates.append(pt1)
        
        if tmax >= 0.0:
            hit_coordinates.append(pt2)
        
        #print hit_coordinates
        if len(hit_coordinates) == 0:
            return None
        
        # Convert hit coordinate back to the world frame
        hit_coords_world = []
        for point in hit_coordinates:
            hit_coords_world.append(transform_point(point, self.transform))
        return hit_coords_world
    

class Cylinder(object):
    """
    Parameterised standard representation of a cylinder. The axis is aligned along z but the radius 
    and the length of the cylinder can be specified. A transformation must be applied to use 
    centered at a different location of angle.
    """
    def __init__(self, radius=1, length=1):
        super(Cylinder, self).__init__()
        self.radius = radius
        self.length = length
        self.transform = tf.identity_matrix()
    
    def append_transform(self, new_transform):
        self.transform = tf.concatenate_matrices(new_transform, self.transform)
    
    def contains(self, point):
        """
        Returns True if the point in inside the cylinder and False if it is on the surface or outside.
        >>> # Inside
        >>> cylinder = Cylinder(.5, 2)
        >>> cylinder.contains([.25, .25, 1])
        True
        >>> # On surface
        >>> cylinder.contains([.0, .0, 2.])
        False
        >>> # Outside
        >>> cylinder.contains([-1,-1,-1])
        False
        """

        if self.on_surface(point) == True:
            return False
        
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        
        origin_z = 0.
        xydistance = np.sqrt(local_point[0]**2 + local_point[1]**2)
        if intervalcheckstrict(origin_z, local_point[2], self.length) == True and xydistance<self.radius:
            return True
        else:
            return False        
            
    def surface_normal(self, ray, acute=True):
        """
        Return the surface normal for a ray on the shape surface. 
        An assert error is raised if the ray is not on the surface.
        
        >>> cylinder = Cylinder(2, 2)
        >>> #Bottom cap in
        >>> ray = Ray([0,0,0], [0,0,1])
        >>> cylinder.surface_normal(ray)
        array([ 0.,  0.,  1.])
        >>> #Bottom cap out
        >>> ray = Ray([0,0,0], [0,0,-1])
        >>> cylinder.surface_normal(ray)
        array([ 0.,  0., -1.])
        >>> # End cap in
        >>> ray = Ray([0,0,2], [0,0,-1])
        >>> cylinder.surface_normal(ray)
        array([ 0.,  0., -1.])
        >>> # End cap out
        >>> ray = Ray([0,0,2], [0,0,1])
        >>> cylinder.surface_normal(ray)
        array([ 0.,  0.,  1.])
        >>> # Radial
        >>> ray = Ray([2, 0, 1], [1,0,0])
        >>> cylinder.surface_normal(ray)
        array([ 1.,  0.,  0.])
        
        """
        assert self.on_surface(ray.position), "The ray is not on the surface."
        invtrans = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, invtrans)
        rdir = transform_direction(ray.direction, invtrans)
        
        # point on radius surface
        pt_radius = np.sqrt(rpos[0]**2 + rpos[1]**2)
        c0 = cmp_floats(pt_radius, self.radius)
        
        #point on end caps
        c1 = cmp_floats(rpos[2], .0)
        c2 = cmp_floats(rpos[2], self.length)
        
        # check radius first
        if c0 and (c1 == c2):
            normal = norm(np.array(rpos) - np.array([0,0,rpos[2]]))
        elif c1:
            normal = np.array([0,0,-1])
        else:
            # Create a vector that points from the axis of the cylinder to the ray position, 
            # this is the normal vector.
            normal = np.array([0,0,1])

        if acute:
            if angle(normal, rdir) > np.pi*0.5:
                normal = normal * -1.
                
        return transform_direction(normal, self.transform)
            
    
    def on_surface(self, point):
        """
        >>> # On surface
        >>> cylinder = Cylinder(.5, 2.)
        >>> cylinder.on_surface([.0, .0, 2.])
        True
        """
        
        """ # !!! Old version !!!
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        
        # xy-component is equal to radius
        pt_radius = np.sqrt(local_point[0]**2 + local_point[1]**2)
        c0 = cmp_floats(pt_radius, self.radius)
        
        #z-component is equal to zero or length
        c1 = cmp_floats(local_point[2], .0)
        c2 = cmp_floats(local_point[2], self.length)
        
       
        if c1 or c2:
            return True
        elif c0:
            return True
        else:
            return False
        """

        
        
        local_point = transform_point(point, tf.inverse_matrix(self.transform))
        
        origin_z = 0.
        xydistance = np.sqrt(local_point[0]**2 + local_point[1]**2)
        
        if intervalcheck(origin_z, local_point[2], self.length) == True:
            if cmp_floats(xydistance, self.radius) == True:
                return True
            
        if smallerequalto(xydistance,self.radius):
            if cmp_floats(local_point[2], origin_z) == True or cmp_floats(local_point[2], self.length) == True:
                return True
                
        return False
            
        
    def surface_identifier(self, surface_point, assert_on_surface = True):
        local_point = transform_point(surface_point, tf.inverse_matrix(self.transform))
        
        origin_z = 0.
        xydistance = np.sqrt(local_point[0]**2 + local_point[1]**2)
        """
        Assert surface_point on surface
        """
        assertbool = False
               
        if intervalcheck(origin_z, local_point[2], self.length) == True:
            if cmp_floats(xydistance, self.radius) == True:                
                surfacename = 'hull'
                assertbool = True
            
        if smallerequalto(xydistance,self.radius):
            if cmp_floats(local_point[2], origin_z) == True:
                surfacename = 'base'
                assertbool = True
            if cmp_floats(local_point[2], self.length) == True:
                surfacename = 'cap'
                assertbool = True

        if assert_on_surface == True:    
            assert assertbool, "The assert bool is wrong."
        return surfacename
        
    
    def intersection(self, ray):
        """
        Returns all forward intersection points with ray and the capped cylinder. 
        The intersection algoithm is taken from, "Intersecting a Ray with a Cylinder"
        Joseph M. Cychosz and Warren N. Waggenspack, Jr., in "Graphics Gems IV", 
        Academic Press, 1994.
        
        >>> cld = Cylinder(1.0, 1.0)
        >>> cld.intersection(Ray([0.0,0.0,0.5], [1,0,0]))
        [array([ 1. ,  0. ,  0.5])]
        
        >>> cld.intersection(Ray([-5,0.0,0.5], [1,0,0]))
        [array([-1. ,  0. ,  0.5]), array([ 1. ,  0. ,  0.5])]
        
        >>> cld.intersection(Ray([.5,.5,-1], [0,0,1]))
        [array([ 0.5,  0.5,  1. ]), array([ 0.5,  0.5,  0. ])]
        
        >>> cld.intersection( Ray([0.0,0.0,2.0], [0,0,-1]))
        [array([ 0.,  0.,  1.]), array([ 0.,  0.,  0.])]
        
        >>> cld.intersection(Ray([-0.2, 1.2,0.5],[0.75498586, -0.53837322,  0.37436697]))
        [array([ 0.08561878,  0.99632797,  0.64162681]), array([ 0.80834999,  0.48095523,  1.        ])]
        
        >>> cld.intersection(Ray(position=[ 0.65993112596983427575736414, -0.036309587083015459896273569,  1.        ], direction=[ 0.24273873128664008591570678, -0.81399482405912471083553328,  0.52772183462341881732271531]))
        [array([ 0.65993113, -0.03630959,  1.        ])]
        
        >>> cld.transform = tf.translation_matrix([0,0,1])
        >>> cld.intersection(Ray([-5,0.0,1.5], [1,0,0]))
        [array([-1. ,  0. ,  1.5]), array([ 1. ,  0. ,  1.5])]
        
        >>> cld.transform = tf.identity_matrix()
        >>> cld.transform = tf.rotation_matrix(0.25*np.pi, [1,0,0])
        >>> cld.intersection(Ray([-5,-.5,-0.25], [1,0,0]))
        [array([-0.84779125, -0.5       , -0.25      ]), array([ 0.84779125, -0.5       , -0.25      ])]
        """
        # Inverse transform the ray to get it into the cylinders local frame
        inv_transform = tf.inverse_matrix(self.transform)
        rpos = transform_point(ray.position, inv_transform)
        rdir = transform_direction(ray.direction, inv_transform)
        direction = np.array([0,0,1])
        
        normal = np.cross(rdir, direction)
        normal_magnitude = magnitude(normal)
        #print normal_magnitude, "Normal magnitude"
        
        if cmp_floats(normal_magnitude, .0):
        
            # Ray parallel to cylinder direction
            normal = norm(normal)
            #d = abs(np.dot(rpos, direction))
            #D = rpos - d * np.array(direction)
            #if magnitude(D) <= self.radius:
            
            # Axis aligned ray inside the cylinder volume only hits caps
            #print "Inside axis aligned ray only hits caps"
            bottom = Plane()
            top = Plane()
            top.transform = tf.translation_matrix([0,0,self.length])
            p0 = top.intersection(Ray(rpos, rdir))
            p1 = bottom.intersection(Ray(rpos, rdir))
            cap_intersections = []
            if p0 != None:
                cap_intersections.append(p0)
            if p1 != None:
                cap_intersections.append(p1)
            points = []
            for point in cap_intersections:
                
                if point[0] != None:
                    point = point[0]
                    point_radius = np.sqrt(point[0]**2 + point[1]**2)
                    if point_radius <= self.radius:
                        #print "Hit cap at point:"
                        #print point
                        #print ""
                        points.append(point)
            
            if len(points) > 0:
                world_points = []
                for pt in points:
                    world_points.append(transform_point(pt, self.transform))
                #print "Local points", points
                #print "World points", world_points
                return world_points
            
            return None
        # finish axis parallel branch
        
        #print "Not parallel to cylinder axis."
        #print ""
        normal = norm(normal)
        d = abs(np.dot(rpos, normal))
        if d <= self.radius:
        
            #Hit quadratic surface
            O = np.cross(rpos, direction)
            t = - np.dot(O,normal) / normal_magnitude
            O = np.cross(normal, direction)
            O = norm(O)
            s = abs(np.sqrt(self.radius**2 - d**2) / np.dot(rdir, O))
            t0 = t - s
            p0 = rpos + t0 * rdir
            t1 = t + s
            p1 = rpos + t1 * rdir
            
            points = []
            if (t0 >= 0.0) and (.0 <= p0[2] <= self.length):
                points.append(p0)
            
            if (t1 >= 0.0) and (.0 <= p1[2] <= self.length):
                points.append(p1)
            
            #print "Hits quadratic surface with t0 and t1, ", t0, t1
            #print ""
            #print "Intersection points:"
            #p0 = rpos + t0 * rdir
            #p1 = rpos + t1 * rdir
            
            # Check that hit quadratic surface in the length range
            #points = []
            #if (.0 <= p0[2] <= self.length) and not Ray(rpos, rdir).behind(p0):
            #    points.append(p0)
            #
            #if (.0 <= p1[2] <= self.length) and not Ray(rpos, rdir).behind(p1):
            #    points.append(p1)
            
            #print points
            #Now compute intersection with end caps
            #print "Now to calculate caps intersections"
            
            bottom = Plane()
            top = Plane()
            top.transform = tf.translation_matrix([0,0,self.length])
            p2 = top.intersection(Ray(rpos, rdir))
            p3 = bottom.intersection(Ray(rpos, rdir))
            cap_intersections = []
            if p2 != None:
                cap_intersections.append(p2)
            if p3 != None:
                cap_intersections.append(p3)
            
            for point in cap_intersections:
                
                if point[0] != None:
                    point = point[0]
                    point_radius = np.sqrt(point[0]**2 + point[1]**2)
                    if point_radius <= self.radius:
                        #print "Hit cap at point:"
                        #print point
                        #print ""
                        points.append(point)
            
            #print points
            if len(points) > 0:
                world_points = []
                for pt in points:
                    world_points.append(transform_point(pt, self.transform))
                return world_points
            return None

class Convex(object):
    """docstring for Convex"""
    def __init__(self, points):
        super(Convex, self).__init__()
        self.points = points
        verts, triangles = qhull3d(points)
        self.faces = range(len(triangles))
        
        for i in range(len(triangles)):
            a = triangles[i][0]
            b = triangles[i][1]
            c = triangles[i][2]
            self.faces[i] = Polygon([verts[a], verts[b], verts[c]])
        
    def on_surface(self, point):
        for face in self.faces:
            if face.on_surface(point):
                return True
        return False
        
    def surface_normal(self, ray, acute=False):
        for face in self.faces:
            if face.on_surface(ray.position):
                normal = face.surface_normal(ray, acute=acute)
                if angle(normal , ray.direction) > np.pi/2:
                    normal = normal * -1
                return normal
                
        assert("Have not found the surface normal for this ray. Are you sure the ray is on the surface of this object?")
    
    def surface_identifier(self, surface_point, assert_on_surface=True):
        return "Convex"
    
    def intersection(self, ray):
        points = []
        for face in self.faces:
            pt = face.intersection(ray)
            if pt != None:
                points.append(np.array(pt[0]))
        if len(points) > 0:
            return points
        return None
    
    def contains(self, point):
        ray = Ray(position=point, direction=norm(np.random.random(3)))
        hit_counter = 0
        for face in self.faces:
            
            if face.on_surface(ray.position):
                return False
                
            pt = face.intersection(ray)
            if pt != None:
                hit_counter = hit_counter + 1
        
        even_or_odd = hit_counter % 2
        if even_or_odd == 0:
            return False
        return True
    
    def centroid(self):
        """Credit:
        http://orion.math.iastate.edu:80/burkardt/c_src/geometryc/geometryc.html
        
        Returns the 'centroid' of the Convex polynomial.
        """
        raise NotImplementedError("The centroid method of the Convex class is not yet implemented.")
        #area = 0.0;
        #for ( i = 0; i < n - 2; i++ ) {
        #areat = triangle_area_3d ( x[i], y[i], z[i], x[i+1], 
        #  y[i+1], z[i+1], x[n-1], y[n-1], z[n-1] );
        #    
        #area = area + areat;
        #*cx = *cx + areat * ( x[i] + x[i+1] + x[n-1] ) / 3.0;
        #*cy = *cy + areat * ( y[i] + y[i+1] + y[n-1] ) / 3.0;
        #*cz = *cz + areat * ( z[i] + z[i+1] + z[n-1] ) / 3.0;
        #
        #}
        #
        #*cx = *cx / area;
        #*cy = *cy / area;
        #*cz = *cz / area;
        #
        
if __name__ == "__main__":
    import doctest
    #doctest.testmod()
    
    if False:
        # Catch the special case in which we cannot take the cross product
        V1 = [0,0,1]                                                          
        V2 = [0,0,-1]
        #import pdb; pdb.set_trace()                                                      
        R = rotation_matrix_from_vector_alignment(V1, V2)
        R2 = rotation_matrix(np.pi, [1,0,0])
        V3 = transform_direction(V1, R)
        print R2
        print cmp_points(V2, V3)

