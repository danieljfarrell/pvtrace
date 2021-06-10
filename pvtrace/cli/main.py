import multiprocessing
import threading
from numpy.lib.function_base import append
import typer
import sqlite3
import os
import time as pytime
from pathlib import Path
from typing import Optional
from queue import Empty
from pvtrace import parse
from pvtrace.light.event import Event
from pvtrace.scene.renderer import MeshcatRenderer
from pvtrace.cli import count, spectrum, time

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA = BASE_DIR / "data" / "schema.sql"
if not SCHEMA.exists():
    raise FileNotFoundError("Cannot find database schema")
SCHEMA = str(SCHEMA)

RENDERER = dict()


app = typer.Typer()
app.add_typer(count.app, name="count")
app.add_typer(spectrum.app, name="spectrum")
app.add_typer(time.app, name="time")


def prepare_database(dbfilepath):
    with open(SCHEMA) as fp:
        connection = sqlite3.connect(dbfilepath)
        cur = connection.cursor()
        cur.executescript(fp.read())
        connection.commit()
        connection.close()


def write_ray(cur, ray, global_throw_id):
    values = (
        global_throw_id,
        ray.position[0],
        ray.position[1],
        ray.position[2],
        ray.direction[0],
        ray.direction[1],
        ray.direction[2],
        ray.wavelength,
        ray.source,
        ray.travelled,
        ray.duration,
    )
    cur.execute("INSERT INTO ray VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
    return cur.lastrowid


def write_event(cur, event, metadata, ray_db_id):

    component = None
    hit = None
    container = None
    adjacent = None
    facet = None
    normal = (None, None, None)
    if metadata:
        component = metadata.get("component", None)
        hit = metadata.get("hit", None)
        container = metadata.get("container", None)
        adjacent = metadata.get("adjacent", None)
        facet = metadata.get("facet", None)
        normal = metadata.get("normal", (None, None, None))

    values = (
        ray_db_id,
        event.name,
        component,
        hit,
        container,
        adjacent,
        facet,
    ) + normal
    cur.execute("INSERT INTO event VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", values)


def monitor_queue(
    dbfilepath,
    queue,
    stop,
    progress,
    evertything,
    scene_obj,
    zmq,
    wireframe,
    skip,
    max_histories,
):

    print(f"Opening connection {dbfilepath}")
    connection = sqlite3.connect(dbfilepath)

    renderer = None
    if zmq:
        renderer = MeshcatRenderer(
            zmq_url=zmq,
            open_browser=False,
            wireframe=wireframe,
            max_histories=max_histories,
        )
        renderer.remove(scene_obj)
        renderer.render(scene_obj)
        renderer.vis.open()

    global_completed = 0
    counts = dict()
    global_ids = dict()
    history = dict()
    while True:

        if stop.is_set() and queue.empty():
            connection.close()
            if renderer:
                del renderer
            return

        try:
            info = queue.get(True, 0.1)
            pid, throw_idx, ray, event = info[:4]

            # Keep track of counts from this process
            if pid not in counts:
                counts[pid] = throw_idx + 1
            counts[pid] = throw_idx + 1

            if sum(counts.values()) > global_completed:
                global_completed += 1
                progress.update(1)

            # Assign unique ID for this process and throw
            if (pid, throw_idx) not in global_ids:
                global_ids[(pid, throw_idx)] = len(global_ids)
                if pid in history:
                    if len(history[pid]) > 1:
                        if renderer:
                            renderer.add_history(history[pid])

                # Render every n rays
                if (len(global_ids) % skip) == 0 or throw_idx == 0:
                    history[pid] = []
                else:
                    if pid in history:
                        history.pop(pid)

            if pid in history:
                history[pid].append((ray, event))

            if evertything:
                # Write all rays to database, not just the initial and final
                cur = connection.cursor()
                metadata = info[4]
                ray_db_id = write_ray(cur, ray, global_ids[(pid, throw_idx)])
                write_event(cur, event, metadata, ray_db_id)
                connection.commit()
            else:
                raise NotImplementedError("Database must store all events")

        except Empty:
            pass


@app.command(short_help="Run raytrace simulations")
def simulate(
    scene: Optional[Path] = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Scene yml file",
    ),
    rays: Optional[int] = typer.Option(100, "--rays", "-r", help="Number of rays"),
    workers: Optional[int] = typer.Option(
        None, "--workers", "-w", help="Number of worker processes"
    ),
    end_rays: Optional[bool] = typer.Option(
        False, "--end-rays", help="Only store end rays in database"
    ),
    seed: Optional[int] = typer.Option(None, "--seed", help="Debugging set RNG seed"),
    overwite: Optional[bool] = typer.Option(
        False,
        "--overwrite",
        help="Overwrite old database file",
    ),
    zmq: str = typer.Option(None, "--zmq", help="ZMQ URL of meshcat-server"),
    wireframe: Optional[bool] = typer.Option(True, help="Render using wireframe"),
    render_every: Optional[int] = typer.Option(10, min=1, help="Render every n-th ray"),
    render_max: Optional[int] = typer.Option(
        1, min=1, help="Maximum number of rays to keep"
    ),
):

    print("WARNING: pvtrace-cli is still in development.")
    print(f"Reading {os.path.relpath(scene)}")
    scene_obj = parse(scene)

    # Database file is in the same folder and has the same name as the yml file
    # but with the .sqlite3 extension
    dbfilepath = os.path.abspath(os.path.splitext(scene)[0]) + ".sqlite3"
    if os.path.exists(dbfilepath):
        if not overwite:
            overwite = typer.confirm("Overwrite existing database file?", abort=True)
        if overwite:
            os.remove(dbfilepath)
    prepare_database(dbfilepath)

    # Prepare for multiprocessing
    manager = multiprocessing.Manager()
    queue = manager.Queue(maxsize=10000)
    stop = threading.Event()
    with typer.progressbar(length=rays) as progress:
        monitor_thread = threading.Thread(
            target=monitor_queue,
            args=(
                dbfilepath,
                queue,
                stop,
                progress,
                True,
                scene_obj,
                zmq,
                wireframe,
                render_every,
                render_max,
            ),
        )
        monitor_thread.start()

        try:
            scene_obj.simulate(
                rays, workers=workers, seed=seed, queue=queue, end_rays=end_rays
            )
        finally:
            # Wait for the queue to be empty before killing the monitor thread
            while not queue.empty():
                pytime.sleep(0.2)
            stop.set()
            monitor_thread.join()
    print("OK")


@app.command(short_help="View scene file in browser")
def show(
    zmq: str = typer.Argument(..., help="ZMQ URL of meshcat-server"),
    scene: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Scene yml file",
    ),
    wireframe: Optional[bool] = typer.Option(True),
):
    scene_obj = parse(str(scene.absolute()))
    renderer = MeshcatRenderer(zmq_url=zmq, open_browser=False, wireframe=wireframe)
    renderer.remove(scene_obj)
    renderer.render(scene_obj)
    renderer.vis.open()


def main():
    app()


if __name__ == "__main__":
    main()
