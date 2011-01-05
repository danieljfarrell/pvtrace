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

import numpy as np
from external.transformations import translation_matrix, rotation_matrix
import external.transformations as tf
from Trace import Photon
from Geometry import Box, Cylinder, FinitePlane, transform_point, transform_direction, rotation_matrix_from_vector_alignment, norm
from Materials import Spectrum

def random_spherecial_vector():
    # This method of calculating isotropic vectors is taken from GNU Scientific Library
    LOOP = True
    while LOOP:
        x = -1. + 2. * np.random.uniform()
        y = -1. + 2. * np.random.uniform()
        s = x**2 + y**2
        if s <= 1.0:
            LOOP = False
            
    z = -1. + 2. * s
    a = 2 * np.sqrt(1 - s)
    x = a * x
    y = a * y
    return np.array([x,y,z])
        
class SimpleSource(object):
    """A light source that will generate photons of a single colour, direction and position."""
    def __init__(self, position=[0,0,0], direction=[0,0,1], wavelength=555, use_random_polarisation=False):
        super(SimpleSource, self).__init__()
        self.position = position
        self.direction = direction
        self.wavelength = wavelength
        self.use_random_polarisation = use_random_polarisation
        self.throw = 0
        self.source_id = "SimpleSource_" + str(id(self))
        
        
    def photon(self):
        
        photon = Photon()
        photon.source = self.source_id
        photon.position = np.array(self.position)
        photon.direction = np.array(self.direction)
        photon.active = True
        photon.wavelength = self.wavelength
        
        # If use_polarisation is set generate a random polarisation vector of the photon
        if self.use_random_polarisation:
            
            # Randomise rotation angle around xy-plane, the transform from +z to the direction of the photon
            vec = random_spherecial_vector()
            vec[2] = 0.
            vec = norm(vec)
            R = rotation_matrix_from_vector_alignment(self.direction, [0,0,1])
            photon.polarisation = transform_direction(vec, R)
            
        else:
            photon.polarisation = None
        
        photon.id = self.throw
        self.throw = self.throw + 1 
        return photon

class Laser(object):
    """A light source that will generate photons of a single colour, direction and position."""
    
    def __init__(self, position=[0,0,0], direction=[0,0,1], wavelength=555, polarisation=None):
        super(Laser, self).__init__()
        self.position = np.array(position)
        self.direction = np.array(direction)
        self.wavelength = wavelength
        assert polarisation != None, "Polarisation of the Laser is not set."
        self.polarisation = np.array(polarisation)
        self.throw = 0
        self.source_id = "LaserSource_" + str(id(self))
        
        
    def photon(self):
        
        photon = Photon()
        photon.source = self.source_id
        photon.position = np.array(self.position)
        photon.direction = np.array(self.direction)
        photon.active = True
        photon.wavelength = self.wavelength
        photon.polarisation = self.polarisation
        photon.id = self.throw
        self.throw = self.throw + 1 
        return photon
        
class PlanarSource(object):
    """A box that emits photons from the top surface (normal), sampled from the spectrum."""
    def __init__(self, spectrum=None, wavelength=555, direction=(0,0,1), length=0.05, width=0.05):
        super(PlanarSource, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.plane = FinitePlane(length=length, width=width)
        self.length = length
        self.width = width
        # direction is the direction that photons are fired out of the plane in the GLOBAL FRAME.
        # i.e. this is passed directly to the photon to set is's direction
        self.direction = direction
        self.throw = 0
        self.source_id = "PlanarSource_" + str(id(self))
    
    def translate(self, translation):
        self.plane.append_transform(tf.translation_matrix(translation))
    
    def rotate(self, angle, axis):
        self.plane.append_transform(tf.rotation_matrix(angle, axis))
    
    def photon(self):
        photon = Photon()
        photon.source = self.source_id
        photon.id = self.throw
        self.throw = self.throw + 1 
        # Create a point which is on the surface of the finite plane in it's local frame
        x = np.random.uniform(0., self.length)
        y = np.random.uniform(0., self.width)
        local_point = (x, y, 0.)
        
        # Transform the direciton
        photon.position = transform_point(local_point, self.plane.transform)
        photon.direction = self.direction
        photon.active = True
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())
        else:
            photon.wavelength = self.wavelength
        return photon

class LensSource(object):
    """
    A source where photons generated in a plane are focused on a line with space tolerance given by variable "focussize".
    The focus line should be perpendicular to the plane normal and aligned with the z-axis. 
    """
    def __init__(self, spectrum = None, wavelength = 555, linepoint=(0,0,0), linedirection=(0,0,1), focussize = 0, planeorigin = (-1,-1,-1), planeextent = (-1,1,1)):
        super(LensSource, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.planeorigin = planeorigin
        self.planeextent = planeextent
        self.linepoint = np.array(linepoint)
        self.linedirection = np.array(linedirection)
        self.focussize = focussize
        self.throw = 0
        self.source_id = "LensSource_" + str(id(self))

    def photon(self):
        photon = Photon()
        photon.source = self.source_id
        photon.id = self.throw
        self.throw = self.throw + 1 
        
        # Position
        x = np.random.uniform(self.planeorigin[0],self.planeextent[0])
        y = np.random.uniform(self.planeorigin[1],self.planeextent[1])
        z = np.random.uniform(self.planeorigin[2],self.planeextent[2])
        photon.position = np.array((x,y,z))        
        
        # Direction
        focuspoint = np.array((0.,0.,0.))        
        focuspoint[0] = self.linepoint[0] + np.random.uniform(-self.focussize,self.focussize)
        focuspoint[1] = self.linepoint[1] + np.random.uniform(-self.focussize,self.focussize)
        focuspoint[2] = photon.position[2] 
        
        direction = focuspoint - photon.position
        modulus = (direction[0]**2+direction[1]**2+direction[2]**2)**0.5
        photon.direction = direction/modulus
        
        # Wavelength
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())
        else:
            photon.wavelength = self.wavelength
            
        return photon   


class LensSourceAngle(object):
    """
    A source where photons generated in a plane are focused on a line with space tolerance given by variable "focussize".
    The focus line should be perpendicular to the plane normal and aligned with the z-axis. 
    For this lense an additional z-boost is added (Angle of incidence in z-direction).
    """
    def __init__(self, spectrum = None, wavelength = 555, linepoint=(0,0,0), linedirection=(0,0,1), angle = 0, focussize = 0, planeorigin = (-1,-1,-1), planeextent = (-1,1,1)):
        super(LensSourceAngle, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.planeorigin = planeorigin
        self.planeextent = planeextent
        self.linepoint = np.array(linepoint)
        self.linedirection = np.array(linedirection)
        self.focussize = focussize
        self.angle = angle
        self.throw = 0
        self.source_id = "LensSourceAngle_" + str(id(self))
        
    def photon(self):
        photon = Photon()
        
        photon.id = self.throw
        self.throw = self.throw + 1 
        
        # Position
        x = np.random.uniform(self.planeorigin[0],self.planeextent[0])
        y = np.random.uniform(self.planeorigin[1],self.planeextent[1])
        boost = y*np.tan(self.angle)
        z = np.random.uniform(self.planeorigin[2],self.planeextent[2]) - boost
        photon.position = np.array((x,y,z))        
        
        # Direction
        focuspoint = np.array((0.,0.,0.))        
        focuspoint[0] = self.linepoint[0] + np.random.uniform(-self.focussize,self.focussize)
        focuspoint[1] = self.linepoint[1] + np.random.uniform(-self.focussize,self.focussize)
        focuspoint[2] = photon.position[2] + boost
        
        direction = focuspoint - photon.position
        modulus = (direction[0]**2+direction[1]**2+direction[2]**2)**0.5
        photon.direction = direction/modulus
        
        # Wavelength
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())
        else:
            photon.wavelength = self.wavelength
            
        return photon   
    

class CylindricalSource(object):
    """
    A source for photons emitted in a random direction and position inside a cylinder(radius, length)
    """
    def __init__(self, spectrum = None, wavelength = 555, radius = 1, length = 10):
        super(CylindricalSource, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.shape = Cylinder(radius = radius, length = length)
        self.radius = radius
        self.length = length
        self.throw = 0
        self.source_id = "CylindricalSource_" + str(id(self))
                
    def translate(self, translation):
        self.shape.append_transform(tf.translation_matrix(translation))

    def rotate(self, angle, axis):
        self.shape.append_transform(tf.rotation_matrix(angle, axis))

    def photon(self):
        photon = Photon()
        photon.source = self.source_id
        photon.id = self.throw
        self.throw = self.throw + 1 
        
        # Position of emission
        phi = np.random.uniform(0., 2*np.pi)
        r = np.random.uniform(0.,self.radius)        
        
        x = r*np.cos(phi)
        y = r*np.sin(phi) 
        z = np.random.uniform(0.,self.length)
        local_center = (x,y,z)
        
        photon.position = transform_point(local_center, self.shape.transform)
        
        
        # Direction of emission (no need to transform if meant to be isotropic)
        phi = np.random.uniform(0.,2*np.pi)
        theta = np.random.uniform(0.,np.pi)
        
        x = np.cos(phi)*np.sin(theta)
        y = np.sin(phi)*np.sin(theta)
        z = np.cos(theta)
        local_direction = (x,y,z)
        
        photon.direction = local_direction
        
        # Set wavelength of photon
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())        
        else:
            photon.wavelength = self.wavelength
            
        # Further initialisation
        photon.active = True
        
        return photon

class PointSource(object):
    """
    A point source that emits randomly in solid angle specified by phimin, ..., thetamax
    """
    def __init__(self, spectrum = None, wavelength = 555, center = (0.,0.,0.), phimin = 0, phimax = 2*np.pi, thetamin = 0, thetamax = np.pi):
        super(PointSource, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.center = center
        self.phimin = phimin
        self.phimax = phimax
        self.thetamin = thetamin
        self.thetamax = thetamax
        self.throw = 0
        self.source_id = "PointSource_" + str(id(self))

    def photon(self):
        photon = Photon()
        photon.source = self.source_id
        photon.id = self.throw
        self.throw = self.throw + 1
        
        phi = np.random.uniform(self.phimin, self.phimax)
        theta = np.random.uniform(self.thetamin, self.thetamax)
        
        x = np.cos(phi)*np.sin(theta)
        y = np.sin(phi)*np.sin(theta)
        z = np.cos(theta)
        direction = (x,y,z)
        
        transform = tf.translation_matrix((0,0,0))
        point = transform_point(self.center, transform)
        
        photon.direction = direction
        photon.position = point
        
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())
        else:
            photon.wavelength = self.wavelength
            
        photon.active = True
        
        return photon

class RadialSource(object):
    """
    A point source that emits at discrete angles theta(i) and phi(i)
    """
    def __init__(self, spectrum = None, wavelength = 555, center = (0.,0.,0.), phimin = 0, phimax = 2*np.pi, thetamin = 0, thetamax = np.pi, spacing=20):
        super(RadialSource, self).__init__()
        self.spectrum = spectrum
        self.wavelength = wavelength
        self.center = center
        self.phimin = phimin
        self.phimax = phimax
        self.thetamin = thetamin
        self.thetamax = thetamax
        self.spacing = spacing
        self.throw = 0
        self.source_id = "RadialSource_" + str(id(self))

    def photon(self):
        photon = Photon()
        
        photon.source = self.source_id
        photon.id = self.throw
        self.throw = self.throw + 1
        
        intphi = np.random.randint(1, self.spacing+1)        
        inttheta = np.random.randint(1, self.spacing+1)
        
        phi = intphi*(self.phimax-self.phimin)/self.spacing
        if self.thetamin == self.thetamax:
            theta = self.thetamin
        else:
            theta = inttheta*(self.thetamax-self.thetamin)/self.spacing
        
        x = np.cos(phi)*np.sin(theta)      
        y = np.sin(phi)*np.sin(theta) 
        z = np.cos(theta)
        direction = (x,y,z)
        
        transform = tf.translation_matrix((0,0,0))
        point = transform_point(self.center, transform)
        
        photon.direction = direction
        photon.position = point
        
        if self.spectrum != None:
            photon.wavelength = self.spectrum.wavelength_at_probability(np.random.uniform())
        else:
            photon.wavelength = self.wavelength
            
        photon.active = True
        
        return photon
