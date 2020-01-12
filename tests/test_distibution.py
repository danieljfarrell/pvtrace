import pytest
import numpy as np
from pvtrace.material.distribution import Distribution
from pvtrace.material.utils import bandgap, thermodynamic_emission


class TestDistribution:
    
    def test_sample_range(self):
        x = np.linspace(400, 1010, 2000)
        abs_spec = np.column_stack((x, bandgap(x, 600, 1000)))
        ems_spec = thermodynamic_emission(abs_spec, T=300, mu=0.1)
        dist = Distribution(ems_spec[:, 0], ems_spec[:, 1])
        xmin = dist.sample(0)
        assert np.isclose(xmin, x.min())
        xmax = dist.sample(1)
        assert np.isclose(xmax, x.max())
        y_at_xmin = dist.lookup(xmin)
        assert np.isclose(y_at_xmin, 0.0)
        y_at_xmax = dist.lookup(xmax)
        assert np.isclose(y_at_xmin, 0.0)

    def test_step_sample(self):
        """ Sampling a step function should only return two value.
        """
        nmedge = 600.0
        nmmin, nmmax = (400.0, 800.0)
        spacing = 1.0
        x = np.arange(nmmin, nmmax + spacing, spacing)
        abs_spec = np.column_stack((x, bandgap(x, nmedge, 1.0)))  # ends a mid range.
        dist = Distribution(abs_spec[:, 0], abs_spec[:, 1], hist=True)
        xmin = dist.sample(0)
        assert np.isclose(xmin, nmmin)
        xmax = dist.sample(1)  # The probabiliity of getting a value > nmedge is zero
        assert np.isclose(xmax, nmedge)
        pmin = dist.lookup(nmmin)
        pmax = dist.lookup(nmmax)
        assert pmin >= 0.0 and pmin <= dist.lookup(nmmin+spacing)
        assert pmax == 1.0
        values = dist.sample(np.linspace(dist.lookup(599-spacing), dist.lookup(600+spacing), 10000))
        assert len(set(values)) == 3
        
