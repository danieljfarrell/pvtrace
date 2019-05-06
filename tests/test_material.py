from pvtrace.material.lumophore import Lumophore
from pvtrace.material.properties import Emissive, Absorptive, Refractive


def test_lumophore():
    lum = Lumophore.make_constant(
        x_range=(300.0, 4000.0),
        wavelength1=550,
        wavelength2=600,
        absorption_coefficient=10.0,
        quantum_yield=1.0
    )
    assert isinstance(lum, Lumophore)
    assert isinstance(lum, Emissive)
    assert not isinstance(lum, Refractive)
    assert lum.quantum_yield == 1.0
    