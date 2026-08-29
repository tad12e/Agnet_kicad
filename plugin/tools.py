"""KiCad ActionPlugin tools adapter delegating to kicad_agent."""

import json
from kicad_agent.backends.pcbnew import PcbnewBackend, mm_to_pcbnew, pcbnew_to_mm, FOOTPRINT_MAP
from kicad_agent.core.actions import Action, ActionType

_backend = PcbnewBackend()

def mm(val):
    return mm_to_pcbnew(val)

def nm(val):
    return pcbnew_to_mm(val)

def get_board_state():
    res = _backend.execute(Action(action_type=ActionType.GET_STATE))
    return json.dumps(res.data, indent=2)

def place_component(ref, component_type, value, x, y):
    res = _backend.execute(Action(
        action_type=ActionType.ADD_FOOTPRINT,
        parameters={
            "reference": ref,
            "component_type": component_type,
            "value": value,
            "x": x,
            "y": y,
        }
    ))
    if res.success:
        return f"OK: Placed {ref} ({value}) at ({x}mm, {y}mm)"
    return f"ERROR: {res.error.message if res.error else 'Failed to place component'}"

def add_trace(x1, y1, x2, y2, width_mm=0.25):
    res = _backend.execute(Action(
        action_type=ActionType.ADD_TRACK,
        parameters={"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width_mm": width_mm}
    ))
    if res.success:
        return f"OK: Trace ({x1},{y1}) to ({x2},{y2}), width={width_mm}mm"
    return f"ERROR: {res.error.message if res.error else 'Failed to add trace'}"

def run_drc():
    res = _backend.execute(Action(action_type=ActionType.RUN_DRC))
    return json.dumps(res.data, indent=2)

def save_board():
    res = _backend.execute(Action(action_type=ActionType.SAVE_DOCUMENT))
    return f"OK: Saved board" if res.success else f"ERROR: {res.error}"