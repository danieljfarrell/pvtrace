import typer
import sqlite3
import numpy
import pandas
import enum
import io
import asciiplotlib as apl
from typing import Optional
from pathlib import Path
from pvtrace.cli.db import (
    sql_spectrum_reflected_from_node,
    sql_spectrum_entering_into_node,
    sql_spectrum_escaping_from_node,
    sql_spectrum_nonradiative_loss_in_node,
    sql_spectrum_reacted_in_node,
    sql_spectrum_killed_in_node,
)

app = typer.Typer(help="Database ray spectra")


class OutputChoice(str, enum.Enum):
    plot = "plot"
    csv = "csv"
    json = "json"


def handle_output(samples, output, vertical=None):
    if output == OutputChoice.plot:
        counts, bin_edges = numpy.histogram(samples)
        fig = apl.figure()

        orientation = "horizontal"
        if vertical:
            orientation = "vertical"
        fig.hist(counts, bin_edges, orientation=orientation, force_ascii=False)
        fig.show()
        return

    if output == OutputChoice.csv:
        buffer = io.StringIO()
        pandas.DataFrame(numpy.array(samples), columns=["nanometers"]).to_csv(buffer)
        print(buffer.getvalue())

    if output == OutputChoice.json:
        buffer = io.StringIO()
        pandas.DataFrame(
            numpy.array(samples).flatten(), columns=["nanometers"]
        ).to_json(buffer)
        print(buffer.getvalue())


@app.command(short_help="Spectrum of rays reflected from node")
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
    nx: Optional[float] = typer.Option(
        None, "--nx", help="Surface normal component in x"
    ),
    ny: Optional[float] = typer.Option(
        None, "--ny", help="Surface normal component in y"
    ),
    nz: Optional[float] = typer.Option(
        None, "--nz", help="Surface normal component in z"
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    atol: Optional[float] = typer.Option(
        1e-6, "--atol", help="Float comparison absolute tolerance"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):
    sql = sql_spectrum_reflected_from_node(
        node, nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol
    )
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


@app.command(short_help="Spectrum of rays entering into node")
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
    nx: Optional[float] = typer.Option(
        None, "--nx", help="Surface normal component in x"
    ),
    ny: Optional[float] = typer.Option(
        None, "--ny", help="Surface normal component in y"
    ),
    nz: Optional[float] = typer.Option(
        None, "--nz", help="Surface normal component in z"
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    atol: Optional[float] = typer.Option(
        1e-6, "--atol", help="Float comparison absolute tolerance"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):
    sql = sql_spectrum_entering_into_node(
        node, nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol
    )
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


@app.command(short_help="Spectrum of rays escaping from node")
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
    nx: Optional[float] = typer.Option(
        None, "--nx", help="Surface normal component in x"
    ),
    ny: Optional[float] = typer.Option(
        None, "--ny", help="Surface normal component in y"
    ),
    nz: Optional[float] = typer.Option(
        None, "--nz", help="Surface normal component in z"
    ),
    facet: Optional[str] = typer.Option(
        None, "--facet", "-f", help="Label of the facet"
    ),
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    atol: Optional[float] = typer.Option(
        1e-6, "--atol", help="Float comparison absolute tolerance"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):
    sql = sql_spectrum_escaping_from_node(
        node, nx=nx, ny=ny, nz=nz, facet=facet, source=source, atol=atol
    )
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


@app.command(short_help="Spectrum of rays non-radiatively lost in node")
def lost(
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
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):

    sql = sql_spectrum_nonradiative_loss_in_node(node, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


@app.command(short_help="Spectrum of rays reacted in node")
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
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):

    sql = sql_spectrum_reacted_in_node(node, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


@app.command(short_help="Spectrum of rays reacted in node")
def killed(
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
    source: Optional[str] = typer.Option(
        None, "--source", "-s", help="Label of the rays source"
    ),
    output: OutputChoice = typer.Option(
        OutputChoice.plot,
        "--output",
        "-o",
        case_sensitive=False,
        help="Pick output format",
    ),
    vertical: Optional[bool] = typer.Option(
        False, "--vertical", help="Terminal histogram is vertical"
    ),
):

    sql = sql_spectrum_killed_in_node(node, source)
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    result = cur.execute(sql).fetchall()
    if len(result) > 0:
        _, samples = zip(*result)
        handle_output(samples, output, vertical=vertical)


def main():
    app()


if __name__ == "__main__":
    main()
