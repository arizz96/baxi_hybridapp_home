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
    CAPACITY_MODELS, find_capacity_model, is_clamped,
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
    res = call(hass, t_ext=-30, t_flow=70)
    edge = TABLE[-25][max(TABLE[-25])]
    assert (res["pt_kw"], res["pel_kw"], res["cop"]) == (edge.pt, edge.pel, edge.cop)
    assert res["clamped"] is True


def test_missing_cell_falls_back_without_error(hass):
    # (-25, 50) non esiste in tabella: nessuna eccezione.
    res = call(hass, t_ext=-25, t_flow=50)
    assert res["pel_kw"] > 0 and res["clamped"] is False


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
