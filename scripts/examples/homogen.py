from __future__ import division
import numpy as np
import pvtrace
from pvtrace.external import transformations as tf
from pvtrace import *

''' Simulation of a rectangular homogeneously doped LSC

Steps:
1) Define sizes
2) Create a light source
3) Load absorption and emission data for orgnaic dye
4) Load linear background absorption for PMMA
5) Create LSC object and start tracer
6) Calculate statistics.

'''

# 1) Define some sizes
L = 0.05
W = 0.05
H = 0.0025

# 2) Create light source from AM1.5 data, truncate to 400 -- 800nm range
file = os.path.join(PVTDATA,'sources','AM1.5g-full.txt')
oriel = load_spectrum(file, xbins=np.arange(400,800))
source = PlanarSource(direction=(0,0,-1), spectrum=oriel, length=L, width=W) # Incident light AM1.5g spectrum
source.translate((0,0,0.05))

# 3) Load dye absorption and emission data, and create material
file = os.path.join(PVTDATA, 'dyes', 'fluro-red.abs.txt')
abs = load_spectrum(file)
file = os.path.join(PVTDATA, 'dyes', 'fluro-red-fit.ems.txt')
ems = load_spectrum(file)
fluro_red = Material(absorption_data=abs, emission_data=ems, quantum_efficiency=0.95, refractive_index=1.5)

# 4) Give the material a linear background absorption (pmma)
abs = Spectrum([0,1000], [2,2])
ems = Spectrum([0,1000], [0,0])
pmma = Material(absorption_data=abs, emission_data=ems, quantum_efficiency=0.0, refractive_index=1.5)

# 5) Make the LSC and give it both dye and pmma materials
lsc = LSC(origin=(0,0,0), size=(L,W,H))
lsc.material = CompositeMaterial([pmma, fluro_red], refractive_index=1.5)
lsc.name = "LSC"
scene = Scene()
scene.add_object(lsc)

# Ask python that the directory of this script file is and use it as the location of the database file
pwd = os.getcwd()
dbfile = os.path.join(pwd, 'homogen_db2.sql') # <--- the name of the database file

trace = Tracer(scene=scene, source=source, seed=1, throws=250, database_file=dbfile, use_visualiser=True, show_log=False)
trace.show_lines = True
trace.show_path = True
import time
tic = time.clock()
trace.start()
toc = time.clock()

# 6) Statistics
print ""
print "Run Time: ", toc - tic
print ""

print "Technical details:"
generated = len(trace.database.uids_generated_photons())
killed = len(trace.database.killed())
thrown = generated - killed
print "\t Generated \t", generated
print "\t Killed \t", killed
print "\t Thrown \t", thrown

print "Summary:"
print "\t Optical efficiency \t", (len(trace.database.uids_out_bound_on_surface('left', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('right', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('near', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('far', luminescent=True))) * 100 / thrown, "%"
print "\t Photon efficiency \t", (len(trace.database.uids_out_bound_on_surface('left')) + len(trace.database.uids_out_bound_on_surface('right')) + len(trace.database.uids_out_bound_on_surface('near')) + len(trace.database.uids_out_bound_on_surface('far')) + len(trace.database.uids_out_bound_on_surface('top')) + len(trace.database.uids_out_bound_on_surface('bottom'))) * 100 / thrown, "%"

print "Luminescent photons:"
edges = ['left', 'near', 'far', 'right']
apertures = ['top', 'bottom']

for surface in edges:
    print "\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%"

for surface in apertures:
    print "\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%"

print "\t", len(trace.database.uids_nonradiative_losses())/thrown * 100, "%"

print "Solar photons (transmitted/reflected):"
for surface in edges:
    print "\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%"

for surface in apertures:
    print "\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%"



