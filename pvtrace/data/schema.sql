
CREATE TABLE ray (
    throw_id NOT NULL,      -- identifer which increments when the light source throws a new ray
    x DOUBLE,               -- position in x
    y DOUBLE,               -- position in y
    z DOUBLE,               -- position in z
    i DOUBLE,               -- direction in x
    j DOUBLE,               -- direction in y
    k DOUBLE,               -- direction in z
    wavelength DOUBLE,      -- wavelength in nanometers
    source TEXT,            -- source which emitted the ray
    travelled DOUBLE,       -- total distance travelled
    duration DOUBLE         -- total time since start of simulation
);


CREATE TABLE event (
    ray_id INTEGER NOT NULL,    -- the ray causing this event
    kind TEXT,                  -- pvtrace Event enum value i.e. GENERATE, EMIT etc.
    component TEXT,             -- name of the component at this event
    hit TEXT,                   -- name of the hit node
    container TEXT,             -- name of the container node
    adjacent TEXT,              -- name of the adjacent node
    facet TEXT,                 -- identifier for the facet
    ni DOUBLE,                  -- surface normal vector x-component
    nj DOUBLE,                  -- surface normal vector y-component
    nk DOUBLE,                  -- surface normal vector z-component
    FOREIGN KEY(ray_id) REFERENCES ray(rowid)
);
