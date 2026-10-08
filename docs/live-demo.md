# Live external-LLM MCP demo

This is a small, repeatable demo of the KiCad agent contract. The external LLM
is the reasoning brain; the MCP server is the controlled body. The model never
writes KiCad files or S-expressions directly.

## 1. Prepare a live schematic

1. Create or open a disposable `led.kicad_sch` in KiCad.
2. Enable **Preferences → Plugins → Enable KiCad API**.
3. Keep the schematic editor open and use one KiCad instance.
4. Start the MCP server from the repository root:

   ```powershell
   python -m kicad_agent.mcp.server `
     --backend auto `
     --sch C:\demo\led.kicad_sch
   ```

Configure the external LLM's MCP client to launch this command over stdio.
The client can be Claude Desktop, an MCP-capable IDE, or another compatible
host; its configuration format is host-specific.

`--backend auto` uses the live KiCad IPC lane when its socket is available.
For a deterministic file-only rehearsal, use `--backend sexpr` instead.
Use `--backend ipc-fallback` only when an explicit file fallback is desired;
`ipc` and `auto` report IPC failures rather than silently editing a file.

## 2. Run the workflow

Ask the external LLM:

> Add a power LED circuit: D1 (LED), R1 (1k), and connections from VCC to
> GND. Show me the plan before making changes.

The live conversation should demonstrate these steps:

1. **Inspect** — call `session_info`, then `get_schematic_state` (and
   `search_symbols` if library IDs are unknown).
2. **Plan** — the LLM presents a short ordered plan, for example: place D1,
   place R1, add wires, verify connectivity, run ERC, and save. It should wait
   for the operator before risky actions.
3. **Approve** — construction edits can proceed under the default policy, but
   destructive operations and saving return `status: "approval_required"` with
   a request ID. The LLM displays the reason and calls:

   ```json
   {"request_id": "<id-from-response>", "decision": "allow"}
   ```

   using the `approve_action` tool. A denied or unresolved request is never
   executed.
4. **Execute** — call `add_symbol` for D1 and R1, then `add_wire` (and
   `add_junction` when required). Keep each tool result in the conversation;
   results include structured success/error information.
5. **Verify** — call `get_schematic_state`,
   `verify_schematic_connectivity`, and `run_erc`. Verification must inspect
   the resulting state rather than trusting a successful write response.
6. **Repair** — if verification reports a missing connection, dangling pin, or
   backend error, explain the failure, issue the smallest corrective tool call,
   and run verification again. If the live lane cannot commit, report that
   fact and continue only when the fallback result explicitly says it wrote a
   file.
7. **Save and finish** — after verification passes, call `save_schematic`.
   If approval is requested, obtain it with `approve_action`, then confirm the
   final state and backend used.

The important evidence for the demo is the trace, not just a changed canvas:
the transcript should show the plan, approval boundary, action results,
independent verification, any repair attempt, and the final backend status.

## 3. Demonstrate fallback honestly

Stop or make IPC unavailable, then repeat the same request with:

```powershell
python -m kicad_agent.mcp.server `
  --backend sexpr `
  --sch C:\demo\led-fallback.kicad_sch
```

The file backend writes the S-expression document directly. In live mode, an
IPC write may fall back to that file backend only in `ipc-fallback` mode; the
result must identify this with fields such as `backend_used: "ipc->sexpr"` and
`fallback_used: true`. If the file backend does not support the operation, the
result is a failure and includes both diagnostics. Treat a successful fallback
as a file update, not proof that the
currently displayed KiCad document changed. Reopen or reload the file in
KiCad, then repeat inspection and verification before declaring success.

## 4. Optional Tier 2 comparison

For a comparison with a server-side provider, open a document and call
`run_design_task` with the same natural-language request. This path performs
planning, execution, verification, and repair inside the runtime, but it
requires `ANTHROPIC_API_KEY`. The external-LLM walkthrough above uses Tier 1
primitive MCP tools and therefore keeps the reasoning model outside the server.
