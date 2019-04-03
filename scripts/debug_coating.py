import numpy as np
import pvtrace
from pvtrace.external import transformations as tf
from pvtrace import *

#Create light source from AM1.5 data, truncate to 400 -- 800nm range

file = os.path.join(PVTDATA,'sources','AM1.5g-full.txt')
oriel = load_spectrum(file, xbins=np.arange(300,1600))
source = PointSource(spectrum=oriel, center=(0,0,0.08), phimin =0, phimax =2*np.pi, thetamin =0.5*np.pi, thetamax =np.pi)

#Load dye absorption and emission data
file = os.path.join(PVTDATA, 'dyes', 'fluro-red.abs.txt')
abs = load_spectrum(file)
file = os.path.join(PVTDATA, 'dyes', 'fluro-red-fit.ems.txt')
ems = load_spectrum(file)

#Make the LSC

lsc = Rod(radius=0.01,length=0.05)
new_transform= tf.translation_matrix([0.05, 0.1, 0])
lsc.name = "LSC"
lsc.material = Material(absorption_data=abs, emission_data=ems, quantum_efficiency=0.5, refractive_index=1.3)
lsc.name = "LSC"

scene = Scene()
scene.add_object(lsc)

# Coating
shape = Cylinder(radius=0.011,length=0.05)
coating = Coating(reflectivity=0.5, shape=shape)
coating.name= "tape"
scene.add_object(coating)

# Ask python that the directory of this script file is and use it as the location of the database file
pwd = os.getcwd()
dbfile = os.path.join(pwd, 'debugcoating.sql') # <--- the name of the database file
if os.path.exists(dbfile):
    os.remove(dbfile)
trace = Tracer(scene=scene, source=source, seed=1, throws=300, database_file=dbfile, use_visualiser=True, show_log=False)
trace.show_lines = True
trace.show_path = True
import time
tic = time.clock()
trace.start()
toc = time.clock()

# 6) Statistics
print("")
print("Run Time: ", toc - tic)
print("")

print("Technical details:")
generated = len(trace.database.uids_generated_photons())
killed = len(trace.database.killed())
thrown = generated - killed
print("\t Generated \t", generated)
print("\t Killed \t", killed)
print("\t Thrown \t", thrown)

print("Summary:")
print("\t Optical efficiency \t", (len(trace.database.uids_out_bound_on_surface('left', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('right', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('near', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('far', luminescent=True))) * 100 / thrown, "%")
print("\t Photon efficiency \t", (len(trace.database.uids_out_bound_on_surface('left')) + len(trace.database.uids_out_bound_on_surface('right')) + len(trace.database.uids_out_bound_on_surface('near')) + len(trace.database.uids_out_bound_on_surface('far')) + len(trace.database.uids_out_bound_on_surface('top')) + len(trace.database.uids_out_bound_on_surface('bottom'))) * 100 / thrown, "%")

print("Luminescent photons:")
edges = ['left', 'near', 'far', 'right']
apertures = ['top', 'bottom']

for surface in edges:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%")

for surface in apertures:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%")

print("\t", len(trace.database.uids_nonradiative_losses())/thrown * 100, "%")

print("Solar photons (transmitted/reflected):")
for surface in edges:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%")

for surface in apertures:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%")