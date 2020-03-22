""" This script compares pvtrace with experimental results and 3D thermodynamic model.

    It demonstrates how to:

    1. Add different dyes to the LSC
    2. Include constant background absorption coefficient
    3. Use a custom light source
        - Sample light source spectrum
        - Uniform illumination over the surface
        - Normal incidence
    4. After simulation plot spectra of rays exiting and entering surfaces.
"""
import logging
logging.getLogger('matplotlib').setLevel(logging.CRITICAL)
from pvtrace import *
import numpy as np
import matplotlib.pyplot as plt



# Simulation wavelength range
x = np.arange(400, 801, dtype=np.float)

# LSC plate size
size = (l, w, d) = (4.8, 1.8, 0.250)  # cm

# Make LSC model
lsc = LSC(size, wavelength_range=x)

# Use Fluro Red dye with peak absorption coefficient 11.39 cm-1
lsc.add_luminophore(
    'Fluro Red',
    np.column_stack((x, fluro_red.absorption(x) * 11.387815)),  # cm-1
    np.column_stack((x, fluro_red.emission(x))),
    quantum_yield=0.95
)

# Include constant background absorption coefficient of 0.02 cm-1
lsc.add_absorber(
    'PMMA',
    0.02 # cm-1
)

# This function returns an approximation of the lamp spectrum used in the experiment
def lamp_spectrum(x):
    """ Fit to an experimentally measured lamp spectrum with long wavelength filter.
    """
    def g(x, a, p, w):
        return a * np.exp(-(((p - x) / w)**2 ))
    a1 = 0.53025700136646192
    p1 = 512.91400020614333
    w1 = 93.491838802960473
    a2 = 0.63578999789955015
    p2 = 577.63100003089369
    w2 = 66.031706473985736
    return g(x, a1, p1, w1) + g(x, a2, p2, w2)

# Add a custon light
lamp_dist = Distribution(x, lamp_spectrum(x))
wavelength_callable = lambda : lamp_dist.sample(np.random.uniform())
position_callable = lambda : rectangular_mask(l/2, w/2)
lsc.add_light(
    "Oriel Lamp + Filter",
    (0.0, 0.0, 0.5 * d + 0.01),  # put close to top surface
    rotation=(np.radians(180), (1, 0, 0)),  # normal and into the top surface
    wavelength=wavelength_callable,  # wavelength delegate callable
    position=position_callable  # uniform surface illumination
)

lsc.show()  # makes things a bit slow
lsc.simulate(250)
lsc.report()

# Get luminescent wavelengths from edge
edge = lsc.spectrum(facets={'left', 'right', 'near', 'far'}, source={'Fluro Red'})

# Get luminescent wavelengths from top and bottom
escape = lsc.spectrum(facets={'top', 'bottom'}, source={'Fluro Red'})

# Get incident wavelengths into top surface
lost = lsc.spectrum(facets={'top'}, source="Oriel Lamp + Filter", kind='first')


plt.hist(edge, bins=np.arange(400, 800, 5), label="edge", histtype='step')
plt.hist(escape, bins=np.arange(400, 800, 5), label="escape",  histtype='step')
plt.hist(lost, bins=np.arange(400, 800, 5), label="lost",  histtype='step')
plt.xlabel('Wavelength (nm)')
plt.ylabel('#')
plt.title("Surface ray counts")
plt.grid(linestyle="dashed")
plt.show()
