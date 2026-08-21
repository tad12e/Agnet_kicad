"""
Mock implementation of pcbnew module for offline testing.
"""

F_Cu = 0

class ActionPlugin:
    def register(self): pass
    def defaults(self): pass
    def Run(self): pass

class VECTOR2I:
    def __init__(self, x, y):
        self.x = x
        self.y = y

class MockFootprint:
    def __init__(self, ref="R1", val="10k", x=100000000, y=100000000, layer="F.Cu"):
        self._ref = ref
        self._val = val
        self._x = x
        self._y = y
        self._layer = layer

    def SetReference(self, ref): self._ref = ref
    def GetReference(self): return self._ref
    def SetValue(self, val): self._val = val
    def GetValue(self): return self._val
    def SetPosition(self, vec):
        self._x = vec.x
        self._y = vec.y
    def GetX(self): return self._x
    def GetY(self): return self._y
    def GetLayerName(self): return self._layer

class MockTrack:
    def __init__(self, board=None):
        self.board = board
        self.start = None
        self.end = None
        self.width = 0
        self.layer = F_Cu

    def SetStart(self, vec): self.start = vec
    def SetEnd(self, vec): self.end = vec
    def SetWidth(self, w): self.width = w
    def SetLayer(self, l): self.layer = l

class MockNet:
    def __init__(self, name):
        self._name = name
    def GetNetname(self): return self._name

class MockNetInfo:
    def __init__(self, nets):
        self._nets = nets
    def NetsByName(self):
        return self._nets

class MockConnectivity:
    def RecalculateRatsnest(self): pass
    def GetUnconnectedCount(self, *args): return 0
    def GetUnconnectedEdges(self): return []

class MockBoard:
    def __init__(self):
        self.footprints = []
        self.tracks = []
        self.nets = {"0": MockNet("GND"), "1": MockNet("VCC")}
        self.connectivity = MockConnectivity()
        self.net_info = MockNetInfo(self.nets)

    def GetFootprints(self):
        return self.footprints

    def GetConnectivity(self):
        return self.connectivity

    def GetNetInfo(self):
        return self.net_info

    def GetFileName(self):
        return "mock_board.kicad_pcb"

    def Add(self, item):
        if isinstance(item, MockFootprint):
            self.footprints.append(item)
        elif isinstance(item, MockTrack):
            self.tracks.append(item)

_BOARD_INSTANCE = MockBoard()

def GetBoard():
    return _BOARD_INSTANCE

def FootprintLoad(lib_path, fp_name):
    return MockFootprint(ref="REF", val="VAL")

def Refresh():
    pass
