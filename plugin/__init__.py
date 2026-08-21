import pcbnew
import wx
from .ui import AgentSidebarDialog

class KiCadAIAgentPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "AI Agent"
        self.category = "AI Assistant"
        self.description = "Natural language PCB design assistant"
        self.show_toolbar_button = True

    def Run(self):
        board = pcbnew.GetBoard()
        dialog = AgentSidebarDialog(None, board)
        dialog.Show()

KiCadAIAgentPlugin().register()
