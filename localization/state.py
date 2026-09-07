import json
import os

# Create a shared file path that both terminals/containers can access.
# In Docker, TELEMETRY_FILE is set to a dedicated shared-volume path so we
# never mount a volume directly over this source folder (that would hide
# the actual .py files baked into the image and break every import here).
STATE_FILE = os.environ.get(
    "TELEMETRY_FILE",
    os.path.join(os.path.dirname(__file__), "telemetry.json")
)

default_telemetry = {
    "x": 0,
    "y": 0,
    "uncertainty": 0,
    "mode": "connecting",
    "reasoning": "System initialized. Awaiting live telemetry stream."
}

def _read_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return default_telemetry.copy()

def _write_state(data):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print(f"State write error: {e}")

def update_telemetry(x, y, uncertainty, mode, reasoning):
    data = _read_state()
    data["x"] = round(float(x), 2)
    data["y"] = round(float(y), 2)
    data["uncertainty"] = round(float(uncertainty), 2)
    data["mode"] = mode
    data["reasoning"] = reasoning
    _write_state(data)

def get_current_position():
    data = _read_state()
    return {"x": data["x"], "y": data["y"], "uncertainty": data["uncertainty"]}

def get_rover_mode():
    return _read_state()["mode"]

def get_reasoning():
    return _read_state()["reasoning"]