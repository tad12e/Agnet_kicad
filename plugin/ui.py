import wx
import threading
from .agent import run_agent

class AgentSidebarDialog(wx.Frame):
    def __init__(self, parent, board):
        super().__init__(parent, title="KiCad AI Agent", size=(400, 600))
        self.board = board
        self._build_ui()
    
    def _build_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Chat history display
        self.chat_display = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        
        # Input row
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.input = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER)
        self.send_btn = wx.Button(panel, label="Send")
        hbox.Add(self.input, proportion=1, flag=wx.EXPAND)
        hbox.Add(self.send_btn)
        
        vbox.Add(self.chat_display, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(hbox, flag=wx.EXPAND | wx.ALL, border=5)
        panel.SetSizer(vbox)
        
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.input.Bind(wx.EVT_TEXT_ENTER, self.on_send)
        
        self.append_message("System", "KiCad AI Agent Ready. Type a command to start!")
    
    def on_send(self, event):
        msg = self.input.GetValue().strip()
        if not msg:
            return
        self.input.Clear()
        self.append_message("You", msg)
        
        # Disable send while processing
        self.send_btn.Disable()
        
        thread = threading.Thread(
            target=self._run_agent_thread, args=(msg,), daemon=True
        )
        thread.start()
    
    def _run_agent_thread(self, msg):
        def on_tool(name, args, result):
            wx.CallAfter(self.append_status, f"🔧 {name}... ✅")
        
        def on_done(text):
            wx.CallAfter(self.append_message, "Agent", text)
            wx.CallAfter(self.send_btn.Enable)
        
        try:
            run_agent(msg, on_tool_call=on_tool, on_response=on_done)
        except Exception as e:
            wx.CallAfter(self.append_message, "System Error", str(e))
            wx.CallAfter(self.send_btn.Enable)
    
    def append_message(self, sender, text):
        self.chat_display.AppendText(f"\n{sender}: {text}\n")
    
    def append_status(self, text):
        self.chat_display.AppendText(f"  {text}\n")
