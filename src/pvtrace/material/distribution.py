from pvtrace.common.errors import AppError
from pvtrace.geometry.utils import allinrange
import numpy as np
import logging
logger = logging.getLogger(__name__)


class Distribution(object):
    """Representation of a statistical distribution to aid in Monte Carlo sampling.
    """

    def __init__(self, x, y):
        """ Initialise the distribution with (x, y) scatter data. 
        
            Parameters
            ----------
            x : array-like
                Will be treated as edges from the left edge include the
                right edge of the last bin.
            y : array-like
                Will be treated as vertex values at the bin edges.
            
            Raises
            ------
            ValueError
                If x is not ascending or if any element of y is not finite.
        """
        if not np.all(np.diff(x) > 0):
            raise ValueError("x must be sorted and ascending.")
        if not np.isfinite(y).any():
            raise ValueError("All values of y must be finite.")

        self._x = x
        self._y = y
        cdf = np.cumsum((y[:-1] + y[1:])*0.5)
        cdf = cdf/np.max(cdf)
        cdf = np.hstack([0.0, cdf])
        self._cdf = cdf
        self._x_range = np.min(x), np.max(x)

    def __call__(self, x):
        """ Returns a linearly interpolated value of the distribution at x.
            
            Parameters
            ----------
            x : array-like or float
                x-values for which you want to know the corresponding y-values
                of the distribution.
            
            Raises
            ------
            ValueError
                If x is outside the data range.
        """
        if not allinrange(x, self._x_range):
            raise ValueError("x is outside data range.")

        y = np.interp(x, self._x, self._y, left=np.nan, right=np.nan)
        return y

    def lookup(self, x):
        """ Returns the probability from the cumulative distribution function 
            corresponding to the value x.
        
            Parameters
            ----------
            x : array-like or float
                The x-value must be in the data range.
            
            Returns
            -------
            prob : array-like or float
                The corresponding probability of the value.

            Raises
            ------
            ValueError
                If any element of x is not inside the data range.
            
            Example
            -------
            This method is useful is you need to truncate the distribution 
            before sampling. For example::
            
                import numpy as np
                import matplotlib.pyplot as plt
                x = np.linspace(0, 200, 200)
                y = np.exp(-((x - 50.0)/20)**2)
                dist = Distribution(x, y)
                p1 = dist.lookup(40.0)
                p2 = dist.lookup(80.0)
                draw = dist.sample(np.random.uniform(p1, p2, 10000))
                plt.hist(draw)

        """
        if not allinrange(x, self._x_range):
            raise ValueError("x is outside data range.")
        
        prob = np.interp(x, self._x, self._cdf, left=np.nan, right=np.nan)
        if prob.size == 1:
            prob = prob.tolist()  # actually a float
        return prob

    def sample(self, p):
        """ Returns the value corresponding to the probability from the cumulative
            distribution function.
            
            Parameters
            ----------
            p : array-like or float
                The probability value, must be between 0 and 1.
            
            Returns
            -------
            xval : array-like or float
                The corresponding x-value.
            
            Raises
            ------
            ValueError
                If p is outside the range [0, 1].
            
            Example
            -------
            Use this method to sample the distribution with randoms numbers. For
            example::
            
                import numpy as np
                import matplotlib.pyplot as plt
                x = np.linspace(0, 200, 200)
                y = np.exp(-((x - 50.0)/20)**2)
                dist = Distribution(x, y)
                drawn = dist.sample(np.random.uniform(0, 1, 10000))
                plt.hist(drawn)
        """
        if not allinrange(p, (0.0, 1.0)):
            raise ValueError("p is outside valid range.")

        xval = np.interp(p, self._cdf, self._x, left=np.nan, right=np.nan)
        if xval.size == 1:
            xval = xval.tolist()  # actually a float
        return xval

