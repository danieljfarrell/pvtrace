import typer
import sqlite3
from typing import Optional
from pathlib import Path
from pvtrace.cli.db import (
    sql_count_reflected_from_node,
    sql_count_entering_into_node,
    sql_count_escaping_from_node,
    sql_count_nonradiative_loss_in_node,
    sql_count_reacted_in_node,
)

app = typer.Typer(help="Database ray counts")


@app.command(short_help="Number of rays reflected from node")
def reflected(
    node: str = typer.Argument(..., help="Node name"),
    database: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Database file",
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
):
    sql = sql_count_reflected_from_node(node, facet, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    print(cur.execute(sql).fetchone()[0])


@app.command(short_help="Number of rays entering node")
def entering(
    node: str = typer.Argument(..., help="Node name"),
    database: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Database file",
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
):
    sql = sql_count_entering_into_node(node, facet, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    print(cur.execute(sql).fetchone()[0])


@app.command(short_help="Number of rays escaping node")
def escaping(
    node: str = typer.Argument(..., help="Node name"),
    database: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Database file",
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
):
    sql = sql_count_escaping_from_node(node, facet, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    print(cur.execute(sql).fetchone()[0])


@app.command(short_help="Number of rays non-radiatively lost in node")
def nonradiative(
    node: str = typer.Argument(..., help="Node name"),
    database: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Database file",
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
):
    sql = sql_count_nonradiative_loss_in_node(node, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    print(cur.execute(sql).fetchone()[0])


@app.command(short_help="Number of rays reacted in node")
def reacted(
    node: str = typer.Argument(..., help="Node name"),
    database: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Database file",
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
):
    sql = sql_count_reacted_in_node(node, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    print(cur.execute(sql).fetchone()[0])


def main():
    app()


if __name__ == "__main__":
    main()
