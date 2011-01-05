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

import numpy as np
from types import *

# Some wavelength points
#x = np.array([400.,600.,601,1000.])
# Some angle values
#y = np.array([0., np.pi/4, np.pi/2])

# Some reflectivity values
#z = np.array([[0.,1e-9,1.-1e-9,1.], [0.,1e-9,1.-1e-9,1.], [0.,1e-9,1.-1e-9,1.]])
#z = np.array([[0.,0.,0.], [1e-9,1e-9,1e-9], [1-1e-9,1-1e-9,1-1e-9], [1.,1.,1.]])
#z_i = I.interp2d(x, y, z, kind='linear', fill_value=0., bounds_error=False)

#np.savetxt("orig.txt", z)
#np.savetxt("intp.txt", z_i(x,y))

#print z_i(610,0.1)
# What crazyness is this spitting out!!!!!!!!!!

class BilinearInterpolation(object):
    """docstring for BilinearInterpolation"""
    def __init__(self, x=None, y=None, z=None, fill_value=0.):
        super(BilinearInterpolation, self).__init__()
        self.x = np.array(x)
        self.y = np.array(y)
        self.z = np.array(z)
        
        # Check the shapes of x,y and z
        x_s = self.x.shape
        y_s = self.y.shape
        z_s = self.z.shape
        assert x_s[0] >= 3, "Need at least 3 points in x."
        assert y_s[0] >= 3, "Need at least 3 points in y."
        assert x_s[0] == z_s[0], "The number of rows in z (which is %s), must be the same as number of elements in x (which is %s)" % (x_s[0], z_s[0])
        assert y_s[0] == z_s[1], "The number of columns in z (which is %s), must be the same as number of elements in y (which is %s)" % (y_s[0], z_s[1])
    
    def __call__(self, xvalue, yvalue):
        """The intepolated value of the surface."""
        try:
            x_i = 0
            found = False
            for i in range(0, len(self.x)-1):
                # print self.x[i], "<=", xvalue, "<", self.x[i+1]
                if self.x[i] <= xvalue < self.x[i+1]:
                    # print "Found, returning index", i
                    x_i = i
                    found = True
                    break
            
            if not found:
                # print "Not found, returning 0."
                return 0.
            x_v = (self.x[x_i], self.x[x_i + 1])
            x_i = (x_i, x_i + 1)
            
            y_i = 0
            found = False
            for i in range(0, len(self.y)-1):
                # print self.y[i], "<=", yvalue, "<", self.y[i+1]
                if self.y[i] <= yvalue < self.y[i+1]:
                    # print "Found, returning index", i
                    y_i = i
                    found = True
                    break
            
            if not found:
                # print "Not found, returning 0."
                return 0.
            y_v = (self.y[y_i], self.y[y_i + 1])
            y_i = (y_i, y_i + 1)
            
            D = (x_v[1] - x_v[0]) * (y_v[1] - y_v[0])
            ta = self.z[x_i[0], y_i[0]]
            tb = (x_v[1] - xvalue)
            tc = (y_v[1] - yvalue)
            t1 = ta * tb  * tc / D
            # print t1, "=", ta, "*", tb, "*", tc, "/", D
            
            ta = self.z[x_i[1], y_i[0]]
            tb = (xvalue - x_v[0]) 
            tc = (y_v[1] - yvalue) 
            t2 = ta * tb * tc / D
            # print t1, "=", ta, "*", tb, "*", tc, "/", D
            
            ta = self.z[x_i[0], y_i[1]]
            tb = (x_v[1] - xvalue)
            tc = (yvalue - y_v[0])
            t3 = ta * tb * tc / D
            # print t1, "=", ta, "*", tb, "*", tc, "/", D
            
            ta = self.z[x_i[1], y_i[1]]
            tb = (xvalue - x_v[0])
            tc = (yvalue - y_v[0])
            t4 = ta * tb * tc / D
            # print t1, "=", ta, "*", tb, "*", tc, "/", D
            
            # print "Therefore,"
            # print t1, "+", t2, "+", t3, "+", t4
            
            # print self.z
            return t1 + t2 + t3 + t4
            
        except ValueError:
            import pdb; pdb.set_trace()
            # Is one of the inputs an array?
            if type(xvalue) == ListType or type(xvalue) == TupleType or type(xvalue) == type(np.array([])):
                constructed_list = []
                for sub_xvalue in xvalue:
                    constructed_list.append(self(sub_xvalue, yvalue))
                return np.array(constructed_list)


if False:
    # Some wavelength points
    x = np.array([400.,600.,601,1000.])
    
    # Some angle values
    y = np.array([0., np.pi/4, np.pi/2])
    
    # Some reflectivity values
    z = np.array([[0.,1e-9,1.-1e-9,1.], [0.,1e-9,1.-1e-9,1.], [0.,1e-9,1.-1e-9,1.]])
    #             rads @ 400nm,    rads @ 600nm,        rads @ 601m,             rads @ 1000nm     
    z = np.array([[0.,0.,0.],      [1e-9,1e-9,1e-9],     [1-1e-9,1-1e-9,1-1e-9],  [1.,1.,1.]])
    # print z.shape
    
    z_i = BilinearInterpolation(x,y,z)
    print z_i(610,0.1)
    