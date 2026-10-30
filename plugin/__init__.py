import os
import pcbnew

class KiCadAIAgentPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "KiCad AI Copilot"
        self.category = "Automation"
        self.description = "Autonomous AI Schematic & PCB Design Assistant + MCP Server"
        self.show_toolbar_button = True
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icon.png")
        if os.path.exists(icon_path):
            self.icon_file_name = icon_path

    def Run(self):
        from .ui import AgentSidebarDialog
        board = pcbnew.GetBoard()
        dialog = AgentSidebarDialog(None, board)
        dialog.Show()

KiCadAIAgentPlugin().register()
