import typer
from typing import Optional
import time
from parse import parse


app = typer.Typer()


@app.command()
def simulate(
    scene: str,
    rays: Optional[int] = typer.Option(100),
    workers: Optional[int] = typer.Option(None),
):
    print("Reading {scene}")
    scene = parse(scene)
    print(f"Running simulation with {rays} rays and {workers} workers")
    result = scene.simulate(rays, workers)
    print(result)


if __name__ == "__main__":
    app()