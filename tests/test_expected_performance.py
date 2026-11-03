"""Azione expected_performance: Pel/Pt/COP delle Capacity Tables per una coppia ipotetica."""

import asyncio
from types import SimpleNamespace

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ServiceValidationError

from custom_components.baxi_hybridapp_home import async_setup
from custom_components.baxi_hybridapp_home.capacity_tables import (
    CAPACITY_MODELS, estimate_cop, find_capacity_model, fit_surface, interpolate, is_clamped,
)
from custom_components.baxi_hybridapp_home.coordinator import BaxiRuntimeData

from .test_runtime import FakeHass

TABLE = CAPACITY_MODELS[0].heating


def setup(api, entries=None):
    runtime = BaxiRuntimeData(api=api, coordinator=SimpleNamespace())
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=runtime)
    hass = FakeHass([entry] if entries is None else entries)
    asyncio.run(async_setup(hass, {}))
    return hass


def call(hass, **data):
    schema, _ = hass.schemas["expected_performance"]
    validated = schema(data)
    return asyncio.run(hass.handlers["expected_performance"](SimpleNamespace(data=validated)))


@pytest.fixture
def hass(api):
    api.thingModel = "AWHP2R 8MR"
    return setup(api)


def test_registered_response_only(hass):
    _, supports = hass.schemas["expected_performance"]
    assert supports is SupportsResponse.ONLY


def test_exact_grid_point(hass):
    assert call(hass, t_ext=15, t_flow=50) == {
        "pel_kw": 1.98, "pt_kw": 7.85, "cop": 3.96, "clamped": False, "model": "AWHP2R 8MR",
    }


def test_interpolated_point(hass):
    # Metà tra (15,50)-(20,50) in t_ext e tra 50-55 in mandata: media dei 4 angoli.
    corners = [(7.85, 1.98, 3.96), (7.33, 1.99, 3.68), (8.01, 1.79, 4.47), (7.47, 1.80, 4.14)]
    expected = [round(sum(c[i] for c in corners) / 4, 2) for i in range(3)]
    res = call(hass, t_ext=17.5, t_flow=52.5)
    assert (res["pt_kw"], res["pel_kw"], res["cop"]) == (expected[0], expected[1], expected[2])
    assert res["clamped"] is False


def test_out_of_table_is_clamped_to_edge(hass):
    # Fuori tabella: clamp all'angolo (-25, 65) della griglia, che in tabella è
    # una cella mancante e quindi stimata (non pubblicata).
    res = call(hass, t_ext=-30, t_flow=70)
    corner = interpolate(TABLE, -25, 65)
    assert (res["pt_kw"], res["pel_kw"], res["cop"]) == (
        round(corner.pt, 2), round(corner.pel, 2), round(corner.cop, 2),
    )
    assert res["clamped"] is True


def test_missing_cell_falls_back_without_error(hass):
    # (-25, 50) non esiste in tabella: nessuna eccezione.
    res = call(hass, t_ext=-25, t_flow=50)
    assert res["pel_kw"] > 0 and res["clamped"] is False


def test_in_between_flow_is_interpolated_not_floored():
    lo, hi, mid = interpolate(TABLE, 15, 50), interpolate(TABLE, 15, 55), interpolate(TABLE, 15, 52)
    assert hi.cop < mid.cop < lo.cop
    assert mid.cop == pytest.approx(lo.cop + (hi.cop - lo.cop) * 0.4)


def test_missing_cell_is_estimated_not_copied_from_neighbour():
    # (-25, 50) e (-25, 60) mancano: prima valevano come (-25, 45) = 1.29.
    published = TABLE[-25][45].cop
    c50, c60 = interpolate(TABLE, -25, 50).cop, interpolate(TABLE, -25, 60).cop
    assert 1.0 <= c60 < c50 < published


def test_published_cells_are_untouched_by_gap_filling():
    for ext, cols in TABLE.items():
        for flow, point in cols.items():
            got = interpolate(TABLE, ext, flow)
            assert (got.pt, got.pel, got.cop) == pytest.approx((point.pt, point.pel, point.cop))


def test_smooth_cop_surface_shape():
    # COP scende con la mandata e sale con la temperatura esterna, ovunque.
    for ext in range(-25, 44, 6):
        values = [estimate_cop(TABLE, ext, flow) for flow in range(25, 66, 5)]
        assert values == sorted(values, reverse=True)
    for flow in range(25, 66, 10):
        values = [estimate_cop(TABLE, ext, flow) for ext in range(-25, 44, 6)]
        assert values == sorted(values)


def test_smooth_cop_tracks_table_within_tolerance():
    # Esclude le due celle a 65 °C (precipizio, scartate dal fit come outlier).
    errors = [
        abs(estimate_cop(TABLE, ext, flow) - p.cop) / p.cop
        for ext, cols in TABLE.items() for flow, p in cols.items() if not (flow == 65 and ext < 10)
    ]
    assert sum(errors) / len(errors) < 0.06


def test_estimate_never_below_one_and_fit_needs_enough_data():
    assert estimate_cop(TABLE, -40, 70) >= 1.0
    assert fit_surface({0: {35: CAPACITY_MODELS[0].heating[0][35]}}) is None
    assert estimate_cop({}, 0, 35) is None


def test_unsupported_model(api):
    api.thingModel = api.thingDefinitionName = "SOMETHING ELSE"
    with pytest.raises(ServiceValidationError):
        call(setup(api), t_ext=10, t_flow=40)


def test_entry_not_loaded(api):
    with pytest.raises(ServiceValidationError):
        call(setup(api, entries=[]), t_ext=10, t_flow=40)


@pytest.mark.parametrize("data", [
    {"t_flow": 40}, {"t_ext": 10}, {"t_ext": -41, "t_flow": 40}, {"t_ext": 51, "t_flow": 40},
    {"t_ext": 10, "t_flow": 19}, {"t_ext": 10, "t_flow": 71},
])
def test_schema_rejects_invalid_input(hass, data):
    with pytest.raises(vol.Invalid):
        call(hass, **data)


def test_is_clamped():
    assert not is_clamped(TABLE, 15, 50)
    assert not is_clamped(TABLE, -25, 25) and not is_clamped(TABLE, 43, 65)
    assert is_clamped(TABLE, -26, 50) and is_clamped(TABLE, 44, 50)
    assert is_clamped(TABLE, 15, 24) and is_clamped(TABLE, 15, 66)
    assert not is_clamped({}, 0, 0)
    assert find_capacity_model("AWHP2R 8MR") is CAPACITY_MODELS[0]
