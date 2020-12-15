import os
from typing import Optional


def sql_count_reflected_from_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):
    """Returns the number of rays reflected from the node"""
    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'REFLECT'",
    ]

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_count_entering_into_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):
    """Returns the number of rays which enter the node"""
    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT COUNT('throw_id') FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_count_escaping_from_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):
    """Returns the number of rays escaping from the node"""
    inner = [
        "SELECT DISTINCT throw_id FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND container = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

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


def sql_count_reacted_in_node(node: str, source: Optional[str] = None):
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


def sql_spectrum_reflected_from_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'REFLECT'",
    ]

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_entering_into_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND adjacent = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

    if facet:
        inner.append(f"AND facet = '{facet}'")

    if source:
        inner.append(f"AND source = '{source}'")

    sql = "SELECT throw_id, wavelength FROM ( {} )".format(os.linesep.join(inner))
    return sql


def sql_spectrum_escaping_from_node(
    node: str, facet: Optional[str] = None, source: Optional[str] = None
):

    inner = [
        "SELECT DISTINCT throw_id, wavelength FROM ray",
        "INNER JOIN event ON ray.rowid = event.ray_id",
        f"WHERE hit = '{node}'",
        f"AND container = '{node}'",
        "AND kind = 'TRANSMIT'",
    ]

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