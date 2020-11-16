SQL_COUNT_ALL_LIGHT_RAYS_ENTERING = """
SELECT COUNT('throw_id') FROM (
    SELECT DISTINCT throw_id FROM ray
    INNER JOIN event ON ray.rowid = event.ray_id
    WHERE hit = 'node/geometry/?' AND 
    kind = 'TRANSMIT' AND 
    source LIKE 'light/%'
)
"""

SQL_COUNT_ALL_LIGHT_RAYS_REFLECTED = """
SELECT COUNT('throw_id') FROM (
    SELECT DISTINCT throw_id FROM ray
    INNER JOIN event ON ray.rowid = event.ray_id
    WHERE hit = 'node/geometry/?' AND 
    kind = 'REFLECT' AND 
    source LIKE 'light/%'
)
"""