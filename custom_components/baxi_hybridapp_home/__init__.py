"""
Custom integration for Baxi Hybrid App devices with Home Assistant.
For more details about this integration, please refer to
https://github.com/Cm-8/baxi_hybridapp_home

custom_components/baxi_hybridapp_home/__init__.py
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_SETPOINT_COMFORT, PARAM_ID_SETPOINT_ECO,
    SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
    HOLIDAY_STAGED_KEY,
    SANITARY_SCHEDULE_DAY_KEYS,
)
from .api import BaxiHybridAppAPI
from .coordinator import BaxiDataUpdateCoordinator
import asyncio
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "water_heater", "button", "binary_sensor", "select", "number", "datetime", "switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])
    coordinator = BaxiDataUpdateCoordinator(hass, entry, api)

    # Primo refresh con semantica config-entry:
    # - credenziali non valide → ConfigEntryAuthFailed → HA avvia il re-auth flow
    # - cloud irraggiungibile  → ConfigEntryNotReady   → HA ritenta il setup con backoff
    await coordinator.async_config_entry_first_refresh()

    # Store API and coordinator
    hass.data.setdefault(DOMAIN, {})[DATA_KEY_API] = api
    hass.data[DOMAIN]["coordinator"] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # -------------------------------------------------------------
    # Servizi: set_comfort / set_eco (aggiornamento setpoint sanitario)
    # -------------------------------------------------------------
    set_schema = vol.Schema({
        vol.Required("value"): vol.All(
            vol.Coerce(int),
            vol.Range(min=SANITARY_MIN_TEMP, max=SANITARY_MAX_TEMP)
        )
    })

    async def handle_set_comfort(call):
        """Aggiorna il setpoint sanitario Comfort via SET (SOLO temperatura)."""
        value = int(call.data.get("value"))

        if value < SANITARY_MIN_TEMP or value > SANITARY_MAX_TEMP:
            _LOGGER.warning(
                "❌ Valore %s fuori range (%s–%s). SET non eseguita.",
                value, SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
            )
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Comfort",
                    "message": f"valore {value}°C fuori range ({SANITARY_MIN_TEMP}-{SANITARY_MAX_TEMP}) — SET annullata",
                    "entity_id": "water_heater.sanitario_comfort",
                },
                blocking=False,
            )
            return

        ok = await hass.async_add_executor_job(
            api.set_configuration_parameter,
            PARAM_ID_SETPOINT_COMFORT,
            value,
        )

        if ok:
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Comfort",
                    "message": f"impostato a {value}°C",
                    "entity_id": "water_heater.sanitario_comfort",
                },
                blocking=False,
            )
            _LOGGER.info("✅ SET Comfort impostato a %s °C", value)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ SET Comfort fallita per %s °C", value)

    async def handle_set_eco(call):
        """Aggiorna il setpoint sanitario Eco via SET (SOLO temperatura)."""
        value = int(call.data.get("value"))

        if value < SANITARY_MIN_TEMP or value > SANITARY_MAX_TEMP:
            _LOGGER.warning(
                "❌ Valore %s fuori range (%s–%s). SET non eseguita.",
                value, SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
            )
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Eco",
                    "message": f"valore {value}°C fuori range ({SANITARY_MIN_TEMP}-{SANITARY_MAX_TEMP}) — SET annullata",
                    "entity_id": "water_heater.sanitario_eco",
                },
                blocking=False,
            )
            return

        ok = await hass.async_add_executor_job(
            api.set_configuration_parameter,
            PARAM_ID_SETPOINT_ECO,
            value,
        )

        if ok:
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Eco",
                    "message": f"impostato a {value}°C",
                    "entity_id": "water_heater.sanitario_eco",
                },
                blocking=False,
            )
            _LOGGER.info("✅ SET Eco impostato a %s °C", value)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ SET Eco fallita per %s °C", value)

    hass.services.async_register(DOMAIN, "set_comfort", handle_set_comfort, schema=set_schema)
    hass.services.async_register(DOMAIN, "set_eco", handle_set_eco, schema=set_schema)

    # -------------------------------------------------------------
    # Servizio: set_sanitary_schedule (fasce Comfort scheduler sanitario)
    # -------------------------------------------------------------
    slot_schema = vol.Schema({
        vol.Required("start"): cv.string,
        vol.Required("end"): cv.string,
    })
    schedule_schema = vol.Schema({
        vol.Required("day"): vol.In(SANITARY_SCHEDULE_DAY_KEYS),
        vol.Required("slots"): [slot_schema],
        vol.Optional("eco_setpoint"): vol.Coerce(int),
    })

    def _sanitary_schedule_entity_id() -> str:
        ent_reg = er.async_get(hass)
        return (
            ent_reg.async_get_entity_id("sensor", DOMAIN, "baxi_sanitary_schedule_state")
            or "sensor.schedulatore_sanitario_stato"
        )

    async def handle_set_sanitary_schedule(call):
        """Sostituisce le fasce Comfort di UN giorno dello scheduler sanitario.

        Rilegge lo scheduler dal cloud prima di scrivere (per non sovrascrivere
        gli altri 6 giorni con dati stantii): vedi api.set_sanitary_day_schedule.
        """
        day = call.data["day"]
        slots = call.data["slots"]
        eco_setpoint = call.data.get("eco_setpoint")
        entity_id = _sanitary_schedule_entity_id()

        try:
            ok = await hass.async_add_executor_job(
                api.set_sanitary_day_schedule, day, slots, eco_setpoint,
            )
        except ValueError as err:
            _LOGGER.warning("❌ Scheduler sanitario %s non valido: %s", day, err)
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Schedulatore Sanitario",
                    "message": f"{day}: {err} — SET annullata",
                    "entity_id": entity_id,
                },
                blocking=False,
            )
            return

        if ok:
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Schedulatore Sanitario",
                    "message": f"{day}: {len(slots)} fasce Comfort aggiornate",
                    "entity_id": entity_id,
                },
                blocking=False,
            )
            _LOGGER.info("✅ Scheduler sanitario %s aggiornato (%d fasce)", day, len(slots))
            # Grace period per dare tempo al backend Baxi di persistere, poi refresh.
            await asyncio.sleep(8)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ SET scheduler sanitario %s fallita", day)

    hass.services.async_register(
        DOMAIN, "set_sanitary_schedule", handle_set_sanitary_schedule, schema=schedule_schema,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_KEY_API)
        hass.data[DOMAIN].pop("coordinator")
        hass.data[DOMAIN].pop(HOLIDAY_STAGED_KEY, None)
    return unload_ok
