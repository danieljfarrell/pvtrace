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

from Geometry import Box, Cylinder, Ray, cmp_points, separation
from external.transformations import translation_matrix, rotation_matrix
import external.transformations as tf
import numpy as np

def transform_point(point, transform):
    return np.array(np.dot(transform, np.matrix(np.concatenate((point, [1.]))).transpose()).transpose()[0,0:3]).squeeze()

def transform_direction(direction, transform):
    angle, axis, point = tf.rotation_from_matrix(transform)
    rotation_transform = tf.rotation_matrix(angle, axis)
    return np.array(np.dot(rotation_transform, np.matrix(np.concatenate((direction, [1.]))).transpose()).transpose()[0,0:3]).squeeze()

   
class CSGadd(object):

    """
    Constructive Solid Geometry Boolean Addition
    """

    def __init__(self, ADDone, ADDtwo):

        super(CSGadd, self).__init__()
        self.ADDone = ADDone
        self.ADDtwo = ADDtwo
        self.reference = 'CSGadd'
        self.transform = tf.identity_matrix()

    def append_name(self, namestring):
        """
        In case a scene contains several CSG objects, this helps
        with surface identification (see return value of def surface_identifier(..))
        """
        self.reference = namestring
        
    def append_transform(self, new_transform):
        self.transform = tf.concatenate_matrices(new_transform, self.transform)
        self.ADDone.transform = tr.concatenate_matrices(new_transform, self.ADDone.transform)
        self.ADDtwo.transform = tr.concatenate_matrices(new_transform, self.ADDtwo.transform)
        
    def contains(self, point):
        """
        Returns True if ray contained by CSGadd, False otherwise
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(point, invtransform)
        
        bool1 = self.ADDone.contains(local_point)
        bool2 = self.ADDtwo.contains(local_point)
        bool3 = self.ADDone.on_surface(local_point)
        bool4 = self.ADDtwo.on_surface(local_point)

        if bool1 or bool2:
            return True

        if bool3 and bool4:
            return True

        return False

    def intersection(self, ray):
        """
        Returns the intersection points of ray with CSGadd in global frame
        """

        # We will need the invtransform later when we return the results..."
        invtransform = tf.inverse_matrix(self.transform)

        localray = Ray()

        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)

        ADDone__intersections = self.ADDone.intersection(localray)
        ADDtwo__intersections = self.ADDtwo.intersection(localray)

        """
        Cover the simpler cases
        """
        if ADDone__intersections == None and ADDtwo__intersections == None:
            return None  

        """
        Change ..._intersections into tuples
        """
        if ADDone__intersections != None:
            for i in range(0,len(ADDone__intersections)):
                point = ADDone__intersections[i]
                new_point = (point[0], point[1], point[2])
                ADDone__intersections[i] = new_point
                
        if ADDtwo__intersections != None:
            for i in range(0,len(ADDtwo__intersections)):
                point = ADDtwo__intersections[i]
                new_point = (point[0],point[1],point[2])
                ADDtwo__intersections[i] = new_point

        """
        Only intersection points NOT containted in resp. other structure relevant
        """
        ADDone_intersections = []
        ADDtwo_intersections = []

        if ADDone__intersections != None:
            for i in range(0,len(ADDone__intersections)):
                if self.ADDtwo.contains(ADDone__intersections[i]) == False:
                    ADDone_intersections.append(ADDone__intersections[i])

        if ADDtwo__intersections != None:
            for j in range(0,len(ADDtwo__intersections)):
                if self.ADDone.contains(ADDtwo__intersections[j]) == False:
                    ADDtwo_intersections.append(ADDtwo__intersections[j])

        """
        => Convert to list
        """
        ADDone_set = set(ADDone_intersections[:])
        ADDtwo_set = set(ADDtwo_intersections[:])
        combined_set = ADDone_set | ADDtwo_set
        combined_intersections = list(combined_set)

        """
        Just in case...
        """
        if len(combined_intersections) == 0:
            return None

        """
        Sort by separation from ray origin
        """
        intersection_separations = []
        for point in combined_intersections:
            intersection_separations.append(separation(ray.position, point))

        """
        Convert into Numpy arrays in order to sort
        """
                                            
        intersection_separations = np.array(intersection_separations)
        sorted_indices = intersection_separations.argsort()
        sorted_combined_intersections = []
        for index in sorted_indices:
            sorted_combined_intersections.append(np.array(combined_intersections[index]))

        global_frame_intersections = []
        for point in sorted_combined_intersections:
            global_frame_intersections.append(transform_point(point, self.transform))

        global_frame_intersections_cleared = []
        for point in global_frame_intersections:
            if self.on_surface(point) == True:
                """
                This is only necessary if the two objects have an entire surface region in common,
                for example consider two boxes joined at one face.
                """
                global_frame_intersections_cleared.append(point)

        if len(global_frame_intersections_cleared) == 0:
            return None
                
        return global_frame_intersections_cleared

    def on_surface(self, point):
        """
        Returns True or False dependent on whether point on CSGadd surface or not
        """

        if self.contains(point):
            return False

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(point, invtransform)
        
        bool1 = self.ADDone.on_surface(local_point)
        bool2 = self.ADDtwo.on_surface(local_point)

        if bool1 == True and self.ADDtwo.contains(local_point) == False:
            return True
                                            
        if bool2 == True and self.ADDone.contains(local_point) == False:
            return True
                                            
        if bool1 == bool2 == True:
            return True
                                            
        else:
            return False

    def surface_identifier(self, surface_point, assert_on_surface = True):
        """
        Returns surface-ID name if surface_point located on CSGadd surface
        """

        """
        Ensure surface_point on CSGadd surface
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(surface_point, invtransform)

        bool1 = self.ADDone.on_surface(local_point)
        bool2 = self.ADDtwo.on_surface(local_point)

        assertbool = False
        if bool1 == True and self.ADDtwo.contains(local_point) == False:
            assertbool = True
        elif bool2 == True and self.ADDone.contains(local_point) == False:
            assertbool = True
        elif bool1 == bool2 == True:
            assertbool = True
        if assert_on_surface == True:
            assert assertbool == True

                                                                         
        if bool1 == True and self.ADDtwo.contains(local_point) == False:
            return self.reference + "_ADDone_" + self.ADDone.surface_identifier(local_point)
                                            
        if bool2 == True and self.ADDone.contains(local_point) == False:
            return self.reference + "_ADDtwo_" + self.ADDtwo.surface_identifier(local_point)
                                            
    def surface_normal(self, ray, acute=True):

        """
        Returns surface normal in point where ray hits CSGint surface
        """

        """
        Ensure surface_point on CSGint surface
        """

        invtransform = tf.inverse_matrix(self.transform)
        localray = Ray()
        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)

        bool1 = self.ADDone.on_surface(localray.position)
        bool2 = self.ADDtwo.on_surface(localray.position)
        
        assertbool = False
        if bool1 == True and self.ADDtwo.contains(localray.position) == False:
            assertbool = True
        elif bool2 == True and self.ADDone.contains(localray.position) == False:
            assertbool = True
        elif bool1 == bool2 == True:
            assertbool = True
        assert assertbool == True


        if bool1 == True and self.ADDtwo.contains(localray.position) == False:
            local_normal = self.ADDone.surface_normal(localray, acute)
            return transform_direction(local_normal, self.transform)

        if bool2 == True and self.ADDone.contains(localray.position) == False:
            local_normal = self.ADDtwo.surface_normal(localray, acute)
            return transform_direction(local_normal, self.transform)
                                             

class CSGsub(object):
    """
    Constructive Solid Geometry Boolean Subtraction
    """
    
    def __init__(self, SUBplus, SUBminus):
        """
        Definition {CSGsub} := {SUBplus}/{SUBminus}
        """
        super(CSGsub, self).__init__()
        self.SUBplus = SUBplus
        self.SUBminus = SUBminus
        self.reference = 'CSGsub'
        self.transform = tf.identity_matrix()

    def append_name(self, namestring):
        """
        In case a scene contains several CSG objects, this helps
        with surface identification
        """
        self.reference = namestring
    
    def append_transform(self, new_transform):
        self.transform = tf.concatenate_matrices(new_transform, self.transform)
    
    def contains(self, point):
        """
        Returns True if ray contained by CSGsub, False otherwise
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(point, invtransform)
        
        bool1 = self.SUBplus.contains(local_point)
        bool2 = self.SUBminus.contains(local_point)
        
        if bool1 == False:
            return False
        
        if bool2 == True:
            return False
        
        else:
            return True
    
    def intersection(self, ray):
        """
        Returns the intersection points of ray with CSGsub in global frame
        """

        # We will need the invtransform later when we return the results..."
        invtransform = tf.inverse_matrix(self.transform)

        localray = Ray()

        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)
        
        SUBplus__intersections = self.SUBplus.intersection(localray)
        SUBminus__intersections = self.SUBminus.intersection(localray)
                  
        """
        Cover the simpler cases
        """
        if SUBplus__intersections == None and SUBminus__intersections == None:
            return None  
         
        """
        Change ..._intersections into tuples
        """
        if SUBplus__intersections != None:
            for i in range(0,len(SUBplus__intersections)):
                point = SUBplus__intersections[i]
                new_point = (point[0], point[1], point[2])
                SUBplus__intersections[i] = new_point

        if SUBminus__intersections != None:
            for i in range(0,len(SUBminus__intersections)):
                point = SUBminus__intersections[i]
                new_point = (point[0], point[1], point[2])
                SUBminus__intersections[i] = new_point
        
        """
        Valid intersection points:
        SUBplus intersections must lie outside SUBminus
        SUBminus intersections must lie inside SUBplus
        """
        
        SUBplus_intersections = []
        SUBminus_intersections = []

        if SUBplus__intersections != None:
            for intersection in SUBplus__intersections:
                if not self.SUBminus.contains(intersection):
                    SUBplus_intersections.append(intersection)

        if SUBminus__intersections != None:
            for intersection in SUBminus__intersections:
                if self.SUBplus.contains(intersection):
                    SUBminus_intersections.append(intersection)
            
        # SUBplus_set = set(SUBplus_intersections[:])
        # SUBminus_set = set(SUBminus_intersections[:])
        # combined_set = SUBplus_set ^ SUBminus_set
        # combined_intersections = list(combined_set)
        
        combined_intersections = np.array(list(set(SUBplus_intersections+SUBminus_intersections)))
        
        # intersection_separations = combined_intersections[0]**2+combined_intersections[1]**2+combined_intersections[2]**2
        """
        Just in case...
        """
        if len(combined_intersections) == 0:
            return None
        
        transposed_intersections = combined_intersections.transpose()
        
        
        intersection_vectors = transposed_intersections[0]-ray.position[0], transposed_intersections[1]-ray.position[1], transposed_intersections[2]-ray.position[2]
        
        # intersection_separations= []
        # print combined_intersections, point, intersection_vectors
              
        intersection_separations = intersection_vectors[0]**2+intersection_vectors[1]**2+intersection_vectors[2]**2
        
        # for point in combined_intersections:
        #     intersection_separations.append(separation(ray.position, point))

        # for i in range(len(intersection_separations)):
        #     print intersection_separations[i], intersection_separations2[i]

        """
        Sort by distance from ray origin => Use Numpy arrays
        """
        # intersection_separations = np.array(intersection_separations)
        sorted_combined_intersections = combined_intersections[intersection_separations.argsort()]
        # sorted_combined_intersections = []
        #         for index in sorted_indices:
        #             sorted_combined_intersections.append(np.array(combined_intersections[index]))
        
        
        # global_frame_intersections = []
        # for point in sorted_combined_intersections:
        #     global_frame_intersections.append(transform_point(point, self.transform))

        global_frame_intersections = [transform_point(point, self.transform) for point in sorted_combined_intersections]
        
        return global_frame_intersections
    
            
    def on_surface(self, point):
        """
        Returns True if the point is on the outer or inner surface of the CSGsub, and False othewise.
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(point, invtransform)
        
        bool1 = self.SUBplus.on_surface(local_point)
        bool2 = self.SUBminus.on_surface(local_point)

        if bool1 == True and self.SUBminus.contains(local_point) == False:
            return True
        if bool2 == True and self.SUBplus.contains(local_point) == True:
            return True
        else:
            return False

        """ Alternatively:
        if bool1 == bool2 == False:
            return False
        if bool1 == True and bool2 == True or SUBminus.contains(point) == True:
            return False
        if bool2 == True and bool1 == True or SUBplus.contains(point) == False:
            return False
        else:
            return True   
        """
        
    def surface_identifier(self, surface_point, assert_on_surface = True):
        """
        Returns a unique identifier for the surface location on the CSGsub.
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(surface_point, invtransform)
        
        bool1 = self.SUBplus.on_surface(local_point)
        bool2 = self.SUBminus.on_surface(local_point)

        assertbool = False
        if bool1 == True and self.SUBminus.contains(local_point) == False:
            assertbool = True
        elif bool2 == True and self.SUBplus.contains(local_point) == True:
            assertbool = True
        if assert_on_surface == True:
            assert assertbool == True

        if bool1 == True and self.SUBminus.contains(local_point) == False:
            return self.reference + "_SUBplus_" + self.SUBplus.surface_identifier(local_point)

        if bool2 == True and self.SUBplus.contains(local_point) == True:
            return self.reference + "_SUBminus_" + self.SUBminus.surface_identifier(local_point)
              
    def surface_normal(self, ray, acute=True):
        """
        Return the surface normal for a ray arriving on the CSGsub surface.
        """

        invtransform = tf.inverse_matrix(self.transform)
        localray = Ray()
        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)
        
        bool1 = self.SUBplus.on_surface(localray.position)
        bool2 = self.SUBminus.on_surface(localray.position)

        assertbool = False
        if bool1 == True and self.SUBminus.contains(localray.position) == False:
            assertbool = True
        if bool2 == True and self.SUBplus.contains(localray.position) == True:
            assertbool = True
        assert assertbool == True

        if bool1 == True and self.SUBminus.contains(localray.position) == False:            
            return self.SUBplus.surface_normal(ray, acute)            

        if bool2 == True and self.SUBplus.contains(localray.position) == True:
            if acute:            
                return self.SUBminus.surface_normal(ray,acute)
            else:
                normal = -1 * self.SUBminus.surface_normal(ray, acute=True)
                # Remove signed zeros
                for i in range(0,3):
                    if normal[i] == 0.0:
                        normal[i] = 0.0
                return normal
    
class CSGint(object):

    """
    Constructive Solid Geometry Boolean Intersection
    """

    def __init__(self, INTone, INTtwo):
    
        super(CSGint, self).__init__()
        self.INTone = INTone
        self.INTtwo = INTtwo
        self.reference = 'CSGint'
        self.transform = tf.identity_matrix()

    def append_name(self, namestring):
        """
        In case a scene contains several CSG objects, this helps
        with surface identification
        """
        self.reference = namestring

    def append_transform(self, new_transform):
        self.transform = tf.concatenate_matrices(new_transform, self.transform)

    def contains(self, point):
        """
        Returns True if ray contained by CSGint, False otherwise
        """

        invtransform = tf.inverse_matrix(self.transform)
        point = transform_point(point, invtransform)
        
        bool1 = self.INTone.contains(point)
        bool2 = self.INTtwo.contains(point)

        if bool1 == bool2 == True:
            return True
        
        else:
            return False

    def intersection(self, ray):
        """
        Returns the intersection points of ray with CSGint in global frame
        """

        # We will need the invtransform later when we return the results..."
        invtransform = tf.inverse_matrix(self.transform)

        localray = Ray()

        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)

        INTone__intersections = self.INTone.intersection(localray)
        INTtwo__intersections = self.INTtwo.intersection(localray)

        """
        Cover the simpler cases
        """
        if INTone__intersections == None and INTtwo__intersections == None:
            return None  
                                    
        """
        Change ..._intersections into tuples
        """
        if INTone__intersections != None:
            for i in range(0,len(INTone__intersections)):
                point = INTone__intersections[i]
                new_point = (point[0], point[1], point[2])
                INTone__intersections[i] = new_point

        if INTtwo__intersections != None:
            for i in range(0,len(INTtwo__intersections)):
                point = INTtwo__intersections[i]
                new_point = (point[0], point[1], point[2])
                INTtwo__intersections[i] = new_point

        """
        Only intersection points contained in resp. other structure relevant
        """
        INTone_intersections = []
        INTtwo_intersections = []

        if INTone__intersections != None:
            for i in range(0,len(INTone__intersections)):
                if self.INTtwo.contains(INTone__intersections[i]) == True:
                    INTone_intersections.append(INTone__intersections[i])

        if INTtwo__intersections != None:       
            for j in range(0,len(INTtwo__intersections)):
                if self.INTone.contains(INTtwo__intersections[j]) == True:
                    INTtwo_intersections.append(INTtwo__intersections[j])

        """
        => Convert to list
        """
        INTone_set = set(INTone_intersections[:])
        INTtwo_set = set(INTtwo_intersections[:])
        combined_set = INTone_set | INTtwo_set
        combined_intersections = list(combined_set)

        """
        Just in case...
        """
        if len(combined_intersections) == 0:
            return None

        """
        Sort by separation from ray origin
        """
        intersection_separations = []
        for point in combined_intersections:
            intersection_separations.append(separation(ray.position, point))

        """
        Convert into Numpy arrays in order to sort
        """
        intersection_separations = np.array(intersection_separations)
        sorted_indices = intersection_separations.argsort()
        sorted_combined_intersections = []
        for index in sorted_indices:
            sorted_combined_intersections.append(np.array(combined_intersections[index]))
            

        global_frame_intersections = []
        for point in sorted_combined_intersections:
            global_frame_intersections.append(transform_point(point, self.transform))

        return global_frame_intersections
    

    def on_surface(self, point):
        """
        Returns True or False dependent on whether point on CSGint surface or not
        """

        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(point, invtransform)
        
        bool1 = self.INTone.on_surface(local_point)
        bool2 = self.INTtwo.on_surface(local_point)

        if bool1 == bool2 == True:
            return True

        if bool1 == True and self.INTtwo.contains(local_point):
            return True

        if bool2 == True and self.INTone.contains(local_point):
            return True

        else:
            return False

    def surface_identifier(self, surface_point, assert_on_surface = True):
        """
        Returns surface-ID name if surface_point located on CSGint surface
        """

        """
        Ensure surface_point on CSGint surface
        """
        
        invtransform = tf.inverse_matrix(self.transform)
        local_point = transform_point(surface_point, invtransform)
        
        bool1 = self.INTone.on_surface(local_point)
        bool2 = self.INTtwo.on_surface(local_point)
        
        assertbool = False
        if bool1 == True and self.INTtwo.contains(local_point) == True:
            assertbool = True
        if bool2 == True and self.INTone.contains(local_point) == True:
            assertbool = True
        if bool1 == bool2 == True:
            assertbool = True
        if assert_on_surface == True:
            assert assertbool == True
                
        if bool1 == True:
            return self.reference + "_INTone_" + self.INTone.surface_identifier(local_point)
        if bool2 == True:
            return self.reference + "_INTtwo_" + self.INTtwo.surface_identifier(local_point)

    def surface_normal(self, ray, acute=True):
        """
        Returns surface normal in point where ray hits CSGint surface
        """

        """
        Ensure surface_point on CSGint surface
        """

        invtransform = tf.inverse_matrix(self.transform)
        localray = Ray()
        localray.position = transform_point(ray.position, invtransform)
        localray.direction = transform_direction(ray.direction, invtransform)
        
        bool1 = self.INTone.on_surface(localray.position)
        bool2 = self.INTtwo.on_surface(localray.position)
        
        assertbool = False
        if bool1 == True and self.INTtwo.contains(localray.position) == True:
            assertbool = True
        if bool2 == True and self.INTone.contains(localray.position) == True:
            assertbool = True
        if bool1 == bool2 == True:
            assertbool = True
        assert assertbool == True
                     
        if bool1 == True:
            return self.INTone.surface_normal(ray, acute)
        else:
            return self.INTtwo.surface_normal(ray, acute)


        
if __name__ == '__main__':

    """
    TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST TEST
    """
    """
    # EXAMPLE ZERO
    INTone = Box(origin = (-1.,0.,0.), extent = (1,1,1))
    INTtwo = Cylinder(1, 1)
    #one.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
    intersect = CSGint(INTone, INTtwo)

    INTthree = Cylinder(0.5,1)
    intersect2 = CSGint(intersect, INTthree) 
    """

    """
    # EXAMPLE ONE
    obj1 = Box(origin=(0,0,0), extent=(3,3,5))
    obj2 = Box(origin=(1,1,0), extent=(2,2,7))
    boxbox = CSGadd(obj2, obj1)
    boxbox.append_name('MyBoxBox')
     

    pt = (1,3,1.5)
    ray = Ray(position=(1,3,1.5), direction=(0.,-1.,0.))
    print "Point: "
    print pt
    print "Ray position: "
    print ray.position
    print "Ray direction: "
    print ray.direction
    print "\n----> test .contains(pt) "
    print obj1.contains(pt)
    print obj2.contains(pt)
    print boxbox.contains(pt)
    print "\n----> test .on_surface(pt)"
    print obj1.on_surface(pt)
    print obj2.on_surface(pt)
    print boxbox.on_surface(pt)    
    print "\n----> test .surface_identifier(pt)"
    print boxbox.surface_identifier(pt)
    print "\n----> test .intersection(ray)"        
    print obj1.intersection(ray)
    print obj2.intersection(ray)
    print boxbox.intersection(ray)
    print "\n----> test .surface_normal(ray)"
    print boxbox.surface_normal(ray)
    # END EXAMPLE ONE
    """

    """
    # EXAMPLE TWO: ITERATIVE ADDITION
    obj1 = Box(origin=(0,0,0), extent=(1,1,1))
    obj2 = Box(origin=(0,0,0), extent=(1,1,1))
    #obj2.append_transform(tf.translation_matrix((0,2,0)))
    obj2.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))

    print obj2.transform
    
    boxbox1 = CSGadd(obj2, obj1)
    boxbox1.append_name('MyBoxBox1')
    boxbox1.append_transform(tf.translation_matrix((0,0,0)))

    boxbox2 = CSGadd(obj2, obj1)
    boxbox2.append_name('MyBoxBox2')
    boxbox2.append_transform(tf.translation_matrix((0,0,2)))

    fourbox = CSGadd(boxbox1, boxbox2)
    fourbox.append_name('MyFourBox')

    print boxbox1.transform
    print '\n'
    print boxbox2.transform
    print '\n'
    print fourbox.transform
    print '\n'

    print obj2.intersection(ray)
    
    ray = Ray(position=(0.5,10,0.5), direction=(0,-1,0))
    print fourbox.intersection(ray)

    ray = Ray(position=(0.5,10,2.5), direction=(0,-1,0))
    print fourbox.intersection(ray)

    print '\nSurface_ID for FourBox'
    print fourbox.surface_identifier((0.9,3,0.5))
    """

    """
    obj1 = Box(origin=(0,0,0), extent=(1,1,1))
    obj2 = Box(origin=(0,0,0), extent=(1,1,1))
    obj2.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
    obj2.append_transform(tf.translation_matrix((0.5,0,0)))

    add = CSGadd(obj1, obj2)
    
    ray = Ray(position=(0.50000000001,10,0.5), direction=(0,-1,0))
    print add.intersection(ray)
    """
    
    """
    # EXAMPLE THREE
    # Illustrates that if for example two boxes are joined at
    # one face with CSGadd, then none of the points on this face are
    # surface points (as should be for most of these points).
    # However, a ray that is contained in that face will
    # not return any intersection points with the CSGadd object
    # (which should not be for some points). 
    obj1 = Box(origin=(0,0,0), extent=(1,1,1))
    obj2 = Box(origin=(0,1,0), extent=(1,2,1))

    add = CSGadd(obj1, obj2)

    ray = Ray(position=(0.5,10,0.5), direction=(0,-1,0))

    print add.intersection(ray)

    print add.on_surface((0.5,1,0.5))
    print add.contains((0.5,1.,0.5))

    ray = Ray(position=(10,1,0.5), direction=(-1,0,0))

    print add.intersection(ray)
    """
    """
    # EXAMPLE FOUR: CSG VISUALISER

    INTone = Box(origin = (-1.,-1.,-0.), extent = (1,1,7))
    INTtwo = Box(origin = (-0.5,-0.5,0), extent = (0.5,0.5,7))
    #INTtwo.append_transform(tf.translation_matrix((0,0.5,0)))
    INTtwo.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
    MyObj = CSGsub(INTone, INTtwo)
    MyObj.append_name('myobj')
      
    

    vis=Visualiser()

    vis.VISUALISER_ON = True

    vis.addCSG(MyObj,0.03,-1,1,-1,1,0,10,visual.color.green)
    #vis.addCSG(MyObj, visual.color.blue)
    """
    """
    box1 = Box()
    box2 = Box(origin = (0.2,.2,0), extent = (0.8,0.8,1))
    csg = CSGsub(box1, box2)

    ray = Ray(position = (0.5,0.8,0.5), direction = (0,-1,0))

    normal = csg.surface_normal(ray, acute = False)
    print normal
    normal = csg.surface_normal(ray, acute = False)
    print normal  
    """

    
                    
                    
                
    
    
    
        

        

        
        
