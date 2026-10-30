"""Interactive wxPython GUI for KiCad AI Agent ActionPlugin."""

import os
import threading
import wx

from .agent import run_agent, get_active_files
from .config import load_config, save_config
from .mcp_config_helper import auto_configure_all


class SettingsDialog(wx.Dialog):
    """Configuration dialog for API keys and LLM providers."""

    def __init__(self, parent):
        super().__init__(parent, title="AI Agent Settings", size=(420, 320))
        self.cfg = load_config()
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Provider selection
        lbl_p = wx.StaticText(panel, label="LLM Provider:")
        self.choice_provider = wx.Choice(panel, choices=["Gemini", "Anthropic"])
        current_provider = self.cfg.get("provider", "gemini").capitalize()
        self.choice_provider.SetStringSelection(current_provider if current_provider in ["Gemini", "Anthropic"] else "Gemini")

        # Gemini API Key
        lbl_g = wx.StaticText(panel, label="Gemini API Key:")
        self.txt_gemini = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=self.cfg.get("gemini_api_key", ""))

        # Anthropic API Key
        lbl_a = wx.StaticText(panel, label="Anthropic API Key:")
        self.txt_anthropic = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=self.cfg.get("anthropic_api_key", ""))

        # Model Name
        lbl_m = wx.StaticText(panel, label="Model Name:")
        self.txt_model = wx.TextCtrl(panel, value=self.cfg.get("model", "gemini-2.5-flash"))

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_save = wx.Button(panel, wx.ID_OK, label="Save")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_sizer.Add(btn_save, flag=wx.RIGHT, border=10)
        btn_sizer.Add(btn_cancel)

        # Layout
        vbox.Add(lbl_p, flag=wx.LEFT | wx.TOP, border=10)
        vbox.Add(self.choice_provider, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        vbox.Add(lbl_g, flag=wx.LEFT | wx.TOP, border=10)
        vbox.Add(self.txt_gemini, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        vbox.Add(lbl_a, flag=wx.LEFT | wx.TOP, border=10)
        vbox.Add(self.txt_anthropic, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        vbox.Add(lbl_m, flag=wx.LEFT | wx.TOP, border=10)
        vbox.Add(self.txt_model, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        vbox.Add(btn_sizer, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=15)
        panel.SetSizer(vbox)

        btn_save.Bind(wx.EVT_BUTTON, self.on_save)

    def on_save(self, event):
        self.cfg["provider"] = self.choice_provider.GetStringSelection().lower()
        self.cfg["gemini_api_key"] = self.txt_gemini.GetValue().strip()
        self.cfg["anthropic_api_key"] = self.txt_anthropic.GetValue().strip()
        self.cfg["model"] = self.txt_model.GetValue().strip()
        save_config(self.cfg)
        self.EndModal(wx.ID_OK)


class AgentSidebarDialog(wx.Frame):
    """Main AI Assistant window docked inside KiCad."""

    def __init__(self, parent, board=None):
        super().__init__(parent, title="KiCad AI Copilot", size=(450, 650))
        self.board = board
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Top Control Row
        top_hbox = wx.BoxSizer(wx.HORIZONTAL)
        lbl_target = wx.StaticText(panel, label="Target:")
        self.domain_choice = wx.Choice(panel, choices=["Schematic", "PCB"])
        self.domain_choice.SetSelection(0)

        self.btn_settings = wx.Button(panel, label="⚙️ Settings")
        self.btn_mcp_setup = wx.Button(panel, label="⚡ Connect Claude/Cursor")

        top_hbox.Add(lbl_target, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        top_hbox.Add(self.domain_choice, proportion=1, flag=wx.RIGHT, border=5)
        top_hbox.Add(self.btn_settings, flag=wx.RIGHT, border=5)
        top_hbox.Add(self.btn_mcp_setup)

        # Chat display area
        self.chat_display = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        self.chat_display.SetBackgroundColour(wx.Colour(248, 249, 250))

        # Bottom Input Row
        input_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.send_btn = wx.Button(panel, label="Send")
        input_hbox.Add(self.input, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)
        input_hbox.Add(self.send_btn)

        # Main Layout
        vbox.Add(top_hbox, flag=wx.EXPAND | wx.ALL, border=8)
        vbox.Add(self.chat_display, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)
        vbox.Add(input_hbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)
        panel.SetSizer(vbox)

        # Event Bindings
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.input.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        self.btn_settings.Bind(wx.EVT_BUTTON, self.on_open_settings)
        self.btn_mcp_setup.Bind(wx.EVT_BUTTON, self.on_mcp_setup)

        # Initial greeting
        pcb_file, sch_file = get_active_files()
        active_doc = sch_file or pcb_file or "Default Project"
        self.append_message("System", f"🚀 KiCad AI Copilot ready!\nActive file: {os.path.basename(active_doc)}")

    def on_open_settings(self, event):
        dlg = SettingsDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            self.append_message("System", "✅ Settings updated successfully.")
        dlg.Destroy()

    def on_mcp_setup(self, event):
        results = auto_configure_all()
        lines = []
        for name, ok, path in results:
            status = "✅ Configured" if ok else "❌ Failed"
            lines.append(f"{name}: {status}")

        msg = "Automatic MCP Configuration Results:\n\n" + "\n".join(lines) + "\n\nYou can now restart Claude Desktop or Cursor to use KiCad MCP tools!"
        wx.MessageBox(msg, "MCP 1-Click Setup", wx.OK | wx.ICON_INFORMATION)
        self.append_message("System", "⚡ MCP Configuration applied to Claude & Cursor.")

    def on_send(self, event):
        msg = self.input.GetValue().strip()
        if not msg:
            return
        self.input.Clear()
        self.append_message("You", msg)

        domain = self.domain_choice.GetStringSelection().lower()
        self.send_btn.Disable()
        self.input.Disable()

        thread = threading.Thread(
            target=self._run_agent_thread, args=(msg, domain), daemon=True
        )
        thread.start()

    def _run_agent_thread(self, msg: str, domain: str):
        def on_tool(name, args, result):
            wx.CallAfter(self.append_status, f"🔧 {name}...")

        def on_done(text):
            wx.CallAfter(self.append_message, "Agent", text)
            wx.CallAfter(self._enable_inputs)
            # Refresh KiCad board view if available
            try:
                import pcbnew
                pcbnew.Refresh()
            except Exception:
                pass

        try:
            run_agent(msg, domain=domain, on_tool_call=on_tool, on_response=on_done)
        except Exception as e:
            wx.CallAfter(self.append_message, "Error", str(e))
            wx.CallAfter(self._enable_inputs)

    def _enable_inputs(self):
        self.send_btn.Enable()
        self.input.Enable()
        self.input.SetFocus()

    def append_message(self, sender: str, text: str):
        self.chat_display.AppendText(f"\n[{sender}]\n{text}\n")

    def append_status(self, text: str):
        self.chat_display.AppendText(f"  {text}\n")
