
PRAGMA foreign_keys = ON;

CREATE TABLE photon(  uid INTEGER PRIMARY KEY,  /*unique id : different for every row*/  pid INTEGER,  /* photon id : constant from throw to escape/loss */ wavelength DOUBLE);

CREATE TABLE state( absorption_counter INTEGER, intersection_counter INTEGER,  active BOOL,  killed BOOL,  source TEXT,  emitter_material TEXT,  absorber_material TEXT,  container_obj TEXT,  on_surface_obj TEXT,  surface_id TEXT, ray_direction_bound TEXT, uid INTEGER,  FOREIGN KEY(uid) REFERENCES photon(uid));

CREATE TABLE position(  x   DOUBLE,  y   DOUBLE,  z   DOUBLE,  uid  INTEGER,  FOREIGN KEY(uid) REFERENCES photon(uid));

CREATE TABLE direction(  x   DOUBLE,  y   DOUBLE,  z   DOUBLE,  uid  INTEGER,  FOREIGN KEY(uid) REFERENCES photon(uid));

CREATE TABLE polarisation(  x   DOUBLE,  y   DOUBLE,  z   DOUBLE,  uid  INTEGER,  FOREIGN KEY(uid) REFERENCES photon(uid));

CREATE TABLE surface_normal(  x   DOUBLE,  y   DOUBLE,  z   DOUBLE,  uid  INTEGER,  FOREIGN KEY(uid) REFERENCES photon(uid));

--  DATA 
-- INSERT INTO position VALUES (0,0,0,0);
-- INSERT INTO position VALUES (1,1,1,1);
-- INSERT INTO position VALUES (0,0,0,2);
-- INSERT INTO photon VALUES(4,0,700);
-- INSERT INTO position VALUES (1,1,2,4);
-- 
-- EXAMPLES
-- 
-- 1.  "Return the unique IDs in the table photon that correspond to the photon with ID of zero."
--     SELECT uid FROM photon WHERE pid=0
-- 
-- 2. "For each unique IDs in the table photon that correspond to the photon with ID of zero, return the x,y,z position coordinates."
--     SELECT x,y,z FROM position WHERE uid IN (SELECT uid FROM photon WHERE pid=0);    
-- 
-- 3. "Return the entering and exiting uid of the photon with pid=0."
--     SELECT MIN(uid), MAX(uid) FROM photon WHERE pid=0;
--
-- 4. Return the uid of photons whos last position was on the surface of an object
-- SELECT uid FROM surface_normal WHERE uid IN (SELECT MAX(uid
--
-- Returns the last uid for each photon
-- SELECT MAX(uid) FROM photon GROUP BY pid
--
-- Return all uid's which have a surface normal
-- SELECT uid FROM surface_normal WHERE uid IN (SELECT MAX(uid) FROM photon GROUP BY pid)

-- Returns all the unique surface normals that have exiting/entering photons
-- SELECT DISTINCT x,y,z FROM surface_normal WHERE uid IN (SELECT uid FROM surface_normal WHERE uid IN (SELECT MAX(uid) FROM photon GROUP BY pid))
--
-- Return  photon IDs (pid's) that have undergone a certain number of rebsorptions.
-- SELECT pid FROM photon WHERE uid IN (SELECT uid FROM state WHERE reabsorption == 2 GROUP BY uid HAVING uid IN (SELECT MAX(uid) FROM photon GROUP BY pid))
