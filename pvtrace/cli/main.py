import multiprocessing
from queue import Empty
import threading
import typer
from typing import Optional
import time
import os
from pvtrace.cli.parse import parse


app = typer.Typer()


def write_to_database(queue, stop, progress):

    global_count = 0
    counts = dict()
    while True:

        if stop.is_set():
            return

        try:
            info = queue.get(True, 1.0)
            pid, throw_idx = info[:2]

            # Keep track of counts from this process
            if pid not in counts:
                counts[pid] = throw_idx + 1
            counts[pid] = throw_idx + 1

            if sum(counts.values()) > global_count:
                global_count += 1
                progress.update(1)

            # print(f"Got info {info}")
        except Empty:
            pass


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

    manager = multiprocessing.Manager()
    queue = manager.Queue(maxsize=5000)
    stop = threading.Event()
    with typer.progressbar(length=rays) as progress:
        monitor_thread = threading.Thread(
            target=write_to_database, args=(queue, stop, progress)
        )
        monitor_thread.start()

        try:
            scene.simulate(rays, workers=workers, queue=queue)
        finally:
            # Might need to wait for the queue to be empty!
            stop.set()
            monitor_thread.join()
    print("OK")


def main():
    app()


if __name__ == "__main__":
    main()