import multiprocessing
import threading
from numpy.lib.function_base import append
import typer
import sqlite3
import os
import time
from pathlib import Path
from typing import Optional
from queue import Empty
from pvtrace.cli.parse import parse
from pvtrace.light.event import Event
from pvtrace.scene.renderer import MeshcatRenderer

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA = BASE_DIR / "data" / "schema.sql"
if not SCHEMA.exists():
    raise FileNotFoundError("Cannot find database schema")
SCHEMA = str(SCHEMA)

RENDERER = dict()

app = typer.Typer()


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

    if metadata:
        component = metadata.get("component", None)
        hit = metadata.get("hit", None)
        container = metadata.get("container", None)
        adjacent = metadata.get("adjacent", None)
        facet = metadata.get("facet", None)

    values = (ray_db_id, event.name, component, hit, container, adjacent, facet)
    cur.execute("INSERT INTO event VALUES (?, ?, ?, ?, ?, ?, ?)", values)


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

                # Render every 10 rays
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
    scene: Optional[Path] = typer.Option(
        ...,
        "--scene",
        "-s",
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
        delete = typer.confirm("Delete existing database file?", abort=True)
        if delete:
            os.remove(dbfilepath)
    prepare_database(dbfilepath)

    # Prepare for multiprocessing
    manager = multiprocessing.Manager()
    queue = manager.Queue(maxsize=5000)
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
            scene_obj.simulate(rays, workers=workers, queue=queue)
        finally:
            # Might need to wait for the queue to be empty!
            while not queue.empty():
                time.sleep(0.2)
            stop.set()
            monitor_thread.join()

    print("OK")


@app.command(short_help="View scene file in browser")
def show(
    scene: Path = typer.Option(
        ...,
        "--scene",
        "-s",
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=True,
        help="Scene yml file",
    ),
    zmq: str = typer.Option(..., "--zmq", help="ZMQ URL of meshcat-server"),
    wireframe: Optional[bool] = typer.Option(True),
):
    scene_obj = parse(scene)
    renderer = MeshcatRenderer(zmq_url=zmq, open_browser=False, wireframe=wireframe)
    renderer.remove(scene_obj)
    renderer.render(scene_obj)
    renderer.vis.open()


def main():
    app()


if __name__ == "__main__":
    main()
