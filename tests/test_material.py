from pvtrace.material.lumophore import Lumophore
from pvtrace.material.properties import Emissive, Absorptive, Refractive
import numpy as np

def test_lumophore():
    lum = Lumophore.make_lumogen_f_red(
        x=np.array([300.0, 400.0, 500.0]),
        absorption_coefficient=10.0,
        quantum_yield=1.0
    )
    assert isinstance(lum, Lumophore)
    assert isinstance(lum, Emissive)
    assert not isinstance(lum, Refractive)
    assert lum.quantum_yield == 1.0
    