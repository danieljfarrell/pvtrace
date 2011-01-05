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

from __future__ import division
try:
    import visual
    VISUAL_INSTALLED = True
    print "Python module visual is installed..."
except:
    print "Python module visual is not installed... telling all Visualiser object to not render."
    VISUAL_INSTALLED = False

import numpy as np
import Geometry as geo
import ConstructiveGeometry as csg
import external.transformations as tf


class Visualiser (object):
    """Visualiser a class that converts project geometry objects into vpython objects and draws them. It can be used programmatically: just add objects as they are created and the changes will update in the display."""
    VISUALISER_ON = True
    if not VISUAL_INSTALLED:
        VISUALISER_ON = False
    
    def __init__(self, background=(0,0,0), ambient=1.):
        super(Visualiser, self).__init__()
        if not Visualiser.VISUALISER_ON:
            return
        self.display = visual.display(title='PVTrace', x=0, y=0, width=800, height=600, background=background, ambient=ambient)
        self.display.exit = False
        visual.curve(pos=[(0,0,0), (.2,0,0)], radius=0.001, color=visual.color.red)
        visual.curve(pos=[(0,0,0), (0,.2,0)], radius=0.001, color=visual.color.green)
        visual.curve(pos=[(0,0,0), (0,0,.2)], radius=0.001, color=visual.color.blue)
        visual.label(pos=(.22, 0, 0), text='X', linecolor=visual.color.red)
        visual.label(pos=(0, .22, 0), text='Y', linecolor=visual.color.green)
        visual.label(pos=(0, 0, .22), text='Z', linecolor=visual.color.blue)
    
    def addBox(self, box, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(box, geo.Box):
            if colour == None:
                colour = visual.color.red
            org = geo.transform_point(box.origin, box.transform)
            ext = geo.transform_point(box.extent, box.transform)
            print "Visualiser: box origin=%s, extent=%s" % (str(org), str(ext))
            size = np.abs(ext - org)
            
            pos = org + 0.5*size
            print "Visualiser: box position=%s, size=%s" % (str(pos), str(size))
            angle, direction, point = tf.rotation_from_matrix(box.transform)
            print "colour,", colour
            if colour == [0,0,0]:
                visual.box(pos=pos, size=size, opacity=0.3, material=visual.materials.plastic)
            else:
                visual.box(pos=pos, size=size, color=geo.norm(colour), opacity=0.5)
    
    def addFinitePlane(self, plane, colour=None, opacity=0.):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(plane, geo.FinitePlane):
            if colour == None:
                colour = visual.color.blue
            # visual doesn't support planes, so we draw a very thin box
            H = .001
            pos = (plane.length/2, plane.width/2, H/2)
            pos = geo.transform_point(pos, plane.transform)
            size = (plane.length, plane.width, H)
            axis = geo.transform_direction((0,0,1), plane.transform)
            visual.box(pos=pos, size=size, color=colour, opacity=0)

    def addPolygon(self, polygon, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(polygon, geo.Polygon):
            if colour == None:
                visual.convex(pos=polygon.pts, color=geo.norm([0.1,0.1,0.1]), material=visual.materials.plastic)
            else:
                visual.convex(pos=convex.points, color=geo.norm(colour), opacity=0.5)
    
    def addConvex(self, convex, colour=None):
        """docstring for addConvex"""
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(convex, geo.Convex):
            if colour == None:
                print "Color is none"
                visual.convex(pos=polygon.pts, color=geo.norm([0.1,0.1,0.1]), material=visual.materials.plastic)
            else:
                import pdb; pdb.set_trace()
                print "Colour is", geo.norm(colour)
                visual.convex(pos=convex.points, color=geo.norm(colour), material=visual.materials.plastic)
            
    def addRay(self, ray, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(ray, geo.Ray):
            if colour == None:
                colour = visual.color.white
            pos = ray.position
            axis = ray.direction * 5
            visual.cylinder(pos=pos, axis=axis, radius=0.0001, color=geo.norm(colour))
    
    def addSmallSphere(self, point, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if colour == None:
            colour = visual.color.blue
        visual.sphere(pos=point, radius=0.00012, color=geo.norm(colour))
        #visual.curve(pos=[point], radius=0.0005, color=geo.norm(colour))
        
        
    def addLine(self, start, stop, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if colour == None:
            colour = visual.color.white
        axis = np.array(stop) - np.array(start)
        visual.cylinder(pos=start, axis=axis, radius=0.0001, color=geo.norm(colour))
    
    def addCylinder(self, cylinder, colour=None):
        if not Visualiser.VISUALISER_ON:
            return
        if colour == None:
            colour = visual.color.blue
        #angle, direction, point = tf.rotation_from_matrix(cylinder.transform)
        #axis = direction * cylinder.length
        position = geo.transform_point([0,0,0], cylinder.transform)
        axis = geo.transform_direction([0,0,1], cylinder.transform)
        print cylinder.transform, "Cylinder:transform"
        print position, "Cylinder:position"
        print axis, "Cylinder:axis"
        print colour, "Cylinder:colour"
        print cylinder.radius, "Cylinder:radius"
        visual.cylinder(pos=position, axis=axis, color=colour, radius=cylinder.radius, opacity=0.5, length = cylinder.length)


    def addCSG(self, CSGobj, res,origin,extent,colour=None):
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
        
        print 'Visualisation of ', CSGobj.reference, ' started...'
            
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
                        voxel = geo.Box(origin = origin, extent = extent)
                        self.addCSGvoxel(voxel, colour=colour)                
                    
                    z = z + res*(zmax-zmin)

                y = y + res*(ymax-ymin)

            x = x + res*(xmax-xmin)     
            
            
        print 'Complete.'
    
                
    def addCSGvoxel(self, box, colour):
        """
        16/03/10: To visualise CSG objects
        """
           
        if colour == None:         
            colour = visual.color.red
            
        org = box.origin
        ext = box.extent
            
        size = np.abs(ext - org)
            
        pos = org + 0.5*size                      
            
        visual.box(pos=pos, size=size, color=colour, opacity=0.2)
        
    def addPhoton(self, photon):
        """Draws a smallSphere with direction arrow and polariation (if data is avaliable)."""
        self.addSmallSphere(photon.position)
        visual.arrow(pos=photon.position, axis=photon.direction * 0.0005, shaftwidth=0.0003, color=visual.color.magenta, opacity=0.8)
        if photon.polarisation != None:
            visual.arrow(pos=photon.position, axis=photon.polarisation * 0.0005, shaftwidth=0.0003, color=visual.color.white, opacity=0.4 )
        
    def addObject(self, obj, colour=None, opacity=0.5, res=0.05, origin=(-0.02,-0.02,0.), extent = (0.02,0.02,1.)):
        if not Visualiser.VISUALISER_ON:
            return
        if isinstance(obj, geo.Box):
            self.addBox(obj, colour=colour)
        if isinstance(obj, geo.Ray):
            self.addRay(obj, colour=colour)
        if isinstance(obj, geo.Cylinder):
            self.addCylinder(obj, colour=colour)
        if isinstance(obj, geo.FinitePlane):
            self.addFinitePlane(obj, colour, opacity)
        if isinstance(obj, csg.CSGadd) or isinstance (obj, csg.CSGint) or isinstance (obj, csg.CSGsub):
            self.addCSG(obj, res, origin, extent, colour)
        if isinstance(obj, geo.Polygon):
            self.addPolygon(obj, colour=colour)
        if isinstance(obj, geo.Convex):
            self.addConvex(obj, colour=colour)
        

if False:
    box1 = geo.Box(origin=[0,0,0], extent=[2,2,2])
    box2 = geo.Box(origin=[2,2,2], extent=[2.1,4,4])
    ray1 = geo.Ray(position=[-1,-1,-1], direction=[1,1,1])
    ray2 = geo.Ray(position=[-1,-1,-1], direction=[1,0,0])
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

INTone = geo.Box(origin = (-1.,-1.,-0.), extent = (1,1,3))
INTtwo = geo.Box(origin = (-0.5,-0.5,0), extent = (0.5,0.5,3))
#INTtwo.append_transform(tf.translation_matrix((0,0.5,0)))
INTtwo.append_transform(tf.rotation_matrix(np.pi/4, (0,0,1)))
myobj = csg.CSGsub(INTone, INTtwo)

#vis.addObject(INTone, colour=visual.color.green)
#vis.addObject(INTtwo, colour=visual.color.blue)

vis.addObject(myobj, res=0.05, colour = visual.color.green)
"""

