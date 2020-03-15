import numpy as np


def absorption(x):
    """ Fit to Lumogen F Red absorption coefficient spectrum using five Gaussians.
    
        Parameters
        ----------
        x : numpy.array
            Wavelength array in nanometers. This should take values in the optical 
            range between 200 and 900.

        Returns
        -------
        numpy.array
            The spectrum normalised to peak value of 1.0.

        Notes
        -----
        This fit is "good enough" for getting sensible answers but for research purposes
        you should be using your own data as this might not be exactly the same 
        spectrum as your materials.

        Example
        -------
        To make a absorption coefficient spectrum in the range 300 to 800 nanometers
        containing 200 points::

            spectrum = absorption(np.linspace(300, 800, 200))
    """
    spec = (
        0.9454846839252642
        * np.exp(-(((578.6167306868869 - x) / 22.69760939870020) ** 2))
        + 0.6430326869158796
        * np.exp(-(((535.1850303736512 - x) / 28.63029894331116) ** 2))
        + 0.1243340609168971
        * np.exp(-(((494.5721783546976 - x) / 13.98438275367119) ** 2))
        + 0.3651471532322375
        * np.exp(-(((440.4679754085741 - x) / 34.91923613222621) ** 2))
        + 0.7042787252835550
        * np.exp(-(((336.0548556730901 - x) / 34.24136755250487) ** 2))
    )
    spec = spec / np.max(spec)
    return spec


def emission(x):
    """ Fit to Lumogen F Red emission spectrum using a Gaussians.

        Parameters
        ----------
        x : numpy.array
            Wavelength array in nanometers. This should take values in the optical 
            range between 200 and 900.

        Returns
        -------
        numpy.array
            The spectrum normalised to peak value of 1.0

        Notes
        -----
        This fit is "good enough" for getting sensible answers but for research purposes
        you should be using your own data as this might not be exactly the same 
        spectrum as your materials.

        Example
        -------
        To make a emission spectrum in the range 300 to 800 nanometers containing 200 
        points::

            spectrum = emission(np.linspace(300, 800, 200))
    """
    spec = 1.0 * np.exp(-(((600.0 - x) / 38.60) ** 2))
    return spec
