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
from external.transformations import translation_matrix, rotation_matrix
import external.transformations as tf
from Geometry import *
from Materials import *
from ConstructiveGeometry import CSGadd, CSGint, CSGsub
import warnings

class Register(object):
    """
    A class that will register photon position and wavelength. Device objects are subclasses of register.
    """
    def __init__(self):
        super(Register, self).__init__()
        self.store = dict()
        # Dictionary whose keys are surface_identifiers. The items are 
        # arrays where each index is an tuples containing ray statistics 
        # as indicated in the log function.
    
    def log(self, photon):        
        
        # Need to check that the photon is on the surface
        #import pdb; pdb.set_trace()
        if not self.shape.on_surface(photon.position):
                                    
            if photon.active == False:
                
                # The photon has been non-radiatively lost inside a material
                key = 'loss'
                if not self.store.has_key(key):
                    self.store[key] = []
                    
                log_entry = (list(photon.position), float(photon.wavelength), None, photon.absorption_counter)
                self.store[key].append(log_entry)
                if photon.show_log: print '   Logged as lost photon...'
                return
            else:
                #A photon has been logged in the interior of a material but photon.active = True, which means it is no non-radiatively lost. So why is it being logged?"
                warnings.warn("It is likely that a light source has been placed inside an object. Normally the light sources should be external. Now attempting to log the ray and continue.")
                key = 'volume_source'
                if not self.store.has_key(key):
                    self.store[key] = []
                log_entry = (list(photon.position), float(photon.wavelength), None, photon.absorption_counter)
                self.store['volume_source'].append(log_entry)
                if photon.show_log: print 'Logged as photon from a volume source...'
                return
        
        # Can do this because all surface_normal with the acute flag False returns outwards facing normals.
        normal = photon.exit_device.shape.surface_normal(photon.ray, acute=False)
        rads = angle(normal, photon.ray.direction)
        if rads < np.pi/2:
            # Ray facing outwards
            bound = "outbound"
        else:
            # Ray facing inwards
            bound = "inbound"

        if photon.show_log: print '   Logged as ', bound, '...'
        
        key = photon.exit_device.shape.surface_identifier(photon.position)
        if not self.store.has_key(key):
            # Add an item for this key.
            self.store[key] = []
        
        # [0] --> position
        # [1] --> wavelength
        # [2] --> boundedness (inbound or outbound)
        # [3] --> re-absorptions
        # [4] --> total jumps
        # [5] --> object_number
        log_entry = (list(photon.position), float(photon.wavelength), bound, photon.absorption_counter)     
        self.store[key].append(log_entry)
    
    def count(self, shape, surface_point, bound):
        """
        Returns the number of photon counts that are on the 
        same surface as the surface_point for the given shape.
        """
        
        key = shape.surface_identifier(surface_point)
        if not self.store.has_key(key):
            return 0.0
        counts = None
        entries = self.store[key]
        counts = 0
        for entry in entries:
            if entry[2] == bound:
                counts = counts + 1
        
        if counts == None:
            return 0
        return counts
    
    def loss(self):
        """
        Returns the number of photons that have been non-radiatively lost in the volume of the shape. 
        A more adventurous version of this could be made that returns positions. 
        """
        if not self.store.has_key('loss'):
            return 0
        return len(self.store['loss'])
        
    def spectrum(self, shape, surface_point, bound):
        """Returns the counts histogram (bins,counts) for """
        
        wavelengths = []
        key = shape.surface_identifier(surface_point)
        if not self.store.has_key(key):
            return None
        
        entries = self.store[key]
        if len(entries) == 0:
            return None
        
        for entry in entries:
            if entry[2] == bound:
                wavelengths.append(float(entry[1]))
        
        if len(wavelengths) is 0:
            return None
        
        wavelengths = np.array(wavelengths)
        min = wavelengths.min()
        max = wavelengths.max()
        
        if len(wavelengths) is 1:
            bins = np.arange(np.floor( wavelengths[0] - 1), np.ceil(wavelengths[0] + 2))
            freq, bins  = np.histogram(wavelengths, bins=bins)
        else:
            bins = np.arange(np.floor( wavelengths.min()-1), np.ceil(wavelengths.max()+2))
            freq, bins  = np.histogram(wavelengths, bins=bins)
        return Spectrum(bins[0:-1], freq)
    

    def reabs(self, shape, surface_point, bound):
        """
        16/03/10: Returns list where list[i+1] contains number of surface photons that experienced i re-absorptions;
        Length of list is ten by default (=> photons with up to 9 re-absorptions recorded), but is extended if necessary.        
        """
        key = shape.surface_identifier(surface_point)
        
        if not self.store.has_key(key):
            return [0,0,0,0,0,0,0,0,0,0]

        reabs_list = [0,0,0,0,0,0,0,0,0,0]

        key_entries = self.store[key]

        for entry in key_entries:

            if entry[2] == bound:
                number_reabs = entry[3]

                # In case reabs_list is not sufficiently long...
                if number_reabs+1 > len(reabs_list):
                    while len(reabs_list) < number_reabs+1:
                        reabs_list.append(0)

                reabs_list[number_reabs] = reabs_list[number_reabs] + 1
                          
        return reabs_list

    def loss_reabs(self):
        """
        16/03/10: Returns list where list[i+1] contains number of LOST photons that experienced i re-absorptions;
        Length of list is ten by default (=> photons with up to 9 re-absorptions recorded), but is extended if necessary.        
        """

        if not self.store.has_key('loss'):
            return [0,0,0,0,0,0,0,0,0,0]

        reabs_list = [0,0,0,0,0,0,0,0,0,0]

        loss_entries = self.store['loss']

        for entry in loss_entries:

            number_reabs = entry[3]
            
            if number_reabs+1 > len(reabs_list):
                while len(reabs_list) < number_reabs+1:
                    reabs_list.append(0)

            reabs_list[number_reabs] = reabs_list[number_reabs] + 1

        return reabs_list                            
  
        
        
class Detector(Register):
    """An abstract class to base solar cell like object from. Similar to the register class but will deactive photon when then hit."""
    def __init__(self):
        super(Detector, self).__init__()

class SimpleCell(Detector):
    """A SimpleCell object is a solar cell with perfect AR coating."""
    def __init__(self, finiteplane):
        super(Detector, self).__init__()
        self.shape = finiteplane
        self.name = "cell"
        self.material = None

class Coating(Register):
    """
       Overview:
       A coating device is a shape that contains a reflective material which may 
       have an spectral and angular dependent reflectivity.
       
       Details:
       When a ray hits an object, the Fresnel equation are used to determine if
       the ray continues on it's path or is reflected. Coatings are special
       objects that supply there own reflectivity, and may also define 
       Rather than using Fresnel equation to determine the reflectivity of 
       
       """
    def __init__(self, reflectivity=None, shape=None, refractive_index=1.5):
        super(Coating, self).__init__()
        self.reflectivity = reflectivity
        self.refractive_index = refractive_index
        self.shape = shape
        self.name = "COATING"
        self.material = ReflectiveMaterial(reflectivity, refractive_index=refractive_index)
        if not isinstance(self.shape, Polygon):
            self.origin = self.shape.origin
            self.size = np.abs(self.shape.extent - self.shape.origin)

class Bounds(Register):
    """A huge box containing only air with refractive index 1."""
    def __init__(self):
        super(Bounds, self).__init__()
        self.shape = Box(origin=(-5,-5,-5), extent=(5,5,5))
        self.material = Material()
        self.name = "BOUNDS"

class Rod(Register):
    """docstring for Rod"""
    def __init__(self, bandgap=555, radius=1, length=1):
        super(Rod, self).__init__()
        self.shape = Cylinder(radius, length)
        self.material = SimpleMaterial(bandgap)

class Prism(Register):
    """Prism"""
    def __init__(self, bandgap=555, base=1, alpha=np.pi/3, beta=np.pi/3, length=1):
        super(Prism, self).__init__()
        h = base*(1/np.tan(alpha) + 1/np.tan(alpha))
        box0 = Box(origin=(0,0,0), extent=(base,h,length))
        box1 = Box(origin=(0,0,0), extent=(h/np.sin(alpha),h,length))
        box1.append_transform(trans.rotation_matrix(alpha, (0,0,1)))
        box2 = Box(origin=(base,0,0), extent=(base+h,h/np.sin(beta),h,length))
        box2.append_transform(trans.rotation_matrix(np.pi/2-beta, (0,0,1)))
        step1 = CSGsub(box0, box1)
        step2 = CSGsub(step1, box2)
        self.shape = step2
        self.material = SimpleMaterial(bandgap)

class LSC(Register):
    """LSC implementation."""
    def __init__(self, bandgap=555, origin=(0,0,0), size=(1,1,1)):
        super(LSC, self).__init__()
        self.origin = np.array(origin)
        self.size = np.array(size)
        self.shape = Box(origin=origin, extent=np.array(origin) + np.array(size))
        self.material = SimpleMaterial(bandgap)
        self.name = "LSC"

        """
        16/03/10: Assume that surfaces with a solar cell attached are index matched. This makes
        sure that all surfaces that hit one of the collection edges are counted.
        e.g. index_matched_surfaces = ['top', 'bottom']
        """
        self.index_matched_surfaces = []

class Collector(Register):
    """Collector implementation."""
    def __init__(self, bandgap=555, origin=(0,0,0), size=(1,1,1)):
        super(Collector, self).__init__()
        self.origin = np.array(origin)
        self.size = np.array(size)
        self.shape = Box(origin=origin, extent=np.array(origin) + np.array(size))
        self.material = SimpleMaterial(bandgap)
        self.name = "LSC"

class RayBin(Collector):
    """An class for erasing the ray if it hits this device. --> e.g. a solar cell!"""
    def __init__(self, bandgap=555, origin=(0,0,0), size=(1,1,1)):
        super(RayBin, self).__init__()
        self.origin = np.array(origin)
        self.size = np.array(size)
        self.shape = Box(origin=origin, extent=np.array(origin) + np.array(size))
        self.material = SimpleMaterial(bandgap)
        self.name = "RayBin"

class PlanarMirror(Register):
    """Planar mirror with variable reflectivity (constant or wavelength dependent but constant in angle). """
    def __init__(self, reflectivity=1.0, origin=(0,0,0), size=(1,1,0.001) ):
        super(PlanarMirror, self).__init__()
        self.reflectivity = reflectivity
        self.shape = Box(origin=np.array(origin), extent=np.array(origin) + np.array(size))
        self.material = ReflectiveMaterial(reflectivity)

class Face(Register):
    """General 2D object for ray tracing surfaces."""
    def __init__(self, reflectivity=1.0, transmittance=-1, shape=Polygon([(0,0,0), (1,0,0), (1,1,0), (0,1,0)])):
        super(Face, self).__init__()
        assert reflectivity + transmittance < 1, "reflectivity + transmittance of Face device must be smaller than 1.0"
        self.reflectivity = reflectivity
        #if reflectivity -> ray reflected, if transmittance -> ray goes straight through, else: ray lost
        if transmittance < 0:
            self.transmittance = 1 - self.reflectivity
        else:
            self.transmittance = transmittance
        self.shape = shape
        self.material = None
        self.name = "FACE"

