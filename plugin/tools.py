import pcbnew
import json
import os
import subprocess

def mm(val):
    return int(val * 1e6)

def nm(val):
    return round(val / 1e6, 2)

def get_footprint_base():
    for env_var in ["KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD8_FOOTPRINT_DIR", "KICAD7_FOOTPRINT_DIR", "KICAD_FOOTPRINT_DIR"]:
        val = os.environ.get(env_var)
        if val and os.path.exists(val):
            return val
    for ver in ["10.0", "9.0", "8.0", "7.0"]:
        candidate = f"C:\\Program Files\\KiCad\\{ver}\\share\\kicad\\footprints"
        if os.path.exists(candidate):
            return candidate
    return r"C:\Program Files\KiCad\10.0\share\kicad\footprints"


FOOTPRINT_MAP = {
    "resistor":  ("Resistor_SMD.pretty",  "R_0402"),
    "capacitor": ("Capacitor_SMD.pretty", "C_0402"),
    "led":       ("LED_SMD.pretty",       "LED_0402"),
    "inductor":  ("Inductor_SMD.pretty",  "L_0402"),
}

def resolve_footprint_name(lib_path, name):
    exact_file = os.path.join(lib_path, f"{name}.kicad_mod")
    if os.path.exists(exact_file):
        return name
    if os.path.exists(lib_path):
        for fname in os.listdir(lib_path):
            if fname.startswith(name) and fname.endswith(".kicad_mod"):
                return fname[:-10]
    return name


def get_board_state():
    board = pcbnew.GetBoard()
    components = []
    for fp in board.GetFootprints():
        components.append({
            "ref":   fp.GetReference(),
            "value": fp.GetValue(),
            "x":     nm(fp.GetX()),
            "y":     nm(fp.GetY()),
            "layer": fp.GetLayerName(),
        })
    nets = []
    for net in board.GetNetInfo().NetsByName().values():
        name = net.GetNetname()
        if name:
            nets.append(name)
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    unconnected = connectivity.GetUnconnectedCount(False)
    return json.dumps({
        "component_count":  len(components),
        "components":       components,
        "nets":             nets,
        "unconnected_pads": unconnected,
        "board_file":       board.GetFileName(),
    }, indent=2)

def place_component(ref, component_type, value, x, y):
    board = pcbnew.GetBoard()
    existing = [fp.GetReference() for fp in board.GetFootprints()]
    if ref in existing:
        return f"ERROR: {ref} already exists. Use a different reference."
    if component_type not in FOOTPRINT_MAP:
        return f"ERROR: Unknown type '{component_type}'. Use: {list(FOOTPRINT_MAP.keys())}"
    lib_folder, footprint_name = FOOTPRINT_MAP[component_type]
    
    footprint_base = get_footprint_base()
    lib_path = os.path.join(footprint_base, lib_folder)
    if not os.path.exists(lib_path):
        return f"ERROR: Footprint library path does not exist: {lib_path}"

    actual_footprint_name = resolve_footprint_name(lib_path, footprint_name)
    fp = pcbnew.FootprintLoad(lib_path, actual_footprint_name)
    if fp is None:
        return f"ERROR: Could not load {actual_footprint_name} from {lib_path}"
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
    board.Add(fp)
    pcbnew.Refresh()
    return f"OK: Placed {ref} ({value}) at ({x}mm, {y}mm)"

def add_trace(x1, y1, x2, y2, width_mm=0.25):
    board = pcbnew.GetBoard()
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(mm(x1), mm(y1)))
    track.SetEnd(pcbnew.VECTOR2I(mm(x2), mm(y2)))
    track.SetWidth(mm(width_mm))
    track.SetLayer(pcbnew.F_Cu)
    board.Add(track)
    pcbnew.Refresh()
    return f"OK: Trace ({x1},{y1}) to ({x2},{y2}), width={width_mm}mm"

def run_drc():
    board = pcbnew.GetBoard()
    connectivity = board.GetConnectivity()
    connectivity.RecalculateRatsnest()
    unconnected = connectivity.GetUnconnectedCount(False)
    return json.dumps({
        "status":            "clean" if unconnected == 0 else "has errors",
        "unconnected_count": unconnected,
    }, indent=2)

def save_board():
    board = pcbnew.GetBoard()
    filepath = board.GetFileName()
    if not filepath:
        return "ERROR: No file path. Save manually first."
    board.Save(filepath)
    return f"OK: Saved to {filepath}"