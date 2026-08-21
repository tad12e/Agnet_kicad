from typing import List, Optional
from .component import Component
from .wire import Wire
from .junction import Junction
from .power import PowerSymbol

class Schematic:
    """
    High-level Schematic container maintaining collections of components, wires, junctions, and power symbols.
    """

    def __init__(self) -> None:
        self.components: List[Component] = []
        self.wires: List[Wire] = []
        self.junctions: List[Junction] = []
        self.power_symbols: List[PowerSymbol] = []

    def add_component(self, component: Component) -> Component:
        self.components.append(component)
        return component

    def add_wire(self, wire: Wire) -> Wire:
        self.wires.append(wire)
        return wire

    def add_junction(self, junction: Junction) -> Junction:
        self.junctions.append(junction)
        return junction

    def add_power_symbol(self, power_symbol: PowerSymbol) -> PowerSymbol:
        self.power_symbols.append(power_symbol)
        return power_symbol

    # Convenience factory helpers

    def resistor(self, reference: str, value: str, x: float, y: float, footprint: str = "") -> Component:
        comp = Component(lib_id="Device:R", reference=reference, value=value, x=x, y=y, footprint=footprint)
        return self.add_component(comp)

    def capacitor(self, reference: str, value: str, x: float, y: float, footprint: str = "") -> Component:
        comp = Component(lib_id="Device:C", reference=reference, value=value, x=x, y=y, footprint=footprint)
        return self.add_component(comp)

    def led(self, reference: str, value: str, x: float, y: float, footprint: str = "") -> Component:
        comp = Component(lib_id="Device:LED", reference=reference, value=value, x=x, y=y, footprint=footprint)
        return self.add_component(comp)

    def switch(self, reference: str, value: str, x: float, y: float, footprint: str = "") -> Component:
        comp = Component(lib_id="Switch:SW_Push", reference=reference, value=value, x=x, y=y, footprint=footprint)
        return self.add_component(comp)

    def arduino(self, reference: str, value: str, x: float, y: float, footprint: str = "") -> Component:
        comp = Component(lib_id="MCU_Module:Arduino_Leonardo", reference=reference, value=value, x=x, y=y, footprint=footprint)
        return self.add_component(comp)

    def wire(self, x1: float, y1: float, x2: float, y2: float) -> Wire:
        w = Wire(x1, y1, x2, y2)
        return self.add_wire(w)

    def junction(self, x: float, y: float) -> Junction:
        j = Junction(x, y)
        return self.add_junction(j)

    def power(self, name: str, x: float, y: float) -> PowerSymbol:
        p = PowerSymbol(name=name, x=x, y=y)
        return self.add_power_symbol(p)

    def save(self, filepath: str) -> None:
        from .writer import KiCadWriter
        writer = KiCadWriter(self)
        writer.save(filepath)
