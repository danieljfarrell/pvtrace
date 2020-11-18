SQL_COUNT_ALL_LIGHT_RAYS_ENTERING = """
SELECT COUNT('throw_id') FROM (
    SELECT DISTINCT throw_id FROM ray
    INNER JOIN event ON ray.rowid = event.ray_id
    WHERE hit = '?' AND 
    kind = 'TRANSMIT' AND 
    source LIKE '%'
)
"""

# First argument is the geometry object hit.
# Second argument is the name of the light source
SQL_COUNT_ALL_LIGHT_RAYS_REFLECTED = """
SELECT COUNT('throw_id') FROM (
    SELECT DISTINCT throw_id FROM ray
    INNER JOIN event ON ray.rowid = event.ray_id
    WHERE hit = '?' AND 
    kind = 'REFLECT' AND 
    source LIKE '%'
)
"""

SQL_COUNT_NONRADIATIVE_EVENTS_IN_CONTAINER = """
SELECT COUNT('throw_id') FROM (
    SELECT DISTINCT throw_id FROM ray
    INNER JOIN event ON ray.rowid = event.ray_id
	WHERE
		kind = 'NONRADIATIVE' AND 
		source IN ('?')
)
"""