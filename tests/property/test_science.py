from hypothesis import given
from hypothesis import strategies as st

from ecotwin.models.runoff import runoff_volume
from ecotwin.models.solar_pv import solar_energy


@given(
    st.floats(min_value=0, max_value=1000),
    st.floats(min_value=0, max_value=1e7),
    st.floats(min_value=0, max_value=1),
)
def test_runoff_bounds(rain, area, coefficient):
    value = runoff_volume({10: area}, rain, {10: coefficient})
    assert 0 <= value <= rain / 1000 * area + 1e-6


@given(
    st.lists(st.floats(min_value=0, max_value=1500), min_size=1, max_size=72),
    st.floats(min_value=0, max_value=1e5),
)
def test_solar_nonnegative(ghi, power):
    assert solar_energy(power, ghi) >= 0
