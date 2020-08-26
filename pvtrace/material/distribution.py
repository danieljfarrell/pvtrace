from pvtrace.geometry.utils import allinrange
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Distribution(object):
    """Representation of a statistical distribution to aid in Monte Carlo sampling.
    """

    def __init__(self, x, y, hist=False):
        """ Initialise the distribution with (x, y) scatter data. 
        
            Parameters
            ----------
            x : array-like
                Will be treated as edges from the left edge include the
                right edge of the last bin.
            y : array-like
                Will be treated as vertex values at the bin edges.
            hist : bool
                If `True` the data will be treated as a histogram and 
                interpolation will not be used during sampling.
            
            Raises
            ------
            ValueError
                If x is not ascending or if any element of y is not finite.
        """
        self.hist = hist
        if x is None and isinstance(y, (float, np.float)):
            self._x = None
            self._y = y
        else:
            if not np.all(np.diff(x) > 0):
                raise ValueError("x must be sorted and ascending.")
            if not np.isfinite(y).any():
                raise ValueError("All values of y must be finite.")
            if np.any(y < 0.0):
                raise ValueError(
                    "Distributions are like histograms all counts must be positive."
                )

            self._x_range = np.min(x), np.max(x)
            self._x = x
            self._y = y
            if hist:
                cdf = np.cumsum(y, dtype=np.float)
                cdf *= 1.0 / cdf[-1]
                self._cdf = cdf
                self._edges = np.insert(x, x.size, 2 * x[-1] - x[-2])
            else:
                cdf = np.cumsum((y[:-1] + y[1:]) * 0.5)
                cdf = cdf / np.max(cdf)
                cdf = np.hstack([0.0, cdf])
                self._cdf = cdf

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
        if self._x is None and isinstance(self._y, (float, np.float)):
            if isinstance(x, (list, tuple, np.ndarray)):
                return np.zeros(len(x)) + self._y
            else:
                return self._y

        if not allinrange(x, self._x_range):
            raise ValueError("x is outside data range.", {"x": x, "x_range": self._x_range})

        if self.hist:
            idx = np.searchsorted(self._edges[:-1], x)
            return self._y[idx]
        else:
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
            raise ValueError("x is outside data range.", {"x": x, "x_range": self._x_range})

        if self.hist:
            idx = np.searchsorted(self._edges[:-1], x)
            return self._cdf[idx]
        else:
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

        if self.hist:
            idx = np.searchsorted(self._cdf, p)
            try:
                return self._x[idx]
            except IndexError:
                return self._x[-1]
        else:
            xval = np.interp(p, self._cdf, self._x, left=np.nan, right=np.nan)
            if xval.size == 1:
                xval = xval.tolist()  # actually a float
            return xval

    @classmethod
    def from_functions(cls, x, callables, hist=False):
        x = np.array(x)
        if len(x.shape) != 1:
            raise ValueError("Requires a 1D array.")
        y = np.zeros(len(x))
        for f in callables:
            y_ = f(x)
            y_[np.where(~np.isfinite(y_))] = 0.0
            y += y_
        return Distribution(x=x, y=y, hist=hist)
