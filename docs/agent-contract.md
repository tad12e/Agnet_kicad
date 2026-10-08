# KiCad Agent Contract

This document defines the boundary between an external LLM client, the KiCad
agent runtime, and KiCad backends. It is the contract for MCP and future CLI
or UI adapters.

## Responsibilities

| Layer | Responsibility | Must not do |
|---|---|---|
| LLM client | Understand user intent, choose the next structured decision, explain results | Edit KiCad files directly or bypass runtime validation |
| Agent runtime | Manage tasks, plans, permissions, action validation, execution, observation, verification, repair, and session state | Assume that a model decision is correct |
| MCP adapter | Expose versioned schemas and translate JSON requests/results | Duplicate planning or backend logic |
| Backend | Execute a validated action against live KiCad IPC or an explicit S-expression fallback | Invent successful results |
| Verifier | Check the resulting design state independently | Trust a tool response without inspecting state |

## Required lifecycle

Every mutating request follows this lifecycle:

```text
user intent
  -> structured task
  -> plan/stage
  -> validated action
  -> permission decision
  -> backend execution
  -> ground-truth observation
  -> independent verification
  -> continue, repair, ask, or finish
```

Read-only inspection may omit planning and permission steps, but it must still
return a structured observation.

## Permission and approval policy

`PermissionPolicy` is the deterministic runtime gate for all action paths,
including controller actions and primitive MCP tools. Inspection and ordinary
design construction remain allowed by default. Destructive actions (such as
deleting symbols or footprints, loading/replacing documents, undoing work, or
saving) and high-risk board operations produce a `PermissionRequest` before
backend execution. The request includes the action, stable request ID, reason,
risk classification, and `ask` decision.

An adapter may resolve the request through an approval callback. The MCP
session exposes the same boundary with `approve_action`, which accepts the
request ID and either `allow` or `deny`. Unresolved requests return
`status: "approval_required"` and are never executed.

## JSON boundary

The shared contract types are in `kicad_agent.core.contracts`:

- `AgentSession`: resumable runtime envelope.
- `Observation`: ground-truth state or event after an action.
- `RepairAttempt`: bounded recovery record.
- `PermissionRequest`: approval boundary for risky actions.
- `AgentMode` and `SessionStatus`: finite lifecycle values.

Existing `Task`, `Plan`, `Action`, `ActionResult`, and `VerificationResult`
remain the domain objects embedded in the session envelope. Every contract
must serialize to JSON-compatible primitives through `to_dict()`.

Verification results expose an explicit `outcome`: `passed`, `failed`, or
`not_verifiable`. A successful backend response is not sufficient evidence for
a mutating action; the verifier must receive a post-action observation. Repair
is bounded by the controller/engine retry budget and reports `repaired`,
`not_repairable`, or `exhausted` rather than retrying indefinitely.

## Backend truthfulness

Results must identify the backend that executed the action. Live IPC and
S-expression fallback are different execution modes and must not be presented
as equivalent. A fallback result must explicitly indicate that fallback was
used and whether the live document was updated. Fallback is opt-in: selecting
`ipc` or `auto` does not silently switch to file editing. Select
`ipc-fallback` (or pass a fallback backend directly) when that behavior is
intended. If the fallback rejects an operation, the result remains failed and
must preserve both the IPC error and the fallback error.
