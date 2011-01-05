from __future__ import division
import numpy as np
import sqlite3 as sql
import inspect
import types
import os
import pvtrace


# The database schema lives inside the pvtrace module directory
DB_SCHEMA = os.path.dirname(pvtrace.__file__) + "/dbschema.sql"

def counted(fn):
    def wrapper(*args, **kwargs):
        wrapper.called+= 1
        return fn(*args, **kwargs)
    wrapper.called= 0
    wrapper.__name__= fn.__name__
    return wrapper

class PhotonDatabase(object):
    """An object the wraps a mysql database.
    """
    def __init__(self, file=None):
        super(PhotonDatabase, self).__init__()
        
        self.uid = 0
        self.needSchema = False
        if file is None:
            self.defaultDatabase = True
            self.file = "/tmp/pvtracedb.sql"
        else:
            self.defaultDatabase = False
            self.file = file
        
        #import pdb; pdb.set_trace()
        print "Looking for Schema file ... ", DB_SCHEMA
        # Delete this file and start again
        if os.path.exists(self.file) and os.path.basename(self.file) == 'pvtracedb.sql' and self.defaultDatabase:
            self.needSchema=True
            os.remove(self.file)
        
        if self.needSchema:
            print "Creating database ...", self.file
        else:
            print "Loading database ...", self.file
        
        self.connection = sql.connect(self.file)
        self.cursor = self.connection.cursor()
        
        
        # The database design
        if self.needSchema:
            try:
                file = open(os.path.abspath(DB_SCHEMA), "r")
                for line in file:
                    #print line
                    self.cursor.execute(line)
            except Exception as inst:
                print "Could not load schema file."
                print type(inst)
                print inst
                exit(1)
                
    def log(self, photon, surface_normal=None, on_surface_obj=None, surface_id=None, ray_direction_bound=None, emitter_material=None, absorber_material=None):
        """Adds a new row to the database. NB Every time this function is called the uid of the photon is incremented."""
        values = (self.uid, photon.id, float(photon.wavelength))
        #import pdb; pdb.set_trace()
        self.cursor.execute('INSERT INTO photon VALUES (?, ?, ?)', values)
        
        values = (photon.position[0], photon.position[1], photon.position[2], self.uid)
        self.cursor.execute('INSERT INTO position VALUES (?, ?, ?, ?)', values)
        
        values = (photon.direction[0], photon.direction[1], photon.direction[2], self.uid)
        self.cursor.execute('INSERT INTO direction VALUES (?, ?, ?, ?)', values)
        
        try:
            values = (photon.polarisation[0], photon.polarisation[1], photon.polarisation[2], self.uid)
            self.cursor.execute('INSERT INTO polarisation VALUES (?, ?, ?, ?)', values)
        except:
            pass
        
        if surface_normal is not None:
            values = (surface_normal[0], surface_normal[1], surface_normal[2], self.uid)
            self.cursor.execute('INSERT INTO surface_normal VALUES (?, ?, ?, ?)', values)
        
        values = (photon.absorption_counter, photon.intersection_counter, photon.active, photon.killed, photon.source, emitter_material, absorber_material, str(photon.container), str(on_surface_obj), str(surface_id), str(ray_direction_bound), self.uid)
        self.cursor.execute('INSERT INTO state VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', values)
        
        # the last line of this method update the unique photon ID (i.e. the row number)
        self.uid = self.uid + 1
        
        # Every 100 times write data to file
        if not self.uid % 1:
            self.connection.commit()
        
    def __del__(self):
        self.cursor.close()
    
    def all_exiting_photon_uid(self):
        return self.cursor.execute('SELECT MAX(uid) FROM photon GROUP BY pid;').fetchall()
    
    def killed(self):
        """Returns the uid of killed photons (one that took too many steps to complete)."""
        return self.cursor.execute('SELECT uid FROM state WHERE killed = 1').fetchall()
        
    def missed(self):
        """Returns the uid of photons that did not hit any scene objects"""
        pass
    
    def surface_ids_with_records(self):
        """Returns surfaces that have recorded exiting objects."""
        return self.cursor.execute('SELECT DISTINCT surface_id FROM state WHERE uid IN (SELECT uid FROM surface_normal WHERE uid IN (SELECT MAX(uid) FROM photon GROUP BY pid));').fetchall()
    
    def surface_normal_from_surface_id(self, surface_id, position_on_surface=None):
        """Returns a surface normal (vector) for a specified surface_id. If the surface is curved, you will need to specify the point on the surface."""
        return self.cursor.execute('SELECT x,y,z FROM surface_normal WHERE uid = (SELECT MIN(uid) FROM state WHERE surface_id = ?)', (surface_id,)).fetchall()[0]
        
    def uids_out_bound_on_surface(self, surface_id, luminescent=None, solar=None):
        """For a surface_id will return all uid on an out bound direction. If keyword luminescent=True, 
        then only luminescent photons will be returned. If solar=True, the only solar photons will be 
        returned. If both are True then both types are returned i.e. the default behaviour. Setting the keyworks to any other value is ignored."""
        if luminescent == solar:
            return self.itemise(self.cursor.execute('SELECT MAX(uid) FROM photon GROUP BY pid HAVING uid IN (SELECT uid FROM state WHERE ray_direction_bound = "Out" AND surface_id=? GROUP BY uid);', (surface_id,)).fetchall())
        elif luminescent == True:
            return self.itemise(self.cursor.execute('SELECT MAX(uid) FROM photon GROUP BY pid HAVING uid IN (SELECT uid FROM state WHERE ray_direction_bound = "Out" AND surface_id=? AND absorption_counter > 0 GROUP BY uid);', (surface_id,)).fetchall())
        elif solar == True:
            return self.itemise(self.cursor.execute('SELECT MAX(uid) FROM photon GROUP BY pid HAVING uid IN (SELECT uid FROM state WHERE ray_direction_bound = "Out" AND surface_id=? AND absorption_counter = 0 GROUP BY uid);', (surface_id,)).fetchall())
        else:
            print "Cannot return any uids for this question. Are you using the function uids_out_bound_on_surface correctly?"
            return []
        
    def uids_in_bound_on_surface(self, surface_id):
        """For a surface_id this function will return all uid on an in bound direction."""
        return self.itemise(self.cursor.execute('SELECT MAX(uid) FROM photon GROUP BY pid HAVING uid IN (SELECT uid FROM state WHERE ray_direction_bound = "In" AND surface_id=? GROUP BY uid);', (surface_id,)).fetchall())
        
    def photon_uid_exiting_surface(self, surface_id):
        """For a surface_id this function will return all uid with direction parallel (in the same direction) as the surface_normal of the surface."""
        pass
    
    def uids_first_intersection(self):
        """Returns the unique identifier of the first intersection for all photons"""
        return self.cursor.execute('SELECT uid FROM state WHERE intersection_counter = 1;').fetchall()
    
    def uids_generated_photons(self):
        return self.cursor.execute('SELECT MIN(uid) FROM photon GROUP BY pid;').fetchall()
    
    def pid_from_uid(self, uid):
        return self.cursor.execute('SELECT pid FROM photon WHERE uid=?', (uid,)).fetchall()
    
    def uids_nonradiative_losses(self):
        return self.itemise(self.cursor.execute("SELECT uid FROM state WHERE surface_id = 'None' AND absorption_counter > 0 AND killed = 0 GROUP BY uid HAVING uid IN (SELECT MAX(uid) FROM photon group BY pid)").fetchall())
    
    def value_for_table_column_uid(self, table, column, uid):
        """Returns values from the database index my table, column and row, where the row is uniquely defined using the photon uid. 
        Column can also be array-like so multiple columns can be specified provided they come from the same table."""
        if type(column) is types.StringType or types.UnicodeType:
            return self.cursor.execute("SELECT ? FROM ? WHERE uid = ?", (column, table, uid)).fetchall()
        elif type(column) is types.ListType or types.TupleType:
            col_headers = ""
            for header in column:
                col_header += header
                if header is not column[-1]:
                    col_header += ', '
            return self.cursor.execute("SELECT (?) FROM ? WHERE uid = ?", (col_headers, table, uid)).fetchall()
        else:
            print "Cannot return any uids for this question. Are you using the function value_for_table_column_uid correctly?"
            return []
        
    def directionForUid(self, uid):
        if  type(uid) == types.IntType or type(uid) == types.FloatType:
            return np.array(self.cursor.execute("SELECT x,y,z FROM direction WHERE uid = ?", (uid,)).fetchall()[0])
        elif type(uid) == types.ListType or type(uid) == types.TupleType:
            # This has a variable number of items so ignoring the secure way to do this... me bad
            items = str(uid)[1:-1]
            cmd = "SELECT x,y,z FROM direction WHERE uid IN (%s)" % (items,)
            return self.cursor.execute(cmd).fetchall()
    
    def polarisationForUid(self, uid):
        if type(uid) == types.IntType or type(uid) == types.FloatType:
            return np.array(self.cursor.execute("SELECT x,y,z FROM polarisation WHERE uid = ?", (uid,)).fetchall()[0])
        elif type(uid) == types.ListType or type(uid) == types.TupleType:
            items = str(uid)[1:-1]
            cmd = "SELECT x,y,z FROM polarisation WHERE uid IN (%s)" % (items,)
            return self.cursor.execute(cmd).fetchall()
    
    def positionForUid(self, uid):
        if type(uid) == types.IntType or type(uid) == types.FloatType:
            return np.array(self.cursor.execute("SELECT x,y,z FROM position WHERE uid = ?", (uid,)).fetchall()[0])
        elif type(uid) == types.ListType or type(uid) == types.TupleType:
            items = str(uid)[1:-1]
            cmd = "SELECT x,y,z FROM position WHERE uid IN (%s)" % items
            return self.cursor.execute(cmd).fetchall()
            
    def wavelengthForUid(self, uid):
        #import pdb; pdb.set_trace()
        if type(uid) == types.IntType or type(uid) == types.FloatType:
            return np.array(self.cursor.execute("SELECT wavelength FROM photon WHERE uid = ?", (uid,)).fetchall()[0])
        elif type(uid) == types.ListType or type(uid) == types.TupleType:
            items = str(uid)[1:-1]
            cmd = "SELECT wavelength FROM photon WHERE uid IN (%s)" % (items,)
            values = self.itemise(self.cursor.execute(cmd).fetchall())
            return values

    def itemise(self, array):
        """Extracts redundent nested arrays from a parent array e.g. [(1,), (2,), (3,), (4,)] becomes (1,2,3,4)."""
        new = []
        is_values = None
        is_points = None
        for item in array:
            
            if type(item) == types.ListType or type(item) == types.TupleType:
                
                if len(item) == 1:
                    # The data is comprised of single values
                    new.append(item[0])
                    is_values = True
                
                if len(item) == 3:
                    # The data is comprised of cartesian points
                    is_points = True
                    new.append(item)
                
                if is_values == is_points:
                    raise ValueError, "All elements must of the array must be singleton arrays (i.e single elements arrays)."
        
        return new

if __name__ == "__main__":
    import PhotonDatabase
    db = PhotonDatabase.PhotonDatabase('/tmp/pvtracedb.sql')
    uid = db.uids_nonradiative_losses()
    print uid
    print db.wavelengthForUid(uid)
    print ""
    print db.positionForUid(uid)
    print ""
    print db.directionForUid(uid)
    print ""
    print db.polarisationForUid(uid)
    
    print "Plotting Test"
    import numpy as np
    import pylab
    data = db.wavelengthForUid(uid)
    hist = np.histogram(data, bins=np.linspace(300,800,num=100))
    pylab.hist(data, bins=np.linspace(300,800,num=100), histtype='stepfilled')
    pylab.savefig('/tmp/plot-test.pdf')
    pylab.clf()
    
    print "Plotting edge"
    uid = db.uids_out_bound_on_surface('left', luminescent=True) + db.uids_out_bound_on_surface('right', luminescent=True) + db.uids_out_bound_on_surface('near', luminescent=True) + db.uids_out_bound_on_surface('far', luminescent=True)
    print uid
    data = db.wavelengthForUid(uid)
    hist = np.histogram(data, bins=np.linspace(300,800,num=100))
    pylab.hist(data, 100, histtype='stepfilled')
    pylab.savefig('/tmp/plot-edge.pdf')
    pylab.clf()
    
    print "Plotting polar"
    for id in ['left','right', 'near', 'far']:
        data = []
        norm = db.surface_normal_from_surface_id(id)
        print "Surface", id, "Normal", norm
        uids = db.uids_out_bound_on_surface(id, luminescent=True)
        
        for item in uids:
            k = db.directionForUid(item)
            rads = pvtrace.angle(norm, k)
            deg = np.degrees(rads)
            data.append(deg)
    
    bins = np.linspace(0,360,num=100)
    hist = np.histogram(data, bins=bins)
    pylab.hist(data, 100, histtype='stepfilled')
    pylab.savefig('/tmp/plot-polar.pdf')
    pylab.clf()
    
    print "Plotting escape"
    uid = db.uids_out_bound_on_surface('top', luminescent=True) + db.uids_out_bound_on_surface('bottom', luminescent=True)
    print uid
    data = db.wavelengthForUid(uid)
    hist, bin_edges = np.histogram(data, bins=np.linspace(300,800,num=10))
    pylab.hist(data, len(bin_edges), histtype='stepfilled')
    pylab.savefig('/tmp/plot-escape.pdf')
    pylab.clf()
    
    print "Plotting reflected"
    uid = db.uids_out_bound_on_surface('bottom', solar=True)
    data = db.wavelengthForUid(uid)
    hist, bin_edges = np.histogram(data, bins=np.linspace(300,800,num=10))
    pylab.hist(data, len(bin_edges), histtype='stepfilled')
    pylab.savefig('/tmp/plot-reflected.pdf')
    pylab.clf()
    
    uid = db.uids_out_bound_on_surface('top', solar=True)
    data = db.wavelengthForUid(uid)
    hist, bin_edges = np.histogram(data, bins=np.linspace(300,800,num=10))
    pylab.hist(data, len(bin_edges), histtype='stepfilled')
    pylab.savefig('/tmp/plot-transmitted.pdf')
    pylab.clf()
    
    
    
    
    
