import numpy as np
from scipy.special import erf

def absorption(x):
    """ Fit to Coumarin Fluro Red absorption coefficient spectrum using four Gaussians.
    
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
    p1 = 549.06438843562137
    a1 = 439.06754804626956
    w1 = 24.298601639828647
    
    p2 = 379.48645797468572
    a2 = 85.177292848284353
    w2 = 13.513987279089216
    
    p3 = 519.58858977131513
    a3 = 660.1731296017241
    w3 = 38.263352007649125
    
    p4 = 490.05625608592726
    a4 = 511.11501615291041
    w4 = 52.213294432464529
    spec = (
        a1 * np.exp(-(((p1 - x) / w1) ** 2))
        + a2 * np.exp(-(((p2 - x) / w2) ** 2))
        + a3 * np.exp(-(((p3 - x) / w3) ** 2))
        + a4 * np.exp(-(((p4 - x) / w4) ** 2))
    )
    spec = spec / np.max(spec)
    return spec


def emission(x):
    """ Fit to Coumarin Fluro Red emission spectrum using an exponentially modified 
        Gaussian.

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
    def emg(x, a, b, c, d):
        r2 = np.sqrt(2)
        return a * c * np.sqrt(2 * np.pi) / (2 * d) * \
            np.exp((c**2/(2*d**2))-((x-b)/d)) * \
            (d/np.abs(d) + erf((x - b)/(r2*c) - c/(r2*d)))
    
    a = 1.1477763237584664
    b = 592.06478874548839
    c = 19.981040318195117
    d = 12.723704058786568
    spec = emg(x, a, b, c, d)
    return spec

if __name__ == '__main__':
    import matplotlib.pyplot as plt
    x = np.arange(200, 900)
    plt.plot(x, absorption(x), label="absorption")
    plt.plot(x, emission(x), label="emission")
    plt.grid(linestyle='dashed')
    plt.show()
