import numpy as np

from pvtrace import LSC


def test_simulate_prepares_spectrum_and_counts():
    np.random.seed(17)
    lsc = LSC((5.0, 5.0, 1.0))
    lsc.add_absorber("background", 0.1)

    lsc.simulate(4)

    assert len(lsc.spectrum(kind="first")) == 4
    assert set(lsc.spectrum(kind="first")) == {555.0}
    assert lsc.counts()["Solar In"].sum() == 4
    assert len(lsc.spectrum(kind="last")) == 4
    assert len(lsc.spectrum(kind="last", events={"nonradiative"})) == 2
    assert lsc.summary()["Non-radiative Loss (fraction):"] == 0.5
