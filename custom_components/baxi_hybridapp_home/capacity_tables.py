"""
Capacity Tables Baxi — prestazioni in riscaldamento per modello.

Dati presi dai fogli tecnici Baxi ("Capacity Tables", valori calcolati
secondo EN 14511), tabella "VALORI MEDI": per ogni combinazione di
temperatura esterna e temperatura di mandata riportano
- Pt  → potenza termica resa [kW]
- Pel → potenza elettrica assorbita [kW]
- COP → coefficiente di prestazione

Si usano i "valori medi" (non quelli di picco) perché rappresentano meglio
il funzionamento medio reale dell'impianto, che è quello che i sensori
"attesi" (expected_*) vogliono stimare a partire da temperatura esterna e
temperatura di mandata correnti.

Per ora è censito solo il modello AWHP2R 8MR. Per aggiungerne altri basta
un'altra voce in CAPACITY_MODELS con la stessa struttura (nessuna modifica
altrove: api.py e sensor.py leggono il modello via find_capacity_model).

custom_components/baxi_hybridapp_home/capacity_tables.py
"""

from __future__ import annotations

from dataclasses import dataclass

# {temp_mandata: (Pt, Pel, COP)} per una riga a temperatura esterna fissa.
_Row = dict[float, tuple[float, float, float]]


@dataclass(frozen=True)
class CapacityPoint:
    pt: float
    pel: float
    cop: float


# {temp_esterna: {temp_mandata: CapacityPoint}}
CapacityTable = dict[float, dict[float, CapacityPoint]]


def _table(rows: dict[float, _Row]) -> CapacityTable:
    return {
        ext: {flow: CapacityPoint(*values) for flow, values in cols.items()}
        for ext, cols in rows.items()
    }


# AWHP2R 8MR — PRESTAZIONI IN RISCALDAMENTO, VALORI MEDI (EN 14511).
# Le celle assenti nella tabella originale ("/", combinazione non
# testata/non applicabile) sono semplicemente omesse.
_AWHP2R_8MR_MEDI: CapacityTable = _table({
    -25: {25: (4.11, 1.79, 2.29), 30: (3.68, 1.82, 2.03), 35: (3.27, 1.96, 1.67), 40: (3.10, 1.99, 1.56), 45: (2.64, 2.05, 1.29)},
    -20: {25: (5.20, 1.79, 2.90), 30: (4.63, 1.90, 2.43), 35: (4.27, 1.97, 2.17), 40: (3.96, 2.20, 1.80), 45: (3.43, 2.11, 1.62), 50: (2.96, 2.08, 1.42), 55: (2.52, 2.00, 1.25)},
    -15: {25: (6.24, 1.79, 3.49), 30: (5.80, 1.95, 2.98), 35: (5.45, 2.15, 2.53), 40: (5.04, 2.18, 2.32), 45: (4.69, 2.31, 2.03), 50: (4.16, 2.36, 1.76), 55: (4.55, 2.65, 1.72), 60: (3.72, 2.64, 1.41)},
    -10: {25: (6.66, 1.71, 3.89), 30: (6.48, 1.86, 3.49), 35: (6.25, 1.92, 3.26), 40: (6.16, 2.30, 2.68), 45: (6.14, 2.46, 2.50), 50: (5.75, 2.58, 2.23), 55: (5.53, 2.75, 2.01), 60: (4.78, 2.65, 1.81)},
    -7:  {25: (7.27, 1.83, 3.97), 30: (7.11, 2.01, 3.53), 35: (7.10, 2.18, 3.25), 40: (6.71, 2.40, 2.79), 45: (6.60, 2.59, 2.55), 50: (6.17, 2.67, 2.31), 55: (6.15, 3.00, 2.05), 60: (5.07, 2.69, 1.89)},
    -5:  {25: (7.25, 1.71, 4.25), 30: (7.11, 1.86, 3.83), 35: (6.69, 2.00, 3.35), 40: (6.56, 2.14, 3.06), 45: (6.49, 2.33, 2.79), 50: (6.29, 2.48, 2.54), 55: (5.56, 2.46, 2.26), 60: (5.38, 2.62, 2.05)},
    0:   {25: (7.60, 1.55, 4.89), 30: (7.78, 1.79, 4.34), 35: (7.67, 1.98, 3.88), 40: (7.74, 2.30, 3.37), 45: (7.16, 2.35, 3.05), 50: (7.39, 2.64, 2.79), 55: (6.33, 2.63, 2.41), 60: (6.03, 2.78, 2.17)},
    5:   {25: (8.09, 1.31, 6.17), 30: (8.08, 1.58, 5.13), 35: (8.08, 1.71, 4.73), 40: (8.03, 2.04, 3.93), 45: (7.62, 2.15, 3.54), 50: (7.50, 2.43, 3.09), 55: (6.68, 2.37, 2.82), 60: (6.21, 2.50, 2.49), 65: (3.32, 2.72, 1.22)},
    7:   {25: (8.60, 1.26, 6.84), 30: (8.21, 1.47, 5.57), 35: (8.30, 1.60, 5.20), 40: (8.00, 1.84, 4.34), 45: (8.20, 2.08, 3.95), 50: (7.53, 2.29, 3.29), 55: (7.50, 2.36, 3.18), 60: (6.25, 2.25, 2.77), 65: (3.44, 2.46, 1.40)},
    10:  {25: (9.05, 1.14, 7.93), 30: (8.12, 1.33, 6.12), 35: (7.89, 1.41, 5.58), 40: (7.77, 1.74, 4.48), 45: (7.91, 2.00, 3.95), 50: (7.65, 2.18, 3.51), 55: (7.14, 2.11, 3.38), 60: (6.89, 2.45, 2.81), 65: (4.92, 2.27, 2.16)},
    15:  {25: (8.96, 0.93, 9.59), 30: (8.32, 1.09, 7.60), 35: (8.11, 1.27, 6.37), 40: (8.20, 1.50, 5.46), 45: (8.15, 1.79, 4.55), 50: (7.85, 1.98, 3.96), 55: (7.33, 1.99, 3.68), 60: (7.13, 2.24, 3.19), 65: (5.19, 2.11, 2.46)},
    20:  {25: (8.82, 0.79, 11.10), 30: (8.46, 0.94, 9.00), 35: (8.37, 1.11, 7.53), 40: (8.58, 1.35, 6.37), 45: (8.36, 1.59, 5.25), 50: (8.01, 1.79, 4.47), 55: (7.47, 1.80, 4.14), 60: (7.34, 2.11, 3.47)},
    25:  {25: (8.39, 0.73, 11.60), 30: (8.17, 0.86, 9.52), 35: (8.01, 0.98, 8.18), 40: (8.47, 1.23, 6.86), 45: (8.44, 1.38, 6.11), 50: (8.23, 1.68, 4.91), 55: (7.31, 1.64, 4.47), 60: (7.10, 1.89, 3.76)},
    30:  {25: (8.23, 0.67, 12.30), 30: (7.75, 0.77, 10.00), 35: (7.52, 0.90, 8.39), 40: (8.24, 1.11, 7.46), 45: (8.42, 1.27, 6.61), 50: (8.35, 1.56, 5.36), 55: (7.13, 1.49, 4.80), 60: (6.77, 1.67, 4.06)},
    35:  {25: (8.63, 0.68, 12.70), 30: (8.13, 0.78, 10.40), 35: (7.89, 0.90, 8.74), 40: (8.64, 1.12, 7.74), 45: (8.83, 1.30, 6.77), 50: (8.75, 1.55, 5.63), 55: (7.48, 1.49, 5.03)},
    40:  {25: (9.20, 0.70, 13.10), 30: (8.39, 0.75, 11.10), 35: (8.04, 0.87, 9.28), 40: (8.81, 1.09, 8.08), 45: (9.01, 1.30, 6.95), 50: (8.94, 1.50, 5.95)},
    43:  {25: (9.56, 0.69, 13.90), 30: (8.72, 0.69, 12.60), 35: (8.36, 0.83, 10.00), 40: (9.16, 1.05, 8.74), 45: (9.36, 1.26, 7.40), 50: (9.28, 1.39, 6.67)},
})


@dataclass(frozen=True)
class CapacityModel:
    """Un modello censito: alias con cui riconoscerlo + tabella prestazioni."""
    aliases: tuple[str, ...]  # confrontati (case/spazi-insensitive) con thingModel/thingDefinitionName
    heating: CapacityTable


CAPACITY_MODELS: tuple[CapacityModel, ...] = (
    CapacityModel(
        # "IDU CSI Alya E 8-10" è il thingModel Servitly osservato su un
        # CSI IN Alya E 8kW reale (vedi diagnostica integrazione): stessa
        # unità da 8 kW della Capacity Table AWHP2R 8MR, solo nome
        # commerciale diverso da quello del foglio tecnico.
        aliases=("AWHP2R 8MR", "AWHP2R8MR", "AWHP2R", "IDU CSI Alya E 8-10"),
        heating=_AWHP2R_8MR_MEDI,
    ),
    # Aggiungere qui gli altri modelli man mano che si ottengono le
    # rispettive Capacity Tables Baxi (stessa struttura di _AWHP2R_8MR_MEDI).
)


def _normalize(value: str | None) -> str:
    return "".join(str(value or "").upper().split())


def find_capacity_model(*candidates: str | None) -> CapacityModel | None:
    """Trova il CapacityModel che corrisponde a uno degli identificativi forniti.

    Pensato per essere chiamato con (thingModel, thingDefinitionName): il
    primo candidato non vuoto che matcha un alias vince.
    """
    for candidate in candidates:
        norm = _normalize(candidate)
        if not norm:
            continue
        for model in CAPACITY_MODELS:
            if any(_normalize(alias) == norm for alias in model.aliases):
                return model
    return None


def _bracket(sorted_keys: list[float], x: float) -> tuple[float, float]:
    """(lo, hi) della griglia tra cui cade x, clampato ai bordi della tabella."""
    if x <= sorted_keys[0]:
        return sorted_keys[0], sorted_keys[0]
    if x >= sorted_keys[-1]:
        return sorted_keys[-1], sorted_keys[-1]
    lo = sorted_keys[0]
    for key in sorted_keys:
        if key <= x:
            lo = key
        else:
            return lo, key
    return sorted_keys[-1], sorted_keys[-1]


def _lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _nearest_point(table: CapacityTable, ext_temp: float, flow_temp: float) -> CapacityPoint | None:
    """Punto valido più vicino nella tabella (fallback per celle mancanti)."""
    best: CapacityPoint | None = None
    best_dist: float | None = None
    for ext, cols in table.items():
        for flow, point in cols.items():
            dist = (ext - ext_temp) ** 2 + (flow - flow_temp) ** 2
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best = point
    return best


def interpolate(table: CapacityTable, ext_temp: float, flow_temp: float) -> CapacityPoint | None:
    """Interpola Pt/Pel/COP sulla griglia (temp. esterna, temp. mandata).

    Interpolazione bilineare standard; le richieste fuori dai limiti
    pubblicati vengono clampate al bordo della tabella. Le celle mancanti
    (combinazioni non testate/non applicabili nella tabella originale)
    ripiegano sul punto valido più vicino, invece di propagare un buco.
    """
    if not table:
        return None

    ext_keys = sorted(table.keys())
    e0, e1 = _bracket(ext_keys, ext_temp)

    def _row_point(ext_key: float) -> CapacityPoint | None:
        row = table[ext_key]
        flow_keys = sorted(row.keys())
        f0, f1 = _bracket(flow_keys, flow_temp)
        p0, p1 = row.get(f0), row.get(f1)
        if p0 is None or p1 is None:
            return _nearest_point({ext_key: row}, ext_key, flow_temp)
        return CapacityPoint(
            pt=_lerp(flow_temp, f0, f1, p0.pt, p1.pt),
            pel=_lerp(flow_temp, f0, f1, p0.pel, p1.pel),
            cop=_lerp(flow_temp, f0, f1, p0.cop, p1.cop),
        )

    row0 = _row_point(e0)
    row1 = _row_point(e1) if e1 != e0 else row0
    if row0 is None or row1 is None:
        return _nearest_point(table, ext_temp, flow_temp)

    return CapacityPoint(
        pt=_lerp(ext_temp, e0, e1, row0.pt, row1.pt),
        pel=_lerp(ext_temp, e0, e1, row0.pel, row1.pel),
        cop=_lerp(ext_temp, e0, e1, row0.cop, row1.cop),
    )
