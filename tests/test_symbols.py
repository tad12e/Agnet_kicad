"""Unit tests for kicad_api.symbols."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kicad_api.symbols import SymbolResolver, SymbolLibraryParser, SymbolInfo, PinInfo


def test_symbol_resolver_builtins():
    resolver = SymbolResolver()
    r = resolver.get("Device:R")
    assert r is not None
    assert r.lib_id == "Device:R"
    assert r.pin_count == 2
    pin1 = r.get_pin("1")
    assert pin1 is not None
    assert pin1.pin_type == "passive"


def test_symbol_resolver_search():
    resolver = SymbolResolver()
    resistors = resolver.search("resistor")
    assert len(resistors) > 0
    assert any(s.lib_id == "Device:R" for s in resistors)


def test_symbol_parser_string():
    sample_sym = """(kicad_symbol_lib
    (version 20211014)
    (generator kicad_symbol_editor)
    (symbol "TestResistor"
        (property "Reference" "R" (at 2 0 90))
        (property "Value" "R" (at 0 0 90))
        (property "Description" "A test resistor")
        (symbol "TestResistor_0_1"
            (rectangle (start -1 -2) (end 1 2))
        )
        (symbol "TestResistor_1_1"
            (pin passive line (at 0 3.81 270) (name "1") (number "1"))
            (pin passive line (at 0 -3.81 90) (name "2") (number "2"))
        )
    )
)"""
    symbols = SymbolLibraryParser.parse_string(sample_sym, library_name="CustomLib")
    assert len(symbols) == 1
    sym = symbols[0]
    assert sym.lib_id == "CustomLib:TestResistor"
    assert sym.description == "A test resistor"
    assert sym.pin_count == 2
    assert sym.get_pin("1") is not None
    assert sym.get_pin("2") is not None
