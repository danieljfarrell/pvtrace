from pvtrace.cli.parse import parse
from pvtrace import MP_OPT
import os
import pandas as pd
import multiprocessing
import pathos

# This scene contains a LSC slab with red dye
# and a host with fairly large background absorption
# coefficient to prevent rays with extremely long
# path length slowing the simulation down
SCENE_YML = "./tests/data/lsc2.yml"

# Want to use a large number here to provide a decent
# amount of work to each worker. For example, using eight
# workers this is only around 600 rays, which is needs to be
# enough to overcome the penalty of starting the subprocess.
RAYS_THROWN = 5000

if __name__ == "__main__":
    import time
    import logging
    import os

    logging.disable(logging.CRITICAL)

    if MP_OPT == "multiprocessing":
        pool = multiprocessing.Pool(processes=os.cpu_count())
    else:
        pool = pathos.pools.ProcessPool(nodes=os.cpu_count())

    num_workers = []
    time_for_sim = []
    num_reps = 3
    data = pd.DataFrame()

    for workers in range(1, os.cpu_count()):
        num_workers.append(workers)

        scene = parse(SCENE_YML)
        for rep in range(num_reps):
            start_t = time.time()
            scene.simulate(num_rays=RAYS_THROWN, workers=workers, pool=pool)
            took = time.time() - start_t
            row = {
                "workers": workers,
                "rep": rep + 1,
                "took": took,
                "thrown": RAYS_THROWN,
                "secs_per_1000_rays": took / RAYS_THROWN * 1000,
                "throughput_rays_per_sec": RAYS_THROWN / took,
            }
            print(row)
            data = data.append(row, ignore_index=True)

    data.reset_index()
    data.to_csv("mp_check_pathos.csv")