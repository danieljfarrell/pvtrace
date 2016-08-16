from __future__ import division
import numpy as np
import sys
import os
import time
sys.path.append(os.getcwd() + "\\pvtrace")
PVTDATA = os.getcwd() + "\\pvtrace\\data"
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

#-----------------------------------------------------------------------------#
#------------------------- Testing with visualiser?? -------------------------#
# Reset cores = 1
# Visualiser = True
testing = False

#-------------- Enter number of cores for parallelised simulations -----------#
# make sure throws/cores == integer
# putting testing=True will reset the number of cores to 1 further down the script.
# If a core has hyperthreading abilities, it counts as 2 cores.
cores=4
#-----------------------------------------------------------------------------#

# Introduce number of photons in simulations
throws = 40

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


#-----------------------------------------------------------------------------#
# --------------------------- Start the raytracer --------------------------- #
if __name__ == "__main__":
    pwd = os.getcwd()

    if testing: # Use this to check that the setup is correct by using visualiser
        cores = 1
        timestring = time.strftime("%H%M%S")
        dbfile = os.path.join(pwd, timestring+"homogen_thread_%i" + ".sql") # <--- temporary database file uses a timestring for naming to remove the need to constantly delete it before re-running the test
        use_visualiser = True
        throws = 200
    else: # Visualiser slows down the simulation, so visualiser should be switched off
        dbfile = os.path.join(pwd, "homogen_thread_%i" + ".sql") # <--- sub-sim database files
        use_visualiser = False

    dbfinal = os.path.join(pwd, 'homogen_merged.sql') # <--- merged database file

        
    trace = Tracer(scene=scene, source=source, steps = 5000, seed=None, throws=throws, database_file=dbfile, use_visualiser=use_visualiser, show_log=False, combined_database_file = dbfinal, parts=cores)
       
    trace.show_lines = True
    trace.show_path = True

    start_time=time.time()
    tic = time.clock()

    # This is where pvtrace is initiated
    if cores == 1: #single core simulation
        trace.start()
    else: # parallelised simulation
        trace.ppstart(cores)
      
    print "time taken = ", time.time() - start_time, "s"   
    toc = time.clock()
    print " "

