"""SQL builders for querying pvtrace simulation databases.

Each public function returns a ``(sql, params)`` tuple which should be
executed as a parameterised query, for example::

    sql = sql_count_entering_into_node("my-box")
    cur.execute(*sql)
"""
import os
from typing import Optional


def _normal_clauses(nx, ny, nz, atol):
    """Utility function to process normal coefficients into SQL lines"""

    lines = []
    params = []
    for value, column in ((nx, "ni"), (ny, "nj"), (nz, "nk")):
        if value is not None:
            lines.append(f"AND (ABS(? - {column}) <= ?)")
            params.extend([value, atol])
    return lines, params


def _boundary_query(
    columns,
    node,
    kind,
    other_column,
    nx=None,
    ny=None,
    nz=None,
    facet=None,
    source=None,
    atol=1e-6,
    count=False,
):
    """Query for rays crossing a node surface.

    `other_column` selects the meaning of the crossing: "adjacent" matches
    rays hitting the node from outside (reflected or entering), "container"
    matches rays hitting the surface from inside (escaping).
    """
    inner = [
        f"SELECT DISTINCT {columns} FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        "WHERE hit = ?",
        f"AND {other_column} = ?",
        "AND kind = ?",
    ]
    params = [node, node, kind]

    normal_lines, normal_params = _normal_clauses(nx, ny, nz, atol)
    inner.extend(normal_lines)
    params.extend(normal_params)

    if facet:
        inner.append("AND facet = ?")
        params.append(facet)

    if source:
        inner.append("AND source = ?")
        params.append(source)

    outer = "SELECT COUNT('throw_id')" if count else f"SELECT {columns}"
    sql = "{} FROM ( {} )".format(outer, os.linesep.join(inner))
    return sql, tuple(params)


def _volume_query(columns, node, kind, source=None, count=False):
    """Query for rays terminating inside a node's volume."""

    inner = [
        f"SELECT DISTINCT {columns} FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        "WHERE container = ?",
        "AND kind = ?",
    ]
    params = [node, kind]

    if source:
        inner.append("AND source = ?")
        params.append(source)

    outer = "SELECT COUNT('throw_id')" if count else f"SELECT {columns}"
    sql = "{} FROM ( {} )".format(outer, os.linesep.join(inner))
    return sql, tuple(params)


# Counts


def sql_count_reflected_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    """Returns the number of rays reflected from the node"""
    return _boundary_query(
        "throw_id", node, "REFLECT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol, count=True,
    )


def sql_count_entering_into_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    """Returns the number of rays which enter the node"""
    return _boundary_query(
        "throw_id", node, "TRANSMIT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol, count=True,
    )


def sql_count_escaping_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    """Returns the number of rays escaping from the node"""
    return _boundary_query(
        "throw_id", node, "TRANSMIT", "container",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol, count=True,
    )


def sql_count_nonradiative_loss_in_node(node: str, source: Optional[str] = None):
    """Returns the number of rays nonradiatively absorbed in the node"""
    return _volume_query("throw_id", node, "NONRADIATIVE", source=source, count=True)


def sql_count_reacted_in_node(node: str, source: Optional[str] = None):
    """Returns the number of rays reacted in the node"""
    return _volume_query("throw_id", node, "REACT", source=source, count=True)


def sql_count_killed_in_node(node: str, source: Optional[str] = None):
    """Returns the number of rays killed in the node"""
    return _volume_query("throw_id", node, "KILL", source=source, count=True)


# Spectra


def sql_spectrum_reflected_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, wavelength", node, "REFLECT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_spectrum_entering_into_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, wavelength", node, "TRANSMIT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_spectrum_escaping_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, wavelength", node, "TRANSMIT", "container",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_spectrum_nonradiative_loss_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, wavelength", node, "NONRADIATIVE", source=source)


def sql_spectrum_reacted_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, wavelength", node, "REACT", source=source)


def sql_spectrum_killed_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, wavelength", node, "KILL", source=source)


# Times


def sql_time_reflected_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, duration", node, "REFLECT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_time_entering_into_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, duration", node, "TRANSMIT", "adjacent",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_time_escaping_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    return _boundary_query(
        "throw_id, duration", node, "TRANSMIT", "container",
        nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol,
    )


def sql_time_nonradiative_loss_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, duration", node, "NONRADIATIVE", source=source)


def sql_time_reacted_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, duration", node, "REACT", source=source)


def sql_time_killed_in_node(node: str, source: Optional[str] = None):
    return _volume_query("throw_id, duration", node, "KILL", source=source)
