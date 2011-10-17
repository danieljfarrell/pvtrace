from __future__ import division
import numpy as np
from pvtrace import *
from pvtrace.external import transformations as tf


scene = Scene()
L = 0.05
W = 0.05
D = 0.001
S = 0.01
T = 0.0001
lsc = LSC(origin=(0,0,S), size=(L,W,T))
absorption_data = np.loadtxt(os.path.join(PVTDATA,"dyes", "lr300.abs.txt"))
T_need = 0.05 # Want to transmit 5% of the light at the peak absorption wavelength
ap = absorption_data[:,1].max()
phi = -1/(ap*(T)) * np.log(T_need)
absorption_data[:,1] = absorption_data[:,1]*phi
print "Absorption data scaled to peak, ", absorption_data[:,1].max()
print "Therefore transmission at peak = ", np.exp(-absorption_data[:,1].max() * T)

absorption = Spectrum(x=absorption_data[:,0], y=absorption_data[:,1])
emission_data = np.loadtxt(os.path.join(PVTDATA,"dyes", "lr300.ems.txt"))
emission = Spectrum(x=emission_data[:,0], y=emission_data[:,1])
linbackgrd = Material(absorption_data=Spectrum(x=[300.,1000.], y=[0.3,0.3]), refractive_index = 1.5, quantum_efficiency=0.)
dopant = Material(absorption_data=absorption, emission_data=emission, quantum_efficiency=.95, refractive_index=1.5)
lsc.material = CompositeMaterial([linbackgrd, dopant])
lsc.name = "FILM"
film = lsc
scene.add_object(film)

lsc = LSC(origin=(0,0,S+T), size=(L,W,D))
lsc.material = linbackgrd
lsc.name = "SUBSTRATE"
substrate = lsc
scene.add_object(substrate)

source = SimpleSource(position=(L/2, W/2, -0.01), direction=(0,0,1), wavelength=555)
#oriel = np.loadtxt("../data/sources/oriel-fit.lamp.txt")
#oriel = Spectrum(oriel[:,0], oriel[:,1])
#oriel = oriel.value(np.arange(400,800))
#oriel = Spectrum(np.arange(400,800), oriel)
#source = PlanarSource(direction=(0,0,1), spectrum=oriel, length=L, width=W)

trace = Tracer(scene=scene, source=source, seed=None, throws=10000, use_visualiser=True)
trace.show_lines = True
trace.show_path = True
trace.start()


