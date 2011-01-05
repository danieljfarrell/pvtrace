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

try:
    import scipy as sp
    from scipy import interpolate
except Exception as exception:
    print exception
    try:
        print "SciPy not installed."
        import interpolate
    except Exception as exception:
        print exception
        print "It seems that you don't have interpolate... bugger... Python FAIL."

from Geometry import *
from ConstructiveGeometry import CSGadd, CSGint, CSGsub
from Interpolation import BilinearInterpolation
from types import *
import os
from external.transformations import translation_matrix, rotation_matrix
import external.transformations as tf

def load_spectrum(file, xbins=None):
    assert os.path.exists(file) == True, "File '%s' does not exist." % file
    xy = np.loadtxt(file)
    spectrum = Spectrum(file=file)
    
    # Truncate the spectrum using the xbins
    if xbins != None:
        yvalues = spectrum(xbins)
        return Spectrum(xbins, yvalues)
    return spectrum
    
def common_abscissa(a,b):
    la = len(a)
    lb = len(b)
    
    
    if la <= lb:
        tmp = a
        a = b
        b = tmp
        
    i = 0
    j = 0
    c = []
    
    while i < len(a):
        
        if a[i] < b[j]:
            c.append(float(a[i]))
            if i + 1 < len(a):
                i = i + 1
            else:
                break
        elif a[i] > b[j]:
            c.append(float(b[j]))
            if j + 1 < len(b):
                j = j + 1
            else:
                break
        else:
            #c.append(float(a[i]))
            i = i + 1
    return c

def wav2RGB(wavelength):
    """http://codingmess.blogspot.com/2009/05/conversion-of-wavelength-in-nanometers.html"""
    w = int(wavelength)
    
    # colour
    if w >= 380 and w < 440:
        R = -(w - 440.) / (440. - 350.)
        G = 0.0
        B = 1.0
    elif w >= 440 and w < 490:
        R = 0.0
        G = (w - 440.) / (490. - 440.)
        B = 1.0
    elif w >= 490 and w < 510:
        R = 0.0
        G = 1.0
        B = -(w - 510.) / (510. - 490.)
    elif w >= 510 and w < 580:
        R = (w - 510.) / (580. - 510.)
        G = 1.0
        B = 0.0
    elif w >= 580 and w < 645:
        R = 1.0
        G = -(w - 645.) / (645. - 580.)
        B = 0.0
    elif w >= 645 and w <= 780:
        R = 1.0
        G = 0.0
        B = 0.0
    else:
        R = 0.0
        G = 0.0
        B = 0.0
        
    # intensity correction
    if w >= 380 and w < 420:
        SSS = 0.3 + 0.7*(w - 350) / (420 - 350)
    elif w >= 420 and w <= 700:
        SSS = 1.0
    elif w > 700 and w <= 780:
        SSS = 0.3 + 0.7*(780 - w) / (780 - 700)
    else:
        SSS = 0.0
    SSS *= 255
    
    return [int(SSS*R), int(SSS*G), int(SSS*B)]


def fresnel_reflection(angle, n1, n2):
    assert 0.0 <= angle <= 0.5*np.pi, "The incident angle must be between 0 and 90 degrees to calculate Fresnel reflection."
    # Catch TIR case
    if n2 < n1:
        if angle > np.arcsin(n2/n1):
            return 1.0
    
    Rs1 = n1 * np.cos(angle) - n2 * np.sqrt(1 - (n1/n2 * np.sin(angle))**2)
    Rs2 = n1 * np.cos(angle) + n2 * np.sqrt(1 - (n1/n2 * np.sin(angle))**2)
    Rs = (Rs1/Rs2)**2
    Rp1 = n1 * np.sqrt(1 - (n1/n2 * np.sin(angle))**2) - n2 * np.cos(angle)
    Rp2 = n1 * np.sqrt(1 - (n1/n2 * np.sin(angle))**2) + n2 * np.cos(angle)
    Rp = (Rp1/Rp2)**2
    return 0.5 * (Rs + Rp)
    
def fresnel_reflection_with_polarisation(normal, direction, polarisation, n1, n2):
    # Catch TIR case
    if n2 < n1:
        if angle(normal, direction) > np.arcsin(n2/n1):
            return 1.0
    
    rads = angle(normal, direction)
    Rs1 = n1 * np.cos(rads) - n2 * np.sqrt(1 - (n1/n2 * np.sin(rads))**2)
    Rs2 = n1 * np.cos(rads) + n2 * np.sqrt(1 - (n1/n2 * np.sin(rads))**2)
    Rs = (Rs1/Rs2)**2
    Rp1 = n1 * np.sqrt(1 - (n1/n2 * np.sin(rads))**2) - n2 * np.cos(rads)
    Rp2 = n1 * np.sqrt(1 - (n1/n2 * np.sin(rads))**2) + n2 * np.cos(rads)
    Rp = (Rp1/Rp2)**2
    
    # Catch the normal incidence case
    if rads == 0.:
        # The reflection is independent of polarisation in this case
        return 0.5 * (Rs + Rp)
    
    # Calculate the weighting factor between TM (-p polarised) and TE (-s polarised) components
    # The normal vector of the plane of incidence
    n_p = norm(np.cross(direction, reflect_vector(normal, direction)))
    # Scalar magnitude of the projection of the polarisation vector on the the plane of incidence
    phi_p = np.sin(np.arccos(np.dot(n_p, norm(polarisation)))) 
    # i.e. how much of the electric field is in the plane of incidence
    return (1 - phi_p) * Rs + phi_p * Rp
    
def fresnel_refraction(normal, vector, n1, n2):
    n = n1/n2
    dot = np.dot(norm(vector), norm(normal))
    c = np.sqrt(1 - n**2 * (1 - dot**2))
    sign = 1
    if dot < 0.0:
        sign = -1
    refraction = n * vector + sign*(c - sign*n*dot) * normal
    return norm(refraction)
    
class Spectrum(object):
    """A class that represents a spectral quantity e.g. absorption, emission or refractive index spectrum as a funcion of wavelength in nanometers."""
        
    def __init__(self, x=None, y=None, file=None):
        super(Spectrum, self).__init__()
        """Initialised with x and y which are array-like data of the same length. x must have units of wavelength (that is in nanometers), y can an arbitrary units. However, if the Spectrum is representing an absorption coefficient y must have units of (1/m)."""
        
        if file != None:
            
            try:
                data = np.loadtxt(file)
            except Exception as e:
                print "Failed to load data from file, %s", str(file)
                print e
                exit(1)
            
            self.x = data[:,0]
            self.y = data[:,1]
        
        elif (x != None and y != None):
            self.x = np.array(x)
            self.y = np.array(y)
        
        else:
            # We need to make some data up -- i.e. flat over the full model range
            self.x = np.array([200, 500, 750, 4000])
            self.y = np.array([0, 0, 0, 0])
        
        
        if len(self.x) == 0:
            # We need to make some data up -- i.e. flat over the full model range
            self.x = np.array([200, 500, 750, 4000])
            self.y = np.array([0, 0, 0, 0])
            
        elif len(self.x) == 1:
            # We have a harder time at making up some data
            xval = self.x[0]
            yval = self.y[0]
            bins = np.arange(np.floor( self.x[0] - 1), np.ceil(self.x[0] + 2))
            indx = np.where(bins==xval)[0][0]
            self.x = np.array(bins)
            self.y = np.zeros(len(self.x))
            self.y[indx] = yval
        
        # Make the 'spectrum'
        self.spectrum = interpolate.interp1d(self.x, self.y, bounds_error=False, fill_value=0.0)
        
        # Make the pdf for wavelength lookups
        try:
            # Convert the (x,y) point pairs to a histogram of bins and frequencies
            bins = np.hstack([self.x, 2*self.x[-1] - self.x[-2]])
        except IndexError:
            print "Index Error from array, ", self.x
        
        cdf  = np.cumsum(self.y)
        pdf  = cdf/max(cdf)
        pdf  = np.hstack([0,pdf[:]])
        self.pdf_lookup = interpolate.interp1d(bins, pdf, bounds_error=False, fill_value=0.0)
        self.pdfinv_lookup = interpolate.interp1d(pdf, bins, bounds_error=False, fill_value=0.0)
    
    def __call__(self, nanometers):
        """Returns the values of the Spectrum at the 'nanometers' value(s). An number is returned if nanometers is a number and numpy array is returned if nanometers if a list of a numpy array."""
        # Check is the nanometers is a number
        b1 = type(nanometers) == FloatType
        b2 = type(nanometers) == IntType
        b3 = type(nanometers) == np.float32
        b4 = type(nanometers) == np.float64
        b5 = type(nanometers) == np.float128
        if b1 or b2 or b3 or b4 or b5:
            return np.float(self.value(nanometers))
        return self.value(nanometers)
    
    def value(self, nanometers):
        '''Returns the value of the spectrum at the specified wavelength (if the wavelength is outside the data range zero is returned)'''
        return self.spectrum(nanometers)
    
    def probability_at_wavelength(self, nanometers):
        '''Returns the probability associated with the wavelength. This is found my computing the cumulative probabililty funcion of the spectrum which is unique for each value for each non-zero y values. If the wavelength is below the data range zero is returned, and if above one is returned.'''
        if (nanometers > self.x.max()):
            return 1.0
        else:
            return self.pdf_lookup(nanometers)
    
    def wavelength_at_probability(self, probability):
        '''Returns the wavelength associated with the specified probability. This is found my computing the inverse cumulative probabililty function (see probability_at_wavelength). The probabililty must be between zero and one (inclusive) otherwise a value error exception is raised.'''
        if (0 <= probability <= 1):
            return self.pdfinv_lookup(probability)
        else:
            raise ValueError('A probability must be between 0 and 1 inclusive')
    
    def write(self, file=None):
        if file != None:
            data = np.zeros((len(self.x),2))
            data[:,0] = self.x
            data[:,1] = self.y
            np.savetxt(file,data)
            
    def __add__(self, other):
        if other == None:
            return self
        common_x = common_abscissa(self.x, other.x)
        new_y = self.value(common_x) + other.value(common_x)
        return Spectrum(common_x, new_y)
        
    def __sub__(self, other):
        if other == None:
            return self
        common_x = common_abscissa(self.x, other.x)
        new_y = self.value(common_x) - other.value(common_x)
        return Spectrum(common_x, new_y)  
        
    def __mul__(self, other):
        if other == None:
            return self
        common_x = common_abscissa(self.x, other.x)
        new_y = self.value(common_x) * other.value(common_x)
        return Spectrum(common_x, new_y)
      
    def __div__(self, other):
        if other == None:
            return self
        common_x = common_abscissa(self.x, other.x)
        new_y = self.value(common_x) / other.value(common_x)
        return Spectrum(common_x, new_y)        

class AngularSpectrum(object):
    """
    A spectrum with an angular dependence.
    >>> x = np.array([400.,600.,601,1000.])
    >>> y = np.array([0., np.pi/4, np.pi/2])
    >>> z = np.array([[0.,0.,0.],      [1e-9,1e-9,1e-9],     [1-1e-9,1-1e-9,1-1e-9],  [1.,1.,1.]])
    >>> z_i = BilinearInterpolation(x,y,z)
    >>> z_i(610,0.1) == 0.99999999902255665
    True
    
    """
    def __init__(self, x, y, z):
        super(AngularSpectrum, self).__init__()
        self.x = x
        self.y = y
        self.z = z
        self.spectrum = BilinearInterpolation(x, y, z, fill_value=0.0)
    
    def value(self, nanometers, radians):
        return self.spectrum(nanometers, radians)
    
class Material(object):
    """A material than can absorb and emit photons objects. A photon is absorbed if a pathlength generated by sampling the Beer-Lambert Law for the photon is less than the pathlength to escape the container. The emission occurs weighted by the quantum_efficiency (a probabililty from 0 to 1). The emission wavelength must occur at a red-shifted value with respect to the absorbed photon. This is achieved by samping the emission spectrum from the photons wavelength upwards. The direction of the emitted photon is choosen uniformally from an isotropic distribution of angles."""
    
    def __init__(self, absorption_data=None, constant_absorption=None, emission_data=None, quantum_efficiency=0.0, refractive_index=1.0):
        """The required arguments are the absorption_spectrum (a Spectrum object, with units 1/m/nm) and an emission_spetrum (a Spectrum object with units 1/nm). The quantum_efficiency is an optional argument with is the probablilty of emission. If quantum_efficiency is set to 0.0 the emission_spectrum is discarded and set to None."""
        
        super(Material, self).__init__()
        
        # --- 
        def spectrum_from_data_source(data_source):
            
            if isinstance(data_source, str):
                if os.path.isfile(data_source):
                    data = np.loadtxt(data_source)
                    return Spectrum(x=data[:,0], y=data[:,1])
                else:
                    raise IOError("File '%s' does not exist at this location, '%s' .") % (os.path.basename(data_source), data_source)
            
            # Data is 'list-like'
            elif isinstance(data_source, list) or isinstance(data_source, tuple) or isinstance(data_source, np.ndarray):
                
                rows, cols = np.shape(data_source)
                assert rows > 1, "Error processing the data file '%s'. PVTrace data files need at least 2 rows and must have 2 columns. This data file has %d rows and %d columns." % (data_source, rows, cols)
                assert cols == 2, "Error processing the data file '%s'. PVTrace data files need at least 2 rows and must have 2 columns. This data file has %d rows and %d columns." % (data_source, rows, cols)
                return Spectrum(x=data_source[:,0], y=data_source[:,1])
            
            # Data is already a spectrum
            elif isinstance(data_source, Spectrum):
                return data_source
            
            else:
                raise IOError("PVTrace cannot process %s input given to the Material object. Please use the location of a text file (UTF-8 format) which contains spectral data as 2 columns of increasing wavelength (col#1 is the wavelength; col#2 is data).")
        
        # --- 
        
        
        
        # Load absorption data
        if constant_absorption != None:
            # Load linear background absorption
            self.constant_absorption = constant_absorption
            self.absorption_data = Spectrum(x=[200,4000], y=[constant_absorption, constant_absorption])
            
        elif absorption_data == None:
            # No data given -- make transparent material
            self.absorption_data = Spectrum(x=[0, 4000], y=[0, 0])
        
        else:
           self.absorption_data = spectrum_from_data_source(absorption_data)
        
        # Load spectral emission data
        if emission_data == None:
            # Flat emission profile
            self.emission_data = Spectrum(x=[200,4000], y=[1,1])
            
        else:
            self.emission_data = spectrum_from_data_source(emission_data)
        
        # Load quantum efficiency
        assert 0 <= quantum_efficiency <= 1, "Quantum efficiency is  outside the 0 to 1 range."
        self.quantum_efficiency = quantum_efficiency
        
        # Load refractive index
        assert refractive_index >= 1, "Refractive index is less than 1.0"
        self.refractive_index = refractive_index
    
    def absorption(self, photon):
        """Returns the absorption coefficient experienced by the photon."""
        return self.absorption_data.value(photon.wavelength)
    
    def emission_direction(self):
        """Returns a 3 component direction vector with is choosen isotropically. 
        NB. This method is overridden by subclasses to provide custom emission 
        direction properties."""
        
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
        
    def emission_wavelength(self, photon):
        """Returns a new emission wavelength for the photon."""
        # The emitted photon must be red-shifted to consevration of energy
        lower_bound = self.emission_data.probability_at_wavelength(photon.wavelength)
        return self.emission_data.wavelength_at_probability(np.random.uniform(lower_bound,1.))
        
    def emission(self, photon):
        """Updates the photon with a new wavelength and direction, assuming it has been absorbed and emitted."""
        
        # Update wavelength
        photon.wavelength = self.emission_wavelength(photon)
        
        # Update direction
        photon.direction = self.emission_direction()
        return photon
        
    def trace(self, photon, free_pathlength):
        '''Will apply absorption and emission probabilities to the photon along its free path in the present geometrical container and return the result photon for tracing. The free_pathlength is the distance travelled in metres until the photon reaches the edge of the present container. It is for the calling object to decided how to proceed with the returned photon. For example, if the returned photon is in the volume of the container the same tracing procedure should be applied. However, if the photon reaches a face, reflection, refraction calculation should be applied etc. If the photon is lost, the photons active instance variables is set to False. It is for the calling object to check this parameter and act accordingly e.g. recording the lost photon and great a new photon to trace.'''
        
        # Assuming the material has a uniform absorption coefficient we generated a random path length weigthed by the material absorption coefficient.
        sampled_pathlength = -np.log(1 - np.random.uniform())/self.absorption(photon)
        
        # Photon absorbed.
        if (sampled_pathlength < free_pathlength):
            
            # Move photon to the absorption location
            photon.material = self
            photon.position = photon.position + sampled_pathlength * photon.direction
            photon.absorption_counter = photon.absorption_counter + 1
            
            # Photon emitted.
            if (np.random.uniform() < self.quantum_efficiency):
                photon.reabs = photon.reabs + 1
                return self.emission(photon)
                
            # Photon not emitted.
            else:
                photon.active = False
                return photon
                
        # Photon not absorbed
        else:
            # Move photon along path
            photon.position = photon.position + free_pathlength * photon.direction
            return photon

class CompositeMaterial(Material):
    """A material that is composed from a homogeneous mix of multiple materials. For example, a plastic plate doped with a blue and red absorbing dyes has the absorption coefficient of plastic as well as the absorption and emission properties of the dyes."""
    def __init__(self, materials, refractive_index=1.5):
        '''Initalised by a list or array of material objects.'''
        super(CompositeMaterial, self).__init__()
        self.materials = materials
        self.refractive_index = refractive_index
    
    def all_absorption_coefficients(self, nanometers):
        '''Returns and array of all the the materials absorption coefficients at the specified wavelength.'''
        count = len(self.materials)
        absorptions = np.zeros(count)
        for i in range(0, count):
            absorptions[i] = self.materials[i].absorption_data.value(nanometers)
        return absorptions
    
    def trace(self, photon, free_pathlength):
        '''Will apply absorption and emission probabilities to the photon along its free path in the present geometrical container and return the result photon for tracing. See help(material.trace) for how this is done for a single material because the same principle applies. The ensemble absorption coefficient is found for the specified photon to determine if absorption occurs. The absorbed material its self is found at random from a distrubution weighted by each of the component absorption coefficients. The resultant photon is returned with possibily with a new position, direction and wavelength. If the photon is absorbed and not emitted the photon is retuned but its active property is set to False. '''
        
        absorptions = self.all_absorption_coefficients(photon.wavelength)
        absorption_coefficient = absorptions.sum()
        sampled_pathlength = -np.log(1 - np.random.uniform())/absorption_coefficient
        
        #Absorption occurs.
        if (sampled_pathlength < free_pathlength):
            # Move photon along path to the absorption point
            photon.absorption_counter = photon.absorption_counter + 1
            photon.position = photon.position + sampled_pathlength * photon.direction
            
            # Find the absorption material
            count = len(self.materials)
            bins = range(0, count+1)
            cdf  = np.cumsum(absorptions)
            pdf  = cdf/max(cdf)
            pdf  = np.hstack([0,pdf[:]])
            pdfinv_lookup = interpolate.interp1d(pdf, bins, bounds_error=False, fill_value=0.0)
            absorber_index = int(np.floor(pdfinv_lookup(np.random.uniform())))
            material = self.materials[absorber_index]
            photon.material = material
            self.emission = material.emission
            self.absorption = material.absorption
            self.quantum_efficiency = material.quantum_efficiency
            
            
            #Emission occurs.
            if (np.random.uniform() < material.quantum_efficiency):
                print "   * Re-emitted *"
                photon.reabs = photon.reabs + 1
                photon = material.emission(photon) # Generates a new photon with red-shifted wavelength, new direction and polariation (if included in simulation)
                return photon
                
            else:
                print "   * Photon Lost *"
                #Emission does not occur. Now set active = False ans return
                photon.active = False
                return photon
                
        else:
            
            #Absorption does not occur. The photon reaches the edge, update it's position and return
            photon.position = photon.position + free_pathlength * photon.direction
            return photon
            
        
class ReflectiveMaterial(object):
    """A Material that reflects photons rather an absorbing photons.

    reflectivity: Spectrum or AngularSpectrum object that defines the
    material reflectivity (i.e. zero to one) over the wavelength 
    range (in nanometers).
    """
    def __init__(self, reflectivity, refractive_index=1.):
        super(ReflectiveMaterial, self).__init__()
        self.reflectivity = reflectivity
        self.refractive_index = refractive_index
    
    def trace(self, photon, normal, free_pathlength):
        """Move the photon one Monte-Carlo step forward by considering material reflections."""
        
        # Absorption is not defined for this material (we assume dielectrics)
        # Therefore is random number is less than reflectivty: photon reflected.
        
        if isinstance(self.reflectivity, Spectrum):
            R = self.reflectivity.value(photon.wavelength)
        if isinstance(self.reflectivity, AngularSpectrum):
            # DJF 8/5/2010
            # 
            # The internal incident angle (substate-coating) will not correspond to the same value of 
            # reflectivity as for the same angle and the external interface (air-coatings) because the 
            # refraction angle into the material will be different. We need to apply a correction factor
            # to account for this effect (see Farrell PhD Thesis, p.129, 2009)
            #
            # If the previous containing object's (i.e. this will be the substate for an internal 
            # collision, or air if an external collision) has a refractive index higher than air
            # (n_air = photon.scene.bounds.material.refractive_index) then the correction is applied,
            # else the photon must be heading into an external interface and no correction is needed.
            #
            if photon.previous_container.material.refractive_index > photon.scene.bounds.material.refractive_index:
                # Hitting internal interface, therefore apply correction to angle
                n_substrate = photon.previous_container.material.refractive_index
                n_environment = photon.scene.bounds.material.refractive_index
                rads = np.asin(n_substrate/n_environment * sin( angle(normal, photon.direction) ))
            else:
                rads = angle(normal, photon.direction)
                
            R = self.reflectivity.value(photon.wavelength, rads)
        else:
            R = self.reflectivity
        
        rn = np.random.uniform()
        if rn < R:
            # Reflected
            photon.direction = reflect_vector(normal, photon.direction)
        else:
            photon.position = photon.position + free_pathlength * photon.direction
        return photon

def hemispherical_vector():
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
    return np.array([x,y,abs(z)])

class DiffuseReflectiveMaterial(object):
    """A Material that reflects diffusively rather an absorbing photons.
    
    reflectivity: Spectrum or AngularSpectrum object that defines the
    material reflectivity (i.e. zero to one) over the wavelength 
    range (in nanometers).
    """
    def __init__(self, reflectivity, refractive_index=1.):
        super(DiffuseReflectiveMaterial, self).__init__()
        self.reflectivity = reflectivity
        self.refractive_index = refractive_index
        
    def trace(self, photon, normal, free_pathlength):
        """Move the photon one Monte-Carlo step forward by considering material reflections."""
        
        # Absorption is not defined for this material (we assume dielectrics)
        # Therefore if random number is less than reflectivty: photon reflected.
        
        if isinstance(self.reflectivity, Spectrum):
            R = self.reflectivity.value(photon.wavelength)
        if isinstance(self.reflectivity, AngularSpectrum):
            rads = angle(normal, photon.direction)
            R = self.reflectivity.value(photon.wavelength, rads)
            
        rn = np.random.uniform()
        if rn < R:
            # SANDY:
            # CHANGE THIS LINE SO THAT RATHER THAN HAVE SPECULAR REFLECTION YOU 
            # HAVE ISOTROPIC REFLECTION OVER A HEMISPHERE WITH THE 'NORMAL' 
            # VECTOR AT THE CENTRE.
            photon.direction = hemispherical_vector()
        else:
            photon.position = photon.position + free_pathlength * photon.direction
        return photon

class SimpleMaterial(Material):
    """SimpleMaterial is a subclass of Material. It simply implements a material with a square absorption and emission spectra that sligtly overlap. The absorption coefficient is set to 10 per metre."""
    def __init__(self, bandgap_nm):
        self.bandgap = bandgap_nm
        absorption_coefficient = 0.0
        absorption = Spectrum([0, bandgap_nm-50, bandgap_nm], [absorption_coefficient, absorption_coefficient, 0.0])
        emission = Spectrum([bandgap_nm-50, bandgap_nm , bandgap_nm + 50.], [0, 1, 0])
        super(SimpleMaterial, self).__init__(absorption_data=absorption, emission_data=emission, quantum_efficiency=1.0, refractive_index=1.0)

class SimpleMaterial2(Material):
    """SimpleMaterial is a subclass of Material. It simply implements a material with a square absorption and a triangular emission spectra that slightly overlapping. The absorption coefficient is set to 10 per metre."""
    def __init__(self, bandgap_nm):
       self.bandgap = bandgap_nm
       absorption_coefficient = 2
       absorption = Spectrum([0, bandgap_nm], [absorption_coefficient, absorption_coefficient])
       Eg = bandgap_nm
       y = [0,1,0]
       x = [Eg-50, Eg-40, Eg]
       emission = Spectrum(x,y)
       super(SimpleMaterial2, self).__init__(absorption_data=absorption, emission_data=emission, quantum_efficiency=1.0, refractive_index=1.0)


if __name__ == "__main__":
    import doctest
    doctest.testmod()

