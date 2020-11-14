import typer
from typing import Optional
import time
import os
from pvtrace.cli.parse import parse


app = typer.Typer()


@app.command()
def simulate(
    scene: str,
    rays: Optional[int] = typer.Option(100),
    workers: Optional[int] = typer.Option(None),
):
    print("WARNING: pvtrace-cli is still in development.")
    print(f"Reading {os.path.relpath(scene)}")
    scene = parse(scene)
    workers_info = workers
    if workers_info is None:
        workers_info = "max"
    print(f"Running simulation with {rays} rays and {workers_info} workers")
    result = scene.simulate(rays, workers)
    print("OK")


def main():
    app()


if __name__ == "__main__":
    main()