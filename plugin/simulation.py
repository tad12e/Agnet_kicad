import subprocess
import os
import tempfile

def run_ngspice_simulation(netlist_path: str, analysis: str = ".tran 1us 1ms") -> str:
    """
    Run ngspice simulation on a .cir netlist file.
    
    Args:
        netlist_path: Full path to .cir file
        analysis: SPICE analysis command (e.g. .tran 1us 1ms or .ac dec 100 1 1Meg)
    """
    if not os.path.exists(netlist_path):
        return f"ERROR: Netlist file not found: {netlist_path}"

    with open(netlist_path, 'r') as f:
        content = f.read()

    if '.tran' not in content.lower() and '.ac' not in content.lower():
        content = content.replace('.end', f'{analysis}\n.end')
        with open(netlist_path, 'w') as f:
            f.write(content)

    temp_out = os.path.join(tempfile.gettempdir(), 'ngspice_out.txt')

    try:
        result = subprocess.run(
            ['ngspice', '-b', '-o', temp_out, netlist_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout + result.stderr
        if os.path.exists(temp_out):
            with open(temp_out, 'r') as f:
                output += "\n--- Simulation Output ---\n" + f.read()
        return output[:3000]
    except FileNotFoundError:
        return "ERROR: ngspice CLI not found. Please ensure ngspice is installed and added to PATH."
    except subprocess.TimeoutExpired:
        return "ERROR: ngspice simulation timed out after 30 seconds."
    except Exception as e:
        return f"ERROR running simulation: {e}"
