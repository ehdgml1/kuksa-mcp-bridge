"""DTC (Diagnostic Trouble Code) database.

Provides a comprehensive mapping of OBD-II DTC codes to human-readable
descriptions, severity levels, affected systems, and recommended actions.
Covers powertrain (Pxxxx), body (Bxxxx), chassis (Cxxxx), and network
(Uxxxx) code families.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Severity type
# ---------------------------------------------------------------------------
Severity = Literal["low", "medium", "high", "critical"]


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------
class DTCInfo(BaseModel):
    """Structured description of a single DTC code.

    Attributes:
        code: OBD-II DTC code (e.g. ``P0301``).
        description: Human-readable explanation of the fault.
        severity: Urgency level for the driver or technician.
        system: Vehicle subsystem affected (e.g. ``Engine``, ``Transmission``).
        recommended_action: Suggested next step for resolution.
    """

    code: str
    description: str
    severity: Severity
    system: str
    recommended_action: str


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DTC_DATABASE: dict[str, DTCInfo] = {
    # ── Powertrain: Fuel / Air Metering (P0100-P0199) ──────────────────
    "P0100": DTCInfo(
        code="P0100",
        description="Mass Air Flow (MAF) sensor circuit malfunction",
        severity="medium",
        system="Engine",
        recommended_action="Inspect MAF sensor wiring and connector; clean or replace MAF sensor.",
    ),
    "P0101": DTCInfo(
        code="P0101",
        description="Mass Air Flow (MAF) sensor range/performance problem",
        severity="medium",
        system="Engine",
        recommended_action="Check for air leaks; clean MAF sensor; replace if reading is out of range.",
    ),
    "P0106": DTCInfo(
        code="P0106",
        description="Manifold Absolute Pressure (MAP) sensor range/performance",
        severity="medium",
        system="Engine",
        recommended_action="Inspect MAP sensor and vacuum hoses; replace sensor if faulty.",
    ),
    "P0110": DTCInfo(
        code="P0110",
        description="Intake Air Temperature (IAT) sensor circuit malfunction",
        severity="low",
        system="Engine",
        recommended_action="Check IAT sensor connector and wiring; replace sensor if open circuit.",
    ),
    "P0115": DTCInfo(
        code="P0115",
        description="Engine Coolant Temperature (ECT) sensor circuit malfunction",
        severity="medium",
        system="Engine",
        recommended_action="Inspect ECT sensor and wiring; verify coolant level; replace sensor.",
    ),
    "P0128": DTCInfo(
        code="P0128",
        description="Coolant thermostat below regulating temperature",
        severity="medium",
        system="Engine",
        recommended_action="Replace thermostat; verify coolant level and ECT sensor operation.",
    ),
    "P0130": DTCInfo(
        code="P0130",
        description="O2 sensor circuit malfunction (Bank 1, Sensor 1)",
        severity="medium",
        system="Emission",
        recommended_action="Inspect O2 sensor wiring; check for exhaust leaks; replace sensor.",
    ),
    "P0171": DTCInfo(
        code="P0171",
        description="System too lean (Bank 1)",
        severity="medium",
        system="Engine",
        recommended_action="Check for vacuum leaks, fuel pressure, and MAF sensor; inspect injectors.",
    ),
    "P0172": DTCInfo(
        code="P0172",
        description="System too rich (Bank 1)",
        severity="medium",
        system="Engine",
        recommended_action="Inspect fuel injectors, fuel pressure regulator, and O2 sensors.",
    ),
    # ── Powertrain: Fuel / Air Metering Injector (P0200-P0299) ─────────
    "P0200": DTCInfo(
        code="P0200",
        description="Injector circuit malfunction",
        severity="high",
        system="Engine",
        recommended_action="Check injector harness and connectors; test each injector resistance.",
    ),
    "P0217": DTCInfo(
        code="P0217",
        description="Engine over-temperature condition",
        severity="critical",
        system="Engine",
        recommended_action="Stop driving immediately; check coolant, radiator fan, and thermostat.",
    ),
    "P0230": DTCInfo(
        code="P0230",
        description="Fuel pump primary circuit malfunction",
        severity="high",
        system="Fuel System",
        recommended_action="Check fuel pump relay, fuse, and wiring; test fuel pump operation.",
    ),
    # ── Powertrain: Ignition / Misfire (P0300-P0399) ───────────────────
    "P0300": DTCInfo(
        code="P0300",
        description="Random/multiple cylinder misfire detected",
        severity="high",
        system="Engine",
        recommended_action="Check spark plugs, ignition coils, fuel injectors, and compression.",
    ),
    "P0301": DTCInfo(
        code="P0301",
        description="Cylinder 1 misfire detected",
        severity="high",
        system="Engine",
        recommended_action="Inspect cylinder 1 spark plug and ignition coil; check injector and compression.",
    ),
    "P0302": DTCInfo(
        code="P0302",
        description="Cylinder 2 misfire detected",
        severity="high",
        system="Engine",
        recommended_action="Inspect cylinder 2 spark plug and ignition coil; check injector and compression.",
    ),
    "P0303": DTCInfo(
        code="P0303",
        description="Cylinder 3 misfire detected",
        severity="high",
        system="Engine",
        recommended_action="Inspect cylinder 3 spark plug and ignition coil; check injector and compression.",
    ),
    "P0304": DTCInfo(
        code="P0304",
        description="Cylinder 4 misfire detected",
        severity="high",
        system="Engine",
        recommended_action="Inspect cylinder 4 spark plug and ignition coil; check injector and compression.",
    ),
    "P0325": DTCInfo(
        code="P0325",
        description="Knock sensor 1 circuit malfunction (Bank 1)",
        severity="medium",
        system="Engine",
        recommended_action="Check knock sensor wiring and connector; replace sensor if faulty.",
    ),
    "P0335": DTCInfo(
        code="P0335",
        description="Crankshaft Position (CKP) sensor circuit malfunction",
        severity="critical",
        system="Engine",
        recommended_action="Inspect CKP sensor and reluctor wheel; replace sensor if no signal.",
    ),
    # ── Powertrain: Emission Controls (P0400-P0499) ────────────────────
    "P0401": DTCInfo(
        code="P0401",
        description="Exhaust Gas Recirculation (EGR) flow insufficient",
        severity="medium",
        system="Emission",
        recommended_action="Clean EGR valve and passages; check vacuum lines; replace valve if stuck.",
    ),
    "P0420": DTCInfo(
        code="P0420",
        description="Catalyst system efficiency below threshold (Bank 1)",
        severity="medium",
        system="Emission",
        recommended_action="Check catalytic converter condition; inspect upstream/downstream O2 sensors.",
    ),
    "P0440": DTCInfo(
        code="P0440",
        description="Evaporative Emission (EVAP) system malfunction",
        severity="low",
        system="Emission",
        recommended_action="Inspect gas cap seal; check EVAP canister and purge valve; look for leaks.",
    ),
    "P0442": DTCInfo(
        code="P0442",
        description="EVAP system small leak detected",
        severity="low",
        system="Emission",
        recommended_action="Tighten or replace gas cap; smoke test EVAP system to locate leak.",
    ),
    # ── Powertrain: Vehicle Speed / Idle Control (P0500-P0599) ─────────
    "P0500": DTCInfo(
        code="P0500",
        description="Vehicle Speed Sensor (VSS) malfunction",
        severity="medium",
        system="Transmission",
        recommended_action="Inspect VSS connector and wiring; replace sensor if signal is absent.",
    ),
    "P0505": DTCInfo(
        code="P0505",
        description="Idle Air Control (IAC) system malfunction",
        severity="medium",
        system="Engine",
        recommended_action="Clean IAC valve; check for vacuum leaks; replace IAC if stuck.",
    ),
    "P0562": DTCInfo(
        code="P0562",
        description="System voltage low",
        severity="medium",
        system="Electrical",
        recommended_action="Test battery and charging system; inspect alternator output and wiring.",
    ),
    # ── Powertrain: Transmission (P0700-P0799) ─────────────────────────
    "P0700": DTCInfo(
        code="P0700",
        description="Transmission control system malfunction",
        severity="high",
        system="Transmission",
        recommended_action="Read transmission-specific DTCs; check TCM and wiring harness.",
    ),
    "P0715": DTCInfo(
        code="P0715",
        description="Input/Turbine speed sensor circuit malfunction",
        severity="high",
        system="Transmission",
        recommended_action="Inspect input speed sensor and connector; replace sensor if defective.",
    ),
    # ── Body Codes (B0xxx) ─────────────────────────────────────────────
    "B0001": DTCInfo(
        code="B0001",
        description="Driver frontal airbag deployment control stage 1",
        severity="critical",
        system="Restraint",
        recommended_action="Have airbag system inspected by dealer immediately; do not drive.",
    ),
    "B0028": DTCInfo(
        code="B0028",
        description="Driver side airbag module short to ground",
        severity="critical",
        system="Restraint",
        recommended_action="Inspect airbag module wiring for damage; replace module if shorted.",
    ),
    "B1000": DTCInfo(
        code="B1000",
        description="ECU (body control module) internal fault",
        severity="high",
        system="Body",
        recommended_action="Attempt ECU reset; reprogram or replace body control module if persists.",
    ),
    # ── Chassis Codes (C0xxx) ──────────────────────────────────────────
    "C0035": DTCInfo(
        code="C0035",
        description="Left front wheel speed sensor circuit malfunction",
        severity="high",
        system="Chassis / ABS",
        recommended_action="Inspect wheel speed sensor and wiring at left front; replace sensor.",
    ),
    "C0050": DTCInfo(
        code="C0050",
        description="Right rear wheel speed sensor circuit malfunction",
        severity="high",
        system="Chassis / ABS",
        recommended_action="Inspect wheel speed sensor and wiring at right rear; replace sensor.",
    ),
    "C0242": DTCInfo(
        code="C0242",
        description="PCM (Powertrain Control Module) indicated TCS malfunction",
        severity="medium",
        system="Chassis / TCS",
        recommended_action="Check PCM communication; inspect TCS actuator and wiring.",
    ),
    # ── Network Codes (U0xxx) ──────────────────────────────────────────
    "U0001": DTCInfo(
        code="U0001",
        description="High-speed CAN communication bus malfunction",
        severity="high",
        system="Network",
        recommended_action="Inspect CAN bus wiring and termination resistors; check for shorts.",
    ),
    "U0073": DTCInfo(
        code="U0073",
        description="Control module communication bus A off",
        severity="high",
        system="Network",
        recommended_action="Check CAN-bus wiring and connectors; verify module power supply.",
    ),
    "U0100": DTCInfo(
        code="U0100",
        description="Lost communication with ECM/PCM",
        severity="critical",
        system="Network",
        recommended_action="Check ECM/PCM power and ground circuits; inspect CAN bus for damage.",
    ),
    "U0121": DTCInfo(
        code="U0121",
        description="Lost communication with Anti-lock Brake System (ABS) module",
        severity="high",
        system="Network",
        recommended_action="Inspect ABS module power, ground, and CAN connections.",
    ),
    "U0140": DTCInfo(
        code="U0140",
        description="Lost communication with Body Control Module (BCM)",
        severity="medium",
        system="Network",
        recommended_action="Inspect BCM power supply and CAN bus connections.",
    ),
}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------
def get_dtc_description(code: str) -> DTCInfo | None:
    """Look up a DTC code in the database.

    Args:
        code: OBD-II DTC code (e.g. ``P0301``). Case-insensitive.

    Returns:
        ``DTCInfo`` if found, else ``None``.
    """
    return DTC_DATABASE.get(code.upper())


def get_all_dtc_codes() -> list[str]:
    """Return all DTC codes present in the database, sorted.

    Returns:
        Sorted list of DTC code strings.
    """
    return sorted(DTC_DATABASE.keys())


def get_dtc_by_severity(severity: Severity) -> list[DTCInfo]:
    """Filter DTC entries by severity level.

    Args:
        severity: One of ``low``, ``medium``, ``high``, ``critical``.

    Returns:
        List of ``DTCInfo`` objects matching the severity.
    """
    return [
        info
        for info in DTC_DATABASE.values()
        if info.severity == severity
    ]


def get_full_database() -> dict[str, DTCInfo]:
    """Return the complete DTC database.

    Returns:
        Mapping of code string to ``DTCInfo`` for every entry.
    """
    return DTC_DATABASE
