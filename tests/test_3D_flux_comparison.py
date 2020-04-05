import pytest
import sys
import os
import numpy as np
import pandas as pd
from pvtrace import LSC, Distribution, rectangular_mask
from pvtrace.data import fluro_red


@pytest.fixture(scope='module')
def lsc():
    """ Compares an LSC simulation to 3D thermodynamic
        radiative transfer model
         
        A.J, Chatten et al. https://doi.org/10.1134/1.1787111
    
        Expected fractions:
        - edge = 0.25
        - escape = 0.66
        - loss = 0.09
    """
    x = np.arange(400, 801, dtype=np.float)
    size = (l, w, d) = (4.8, 1.8, 0.250)  # cm-1
    lsc = LSC(size, wavelength_range=x)

    lsc.add_luminophore(
        'Fluro Red',
        np.column_stack((x, fluro_red.absorption(x) * 11.387815)),  # cm-1
        np.column_stack((x, fluro_red.emission(x))),
        quantum_yield=0.95
    )
    
    lsc.add_absorber(
        'PMMA',
        0.02 # cm-1
    )
    
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
    
    throw = 300
    lsc.simulate(throw, emit_method='redshift')
    return lsc

@pytest.mark.skip(reason="Takes to long to include in unit general tests.")
def test_edge(lsc):
    incident = float(
        len(
            lsc.spectrum(
                source={"Oriel Lamp + Filter"},
                kind='first',
                facets={'top'}
            )
        )
    )
    edge = len(lsc.spectrum(facets={'left', 'right', 'near', 'far'}, source='all'))
    assert np.isclose(edge/incident, 0.25, atol=0.04)

@pytest.mark.skip(reason="Takes to long to include in unit general tests.")
def test_escape(lsc):
    incident = float(
        len(
            lsc.spectrum(
                source={"Oriel Lamp + Filter"},
                kind='first',
                facets={'top'}
            )
        )
    )
    escape = len(lsc.spectrum(facets={'top', 'bottom'}, source='all'))
    assert np.isclose(escape/incident, 0.64, atol=0.04)

@pytest.mark.skip(reason="Takes to long to include in unit general tests.")
def test_lost(lsc):
    incident = float(
        len(
            lsc.spectrum(
                source={"Oriel Lamp + Filter"},
                kind='first',
                facets={'top'}
            )
        )
    )
    lost = len(lsc.spectrum(source='all', events={'absorb'}))
    assert np.isclose(lost/incident, 0.11, atol=0.04)
