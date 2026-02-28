# DBC — Vehicle CAN Database Files

This directory contains CAN database (DBC) files and associated configuration
for feeding vehicle data into Kuksa Databroker via `kuksa-can-provider`.

## Directory Structure

```
dbc/
├── README.md                          # This file
├── hyundai_kia/                       # Hyundai/Kia vehicle profile
│   ├── hyundai_kia_generic.dbc        # CAN message & signal definitions
│   ├── vss_dbc.json                   # DBC signal → VSS path mapping
│   └── candump.log                    # Pre-generated CAN frame replay
├── tesla_model3/                      # Tesla Model 3 vehicle profile
│   ├── tesla_model3.dbc               # CAN message & signal definitions
│   ├── vss_dbc.json                   # DBC signal → VSS path mapping
│   └── candump.log                    # Pre-generated CAN frame replay
└── scripts/
    ├── generate_candump.py            # Candump file generator
    ├── requirements.txt               # Python dependencies
    └── test_generate_candump.py       # Generator tests
```

## How It Works

### Architecture

```
Mode A (Default — Python Simulator):
  simulator → gRPC → Kuksa Databroker → MCP Server

Mode B (DBC Feeder):
  candump.log → kuksa-can-provider → gRPC → Kuksa Databroker → MCP Server
```

The MCP server doesn't know or care how data arrives in the Databroker.
It always reads via the same gRPC API. This proves **zero code changes**
are needed when switching data sources or vehicle profiles.

### Why Candump Replay?

macOS (and Docker Desktop) doesn't support the `vcan` kernel module
required for virtual CAN interfaces. Instead, we pre-generate
candump-format log files containing encoded CAN frames.
`kuksa-can-provider` replays these files as if reading from a live
CAN bus.

For Linux environments with vcan support, see `infra/vcan-setup.sh`.

## Switching Vehicle Profiles

### Default (Hyundai/Kia)

```bash
docker compose --profile dbc-feeder up
```

### Tesla Model 3

```bash
VEHICLE_PROFILE=tesla_model3 docker compose --profile dbc-feeder up
```

### Verify the Switch

After switching profiles, the same MCP queries return data:

```bash
# These commands work identically regardless of vehicle profile
# (via MCP Inspector or Claude Desktop)
get_vehicle_signal("Vehicle.Speed")
get_multiple_signals(["Vehicle.Speed", "Vehicle.Powertrain.CombustionEngine.Speed"])
```

## Signal Coverage

Both profiles map to the same 9 VSS signals:

| VSS Path | Hyundai DBC Signal | Tesla DBC Signal |
|----------|-------------------|-----------------|
| Vehicle.Speed | VehicleSpeed | DI_vehicleSpeed |
| Vehicle.TraveledDistance | TraveledDistance | DI_odometer |
| Vehicle.Powertrain.CombustionEngine.Speed | EngineRPM | DI_motorRPM |
| Vehicle.Powertrain.CombustionEngine.ECT | EngineCoolantTemp | DI_inverterTemp |
| Vehicle.Powertrain.TractionBattery.StateOfCharge.Current | BatterySOC | BMS_stateOfCharge |
| Vehicle.Powertrain.TractionBattery.CurrentVoltage | BatteryVoltage | BMS_packVoltage |
| Vehicle.Powertrain.TractionBattery.Temperature | BatteryTemp | BMS_packTemp |
| Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature | SetTemp | HVAC_setpointTemp |
| Vehicle.Cabin.HVAC.AmbientAirTemperature | AmbientTemp | HVAC_cabinTemp |

> **Note:** `Vehicle.OBD.DTCList` is intentionally NOT mapped via DBC.
> OBD-II DTC codes use the UDS protocol (ISO 14229), not standard CAN
> data frames. This is a deliberate design choice reflecting real
> automotive architecture.

## Adding a New Vehicle Profile

1. Create a new directory: `dbc/<profile_name>/`
2. Add a DBC file with CAN message definitions for your vehicle
3. Create `vss_dbc.json` mapping your DBC signals to VSS paths
4. Generate candump data:
   ```bash
   cd dbc/scripts
   pip install -r requirements.txt
   python generate_candump.py \
     --dbc ../<profile_name>/<your_file>.dbc \
     --output ../<profile_name>/candump.log \
     --duration 60
   ```
5. Test: `VEHICLE_PROFILE=<profile_name> docker compose --profile dbc-feeder up`

## Regenerating Candump Files

```bash
cd dbc/scripts
pip install -r requirements.txt

# Hyundai/Kia
python generate_candump.py \
  --dbc ../hyundai_kia/hyundai_kia_generic.dbc \
  --output ../hyundai_kia/candump.log \
  --duration 60

# Tesla Model 3
python generate_candump.py \
  --dbc ../tesla_model3/tesla_model3.dbc \
  --output ../tesla_model3/candump.log \
  --duration 60
```
