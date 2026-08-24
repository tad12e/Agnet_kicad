"""Helper to inject symbol definitions into a schematic's lib_symbols section."""
import re
import os

def extract_symbol_definition(sym_lib_path: str, symbol_name: str) -> str:
    """Extract a symbol block from a .kicad_sym file."""
    with open(sym_lib_path, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = rf'\(symbol\s+"{re.escape(symbol_name)}"\s+'
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Symbol '{symbol_name}' not found in {sym_lib_path}")

    start = match.start()
    depth = 0
    end = start
    for i in range(start, len(content)):
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    return content[start:end]


def inject_lib_symbols_into_schematic(sch_path: str, symbols: dict[str, str]):
    """Inject symbol definitions into the (lib_symbols ...) section of a .kicad_sch file."""
    with open(sch_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find (lib_symbols ...) block
    match = re.search(r'\(lib_symbols(\s*|\s+[\s\S]*?)\n\t\)', content)
    if not match:
        # Match (lib_symbols) with no content
        match = re.search(r'\(lib_symbols\)', content)

    if not match:
        raise ValueError(f"Could not find (lib_symbols) in {sch_path}")

    # Build the new lib_symbols block
    lib_symbols_text = "(lib_symbols\n"
    for full_lib_id, sym_s_expr in symbols.items():
        # Replace the top symbol name with full lib_id if needed, or format
        # In KiCad 7/8/9/10, (lib_symbols (symbol "Device:R" ...))
        formatted_sym = re.sub(r'^\(symbol\s+"([^"]+)"', f'(symbol "{full_lib_id}"', sym_s_expr.strip())
        # Indent each line
        indented = "\n".join("\t\t" + line for line in formatted_sym.split("\n"))
        lib_symbols_text += indented + "\n"
    lib_symbols_text += "\t)"

    # Replace in file
    new_content = content[:match.start()] + lib_symbols_text + content[match.end():]
    with open(sch_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"✓ Injected {len(symbols)} symbol definitions into {sch_path}")


if __name__ == "__main__":
    device_sym_path = r"C:\Program Files\KiCad\10.0\share\kicad\symbols\Device.kicad_sym"
    r_def = extract_symbol_definition(device_sym_path, "R")
    sch_file = r"C:\Users\hp\ECE\test\Agent\Agent.kicad_sch"
    inject_lib_symbols_into_schematic(sch_file, {"Device:R": r_def})
