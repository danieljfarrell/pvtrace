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


# Count all non-radiative events of rays emitted by my-lumogen-red in my-simple-box
# pvtrace-cli count --event nonradiative --source my-lumogen-red --node my-simple-box database.sqlite3

# Count all first ray entering my-simple-box from green-laser light source
# pvtrace-cli count --first --event transmit --source green-laser --node my-simple-box database.sqlite3

# Eventually we can use facet tags too:
# Count all first ray entering my-simple-box by the top facet from green-laser light source
# pvtrace-cli count --first --event transmit --source green-laser --node my-simple-box --facet top database.sqlite3

# ASIDE
# --first tag returns the first occurrence of the `event` option in the ray history
# Count all first ray reflected from my-simple-box by the top facet from green-laser light source
# pvtrace-cli count --first --event reflect --source green-laser --node my-simple-box --facet top database.sqlite3
