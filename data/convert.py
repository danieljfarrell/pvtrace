import numpy as np
data = np.loadtxt("lr300.abs.txt")

# convert to energy spectrum, changes the spectral shape according to the 
# conservation of area. However, the resulting spectrum is normalised 
# back to the original height
# int f(L) dL = f(E) dE
# f(E)  =f(L) dL/dE
# L = hc/E hcE^-1
# dL/dE = -hc/E^2

def nm2eV(nm):
    return 1.9864454e-25 / (nm * 1e-9) * 6.2415097e+18

peak = data[:,1].max()
data[:,0] = nm2eV(data[:,0])
data[:,1] = data[:,1] * 1.9864454e-25 / data[:,0]**2
new_peak = data[:,1].max()
data[:,1] = peak/new_peak * data[:,1]
np.savetxt("lr300.abs.converted.txt", data)