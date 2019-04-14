import numpy as np
import pvtrace
from pvtrace.external import transformations as tf
from pvtrace import *

#Create light source from AM1.5 data, truncate

L=0.02
W=0.05

file = os.path.join(PVTDATA,'sources','AM1.5g-full.txt')
oriel = load_spectrum(file, xbins=np.arange(300,600))
#source = PlanarSource(direction=(0,0,-1), spectrum=oriel, length=L, width=W) # Incident light AM1.5g spectrum
#source.translate((0.0, 0.0, 0.1))
hull_source = SimpleSource(position=[0, 0.02, 0.025], direction=[0,-1,0], wavelength=555)
base_source = SimpleSource(position=[0, 0.0, -0.05], direction=[0,0,1], wavelength=555)
cap_source = SimpleSource(position=[0, 0.0, 0.05], direction=[0,0,-1], wavelength=555)


#Load dye absorption and emission data, and create material
file = os.path.join(PVTDATA, 'dyes', 'lr300.abs.txt')
abs = load_spectrum(file)
file = os.path.join(PVTDATA, 'dyes', 'lr300.ems.txt')
ems = load_spectrum(file)
fluro_red = Material(absorption_data=abs, emission_data=ems, quantum_efficiency=1.00, refractive_index=1.5)

#Give the material a linear background absorption (pmma)
abs = Spectrum([0,1000], [0,0])
ems = Spectrum([0,1000], [0,0])
pmma = Material(absorption_data=abs, emission_data=ems, quantum_efficiency=0.0, refractive_index=1.5)

#Make the LSC

lsc = Rod(radius=0.01,length=0.05)
new_transform= tf.translation_matrix([0.00, 0.0, 0])
lsc.name = "LSC"
lsc.material = CompositeMaterial([pmma, fluro_red], refractive_index=1.5)
lsc.name = "LSC"

scene = Scene()
scene.add_object(lsc)

#Ask python that the directory of this script file is and use it as the location of the database file
pwd = os.getcwd()
dbfile = os.path.join(pwd, 'cylinder.sql') # <--- the name of the database file
if os.path.exists(dbfile):
    os.remove(dbfile)
print(cap_source)
trace = Tracer(scene=scene, source=hull_source, seed=1, throws=1, database_file=dbfile, use_visualiser=True, show_log=False)
trace.show_lines = True
trace.show_path = True
import time
tic = time.clock()
trace.start()
toc = time.clock()

#Statistics
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
print("\t Optical efficiency \t", (len(trace.database.uids_out_bound_on_surface('cap', luminescent=True)) + len(trace.database.uids_out_bound_on_surface('base', luminescent=True))) * 100 / thrown, "%")
print("\t Photon efficiency \t", (len(trace.database.uids_out_bound_on_surface('cap')) + len(trace.database.uids_out_bound_on_surface('base')) + len(trace.database.uids_out_bound_on_surface('hull'))) * 100 / thrown, "%")

print("Luminescent photons:")
edges = ['hull']
apertures = ['cap', 'base']

for surface in edges:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%")

for surface in apertures:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, luminescent=True))/thrown * 100, "%")

print("\t", "Losses", len(trace.database.uids_nonradiative_losses())/thrown * 100, "%")

print("Solar photons (transmitted/reflected):")
for surface in edges:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%")

for surface in apertures:
    print("\t", surface, "\t", len(trace.database.uids_out_bound_on_surface(surface, solar=True))/thrown * 100, "%")
