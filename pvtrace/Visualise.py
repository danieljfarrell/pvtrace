# pvtrace is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# 
# pvtrace is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


VISUAL_INSTALLED = False

try:
    # Import VPython 6
    import visual
    VISUAL_INSTALLED = True
except ImportError:
    print("Module visual is not installed.")

try:
    # Import VPython 7
    import vpython as visual
    VISUAL_INSTALLED = True
except ImportError:
    print('Module vpython is not installed.')

if not VISUAL_INSTALLED:
    print("No visualisation installed. Will not render scene.")

import numpy as np
from pvtrace.Geometry import Box, Sphere, FinitePlane, Polygon, Convex, Ray, Cylinder, transform_point, transform_direction, norm
from pvtrace import ConstructiveGeometry as csg
from pvtrace.external import transformations as tf

norm = lambda x: x

class Visualiser (object):
    """Visualiser a class that converts project geometry objects into vpython objects and draws them. It can be used programmatically: just add objects as they are created and the changes will update in the display."""
    VISUALISER_ON = True
    if not VISUAL_INSTALLED:
        VISUALISER_ON = False
    
    def __init__(self, background=(0,0,0), ambient=1.):
        super(Visualiser, self).__init__()
        if not Visualiser.VISUALISER_ON:
            return
        #self.display = visual.display(title='pvtrace', x=0, y=0, width=800, height=600, background=(0.957, 0.957, 1), ambient=0.5)
        #self.display.exit = False
        visual.curve(pos=[visual.vec(0,0,0), visual.vec(.2,0,0)], radius=0.001, color=visual.color.red)
        visual.curve(pos=[visual.vec(0,0,0), visual.vec(0,.2,0)], radius=0.001, color=visual.color.green)
        visual.curve(pos=[visual.vec(0,0,0), visual.vec(0,0,.2)], radius=0.001, color=visual.color.blue)
        visual.label(pos=visual.vec(.22, 0, 0), text='X', linecolor=visual.color.red)
        visual.label(pos=visual.vec(0, .22, 0), text='Y', linecolor=visual.color.green)
        visual.label(pos=visual.vec(0, 0, .22), text='Z', linecolor=visual.color.blue)
        
    
    def addBox(self, box, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(box, Box):
            if colour is None:
                colour = visual.color.red
            
            org = transform_point(box.origin, box.transform)
            ext = transform_point(box.extent, box.transform)
            print("Visualiser: box origin=%s, extent=%s" % (str(org), str(ext)))
            size = np.abs(ext - org)
            
            pos = org + 0.5*size
            print("Visualiser: box position=%s, size=%s" % (str(pos), str(size)))
            angle, direction, point = tf.rotation_from_matrix(box.transform)
            print("colour,", colour)
            pos = visual.vec(*pos.tolist())
            size = visual.vec(*size.tolist())

            try:
                colour = visual.vec(*colour)
            except:
                pass

            #visual.box(pos=pos, size=size, opacity=opacity, color=None)
            visual.box(pos=pos, size=size, color=colour, opacity=opacity)
    
    def addSphere(self, sphere, colour=None, opacity=1.):
        """docstring for addSphere"""
        if not Visualiser.VISUALISER_ON:
            return
        
        if isinstance(sphere, Sphere):
            if colour == None:
                colour = visual.color.red
            if np.allclose(np.array(colour), np.array([0,0,0])):
                visual.sphere(pos=visual.vec(sphere.centre), radius=sphere.radius, opacity=opacity)
            else:
                visual.sphere(pos=visual.vec(sphere.centre), radius=sphere.radius, color=norm(colour), opacity=opacity)
            
    def addFinitePlane(self, plane, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(plane, FinitePlane):
            if colour == None:
                colour = visual.color.blue
            # visual doesn't support planes, so we draw a very thin box
            H = .001
            pos = (plane.length/2, plane.width/2, H/2)
            pos = transform_point(pos, plane.transform)
            size = (plane.length, plane.width, H)
            axis = transform_direction((0,0,1), plane.transform)
            visual.box(pos=visual.vec(pos), size=size, color=colour, opacity=opacity)

    def addPolygon(self, polygon, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(polygon, Polygon):
            if colour == None:
                visual.convex(pos=polygon.pts, color=norm([0.1,0.1,0.1]))
            else:
                visual.convex(pos=polygon.pts, color=norm(colour))
    
    def addConvex(self, convex, colour=None, opacity=1.):
        """docstring for addConvex"""
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(convex, Convex):
            if colour == None:
                print("Color is none")
                visual.convex(pos=convex.points, color=norm([0.1,0.1,0.1]))
            else:
                #import pdb; pdb.set_trace()
                print("Colour is", norm(colour))
                visual.convex(pos=convex.points, color=norm(colour))
                
    def addRay(self, ray, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(ray, Ray):
            if colour == None:
                colour = visual.color.white
            pos = ray.position
            axis = ray.direction * 5
            visual.cylinder(pos=pos, axis=axis, radius=0.0001, color=norm(colour), opacity=opacity)
    
    def addSmallSphere(self, point, colour=None, opacity=1.0):
        if not Visualiser.VISUALISER_ON:
            return
        if colour is None:
            colour = visual.color.blue
        try:
            colour = visual.vec(*colour)
        except TypeError:
            pass
        point = tuple(point)
        pos = visual.vec(*point)
        visual.sphere(pos=pos, radius=0.00012, color=norm(colour), opacity=opacity)
        #visual.curve(pos=[point], radius=0.0005, color=norm(colour))
        
        
    def addLine(self, start, stop, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if colour is None:
            colour = visual.color.white
        colour = visual.vec(*colour)
        axis = np.array(stop) - np.array(start)
        axis = visual.vec(*axis.tolist())
        start = visual.vec(*tuple(start))
        visual.cylinder(pos=start, axis=axis, radius=0.0001, color=norm(colour), opacity=opacity)
    
    def addCylinder(self, cylinder, colour=None, opacity=1.):
        if not Visualiser.VISUALISER_ON:
            return
        if colour is None:
            colour = visual.color.blue
        if not isinstance(colour, visual.vec):
            colour = visual.vec(*colour)
        #angle, direction, point = tf.rotation_from_matrix(cylinder.transform)
        #axis = direction * cylinder.length
        position = transform_point([0,0,0], cylinder.transform)
        axis = transform_direction([0,0,1], cylinder.transform)
        print(cylinder.transform, "Cylinder:transform")
        print(position, "Cylinder:position")
        print(axis, "Cylinder:axis")
        print(colour, "Cylinder:colour")
        print(cylinder.radius, "Cylinder:radius")
        pos = visual.vec(*tuple(position))
        axis = visual.vec(*axis.tolist())
        visual.cylinder(pos=pos, axis=axis, color=colour, radius=cylinder.radius, opacity=opacity, length = cylinder.length)


    def addCSG(self, CSGobj, res,origin,extent, colour=None, opacity=1.):
        """
        Visualise a CSG structure in a space subset defined by xmin, xmax, ymin, .... with division factor (i.e. ~ resolution) res
        """

        #INTone = Box(origin = (-1.,-1.,-0.), extent = (1,1,3))
        #INTtwo = Box(origin = (-0.5,-0.5,0), extent = (0.5,0.5,3))
        #INTtwo.append_transform(tf.translation_matrix((0,0.5,0)))
        #INTtwo.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
        #CSGobj = CSGsub(INTone, INTtwo)
       
        #xmin = -1.
        #xmax = 1.
        #ymin = -1.
        #ymax = 1.
        #zmin = -1.
        #zmax = 3.

        #resolution = 0.05
        #print "Resolution: ", res

        xmin = origin[0]
        xmax = extent[0]
        ymin = origin[1]
        ymax = extent[1]
        zmin = origin[2]
        zmax = extent[2]

        """
        Determine Voxel size from resolution
        """
        voxelextent = (res*(xmax-xmin), res*(ymax-ymin), res*(zmax-zmin))
        pex = voxelextent


        """
        Scan space
        """
        
        x = xmin
        y = ymin
        z = zmin
        
        print('Visualisation of ', CSGobj.reference, ' started...')
            
        while x < xmax:

            y=ymin
            z=zmin
                  
            while y < ymax:            
                
                z = zmin
                
                while z < zmax:                
                    
                    pt = (x, y, z)                
                    
                    if CSGobj.contains(pt):
                        origin = (pt[0]-pex[0]/2, pt[1]-pex[1]/2, pt[2]-pex[2]/2)
                        extent = (pt[0]+pex[0]/2, pt[1]+pex[1]/2, pt[2]+pex[2]/2)
                        voxel = Box(origin = origin, extent = extent)
                        self.addCSGvoxel(voxel, colour=colour, opacity=1.)                
                    
                    z = z + res*(zmax-zmin)

                y = y + res*(ymax-ymin)

            x = x + res*(xmax-xmin)     
            
            
        print('Complete.')
    
                
    def addCSGvoxel(self, box, colour, opacity=1.):
        """
        16/03/10: To visualise CSG objects
        """
           
        if colour == None:         
            colour = visual.color.red
            
        org = box.origin
        ext = box.extent
            
        size = np.abs(ext - org)
            
        pos = org + 0.5*size                      
            
        visual.box(pos=pos, size=size, color=colour, opacity=opacity)
        
    def addPhoton(self, photon):
        """Draws a smallSphere with direction arrow and polariation (if data is avaliable)."""
        self.addSmallSphere(photon.position)
        visual.arrow(pos=photon.position, axis=photon.direction * 0.0005, shaftwidth=0.0003, color=visual.color.magenta, opacity=0.8)
        if photon.polarisation != None:
            visual.arrow(pos=photon.position, axis=photon.polarisation * 0.0005, shaftwidth=0.0003, color=visual.color.white, opacity=0.4 )
        
    def addObject(self, obj, colour=None, opacity=0.5, res=0.05):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(obj, Box):
            self.addBox(obj, colour=colour, opacity=opacity)
        if isinstance(obj, Ray):
            self.addRay(obj, colour=colour, opacity=opacity)
        if isinstance(obj, Cylinder):
            self.addCylinder(obj, colour=colour, opacity=opacity)
        if isinstance(obj, FinitePlane):
            self.addFinitePlane(obj, colour, opacity, opacity=opacity)
        if isinstance(obj, csg.CSGadd) or isinstance (obj, csg.CSGint) or isinstance (obj, csg.CSGsub):
            self.addCSG(obj, res, origin, extent, colour, opacity=opacity)
        if isinstance(obj, Polygon):
            self.addPolygon(obj, colour=colour, opacity=opacity)
        if isinstance(obj, Convex):
            self.addConvex(obj, colour=colour, opacity=opacity)
        if isinstance(obj, Sphere):
            self.addSphere(obj, colour=colour,  opacity=opacity)
        

if False:
    box1 = Box(origin=[0,0,0], extent=[2,2,2])
    box2 = Box(origin=[2,2,2], extent=[2.1,4,4])
    ray1 = Ray(position=[-1,-1,-1], direction=[1,1,1])
    ray2 = Ray(position=[-1,-1,-1], direction=[1,0,0])
    vis = Visualiser()
    vis.addObject(box1)
    import time
    time.sleep(1)
    vis.addObject(ray1)
    time.sleep(1)
    vis.addObject(ray2)
    time.sleep(1)
    vis.addObject(box2)
    time.sleep(1)
    vis.addLine([0,0,0],[5,4,5])

"""
# TEST TEST TEST
vis = Visualiser()

INTone = Box(origin = (-1.,-1.,-0.), extent = (1,1,3))
INTtwo = Box(origin = (-0.5,-0.5,0), extent = (0.5,0.5,3))
#INTtwo.append_transform(tf.translation_matrix((0,0.5,0)))
INTtwo.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
myobj = csg.CSGsub(INTone, INTtwo)

#vis.addObject(INTone, colour=visual.color.green)
#vis.addObject(INTtwo, colour=visual.color.blue)

vis.addObject(myobj, res=0.05, colour = visual.color.green)
"""

