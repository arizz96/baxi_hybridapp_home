"""
Calendar platform for Baxi Hybrid App custom integration for Home Assistant.

Espone lo scheduler sanitario (fasce Comfort) come calendario HA modificabile:
ogni fascia è un evento settimanale ricorrente (rrule=FREQ=WEEKLY, uid
"GiornoIta#indice", es. "Lun#0"). Il tempo fuori dagli eventi resta/torna Eco —
a differenza di device a "copertura totale" (es. termostati con schedulazione
sulle 24h come MTS100/MTS200), qui cancellare o spostare una fascia non
richiede richiudere buchi: il resto del giorno è implicitamente Eco.

Ispirato all'approccio calendar-as-scheduler di krahabb/meross_lan
(custom_components/meross_lan/calendar.py), adattato al modello Baxi.

custom_components/baxi_hybridapp_home/calendar.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.calendar import (
    CalendarEntity,
    CalendarEntityFeature,
    CalendarEvent,
)
from homeassistant.components.calendar.const import EVENT_END, EVENT_START
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DATA_KEY_API, DOMAIN, SANITARY_SCHEDULE_DAY_KEYS
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

# Orizzonte di ricerca per "prossimo evento" quando nessuna fascia è attiva ora
# (copre più di una settimana per non perdere schedulazioni rade).
_LOOKAHEAD_DAYS = 8

# Tempo di attesa dopo una scrittura prima di rinfrescare dal cloud (come per
# le altre scritture PUT dell'integrazione: water_heater.py, __init__.py).
_WRITE_GRACE_SECONDS = 8


class BaxiSanitaryScheduleCalendar(CoordinatorEntity, CalendarEntity):
    """Calendario Schedulatore Sanitario (fasce Comfort, editabile)."""

    _attr_name = "Schedulatore Sanitario"
    _attr_unique_id = "baxi_sanitary_schedule_calendar"
    _attr_icon = "mdi:calendar-clock"
    _attr_supported_features = (
        CalendarEntityFeature.CREATE_EVENT
        | CalendarEntityFeature.DELETE_EVENT
        | CalendarEntityFeature.UPDATE_EVENT
    )

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api

    @property
    def device_info(self):
        return build_device_info(self._api)

    @property
    def available(self) -> bool:
        return getattr(self._api, "sanitary_scheduler_status", None) == "ok"

    # ---------------- Lettura ----------------
    @property
    def event(self) -> CalendarEvent | None:
        """Fascia Comfort in corso, o la prossima futura entro _LOOKAHEAD_DAYS."""
        now = dt_util.now()
        occurrences = self._api.sanitary_comfort_occurrences(
            now, now + timedelta(days=_LOOKAHEAD_DAYS)
        )
        if not occurrences:
            return None
        occurrences.sort(key=lambda o: o["start"])
        return self._to_calendar_event(occurrences[0])

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime,
    ) -> list[CalendarEvent]:
        occurrences = await hass.async_add_executor_job(
            self._api.sanitary_comfort_occurrences, start_date, end_date,
        )
        return [self._to_calendar_event(o) for o in occurrences]

    @staticmethod
    def _to_calendar_event(occurrence: dict) -> CalendarEvent:
        return CalendarEvent(
            start=occurrence["start"],
            end=occurrence["end"],
            summary="Comfort",
            description="Fascia Comfort — Schedulatore Sanitario Baxi",
            uid=occurrence["uid"],
            rrule="FREQ=WEEKLY",
        )

    @staticmethod
    def _parse_uid(uid: str) -> tuple[str, int]:
        try:
            day_key, index_str = uid.split("#", 1)
            index = int(index_str)
        except (ValueError, AttributeError):
            raise ValueError(f"uid evento non valido: {uid!r}") from None
        if day_key not in SANITARY_SCHEDULE_DAY_KEYS:
            raise ValueError(f"uid evento non valido: {uid!r}")
        return day_key, index

    # ---------------- Scrittura ----------------
    async def async_create_event(self, **kwargs: Any) -> None:
        await self._write_event(kwargs[EVENT_START], kwargs[EVENT_END])

    async def async_update_event(
        self,
        uid: str,
        event: dict[str, Any],
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        await self._write_event(event[EVENT_START], event[EVENT_END], replace_uid=uid)

    async def async_delete_event(
        self,
        uid: str,
        recurrence_id: str | None = None,
        recurrence_range: str | None = None,
    ) -> None:
        try:
            day_key, index = self._parse_uid(uid)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        try:
            ok = await self.hass.async_add_executor_job(
                self._api.delete_sanitary_comfort_slot, day_key, index,
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        if not ok:
            raise HomeAssistantError("Scrittura dello scheduler sanitario fallita")
        await self._after_write()

    async def _write_event(
        self, start: datetime, end: datetime, replace_uid: str | None = None,
    ) -> None:
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            raise HomeAssistantError(
                "Lo scheduler sanitario non supporta eventi 'tutto il giorno': indica un orario"
            )
        if start.date() != end.date():
            raise HomeAssistantError(
                "Le fasce Comfort non possono superare la mezzanotte: usa un solo giorno per evento"
            )

        day_key = SANITARY_SCHEDULE_DAY_KEYS[start.weekday()]
        slot = {"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")}

        replace_index = None
        if replace_uid is not None:
            try:
                replace_day_key, replace_index = self._parse_uid(replace_uid)
            except ValueError as err:
                raise HomeAssistantError(str(err)) from err
            if replace_day_key != day_key:
                # Spostare l'evento su un altro giorno: cancella nel vecchio,
                # poi crea come nuova fascia in quello nuovo.
                try:
                    await self.hass.async_add_executor_job(
                        self._api.delete_sanitary_comfort_slot, replace_day_key, replace_index,
                    )
                except ValueError as err:
                    raise HomeAssistantError(str(err)) from err
                replace_index = None

        try:
            ok = await self.hass.async_add_executor_job(
                self._api.upsert_sanitary_comfort_slot, day_key, slot, replace_index,
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        if not ok:
            raise HomeAssistantError("Scrittura dello scheduler sanitario fallita")
        await self._after_write()

    async def _after_write(self) -> None:
        # Grace period per dare tempo al backend Baxi di persistere, poi
        # refresh: CoordinatorEntity aggiorna automaticamente lo stato quando
        # il coordinator notifica i listener.
        await asyncio.sleep(_WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([BaxiSanitaryScheduleCalendar(coordinator, api)])
