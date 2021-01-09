import os
from typing import Optional, Tuple


def _process_normal(nx, ny, nz, atol):
    """Utility function to process normal coefficients into SQL lines"""

    lines = []
    if nx is not None:
        lines.append(f"AND (ABS({nx} - ni) <= {atol})")

    if ny is not None:
        lines.append(f"AND (ABS({ny} - nj) <= {atol})")

    if nz is not None:
        lines.append(f"AND (ABS({nz} - nk) <= {atol})")

    return lines


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

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'REFLECT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


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

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


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

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND container = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_count_nonradiative_loss_in_node(node: str, source: Optional[str] = None):
    """Returns the number of rays nonradiatively absorbed in the node"""

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'NONRADIATIVE'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_count_reacted_in_node(
    node: str,
    source: Optional[str] = None,
):
    """Returns the number of rays reacted in the node"""

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'REACT'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_count_killed_in_node(
    node: str,
    source: Optional[str] = None,
):

    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'KILL'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_reflected_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'REFLECT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_entering_into_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_escaping_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND container = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_nonradiative_loss_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'NONRADIATIVE'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_reacted_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'REACT'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_killed_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'KILL'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_reflected_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):

    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'REFLECT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_entering_into_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):

    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_escaping_from_node(
    node: str,
    nx: Optional[float] = None,
    ny: Optional[float] = None,
    nz: Optional[float] = None,
    facet: Optional[str] = None,
    source: Optional[str] = None,
    atol: float = 1e-6,
):
    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND container = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    inner.extend(_process_normal(nx, ny, nz, atol))

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_nonradiative_loss_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'NONRADIATIVE'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_reacted_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'REACT'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_time_killed_in_node(node: str, source: Optional[str] = None):

    inner = [
        "SELECT DISTINCT throw_id, duration FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE container = '{node}'",
        "AND kind = 'KILL'",
    ]

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, duration FROM ( {} )".format(os.linesep.join(inner))
    return sql


if __name__ == "__main__":
    print(sql_count_reflected_from_node("my-simple-box", source="green-laser"))
    print(sql_count_entering_into_node("my-simple-box", source="green-laser"))
    print(sql_count_escaping_from_node("my-simple-box", source="green-laser"))
    print(sql_count_nonradiative_loss_in_node("my-simple-box", source="green-laser"))
    print(sql_count_reacted_in_node("my-simple-box", source="green-laser"))

    print(sql_spectrum_reflected_from_node("my-simple-box", source="green-laser"))
    print(sql_spectrum_entering_into_node("my-simple-box", source="green-laser"))
    print(sql_spectrum_escaping_from_node("my-simple-box", source="green-laser"))
    print(sql_spectrum_nonradiative_loss_in_node("my-simple-box", source="green-laser"))
    print(sql_spectrum_reacted_in_node("my-simple-box", source="green-laser"))