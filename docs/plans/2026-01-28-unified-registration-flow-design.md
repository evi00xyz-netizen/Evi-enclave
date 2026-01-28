# Unified Registration Flow Design

**Date:** 2026-01-28
**Status:** Approved

## Overview

Replace the current multi-step registration wizard (Steps 2-4) with a single "Register Agent" button that handles Identity, Reputation, and TEE registration in one unified flow.

## Current vs New Flow

**Current (5 separate steps):**
```
Funding → Identity Button → Reputation (info) → Prepare TEE → Submit TEE → View Agent
```

**New (consolidated):**
```
Funding → "Register Agent" Button → [Progress Cards] → "Go to Dashboard" Button
```

## Registration Sequence

```
1. Identity Registration (blocking)
   POST /api/register
   └─ Returns: { tx_hash, agent_id } (after polling confirmation)

2. Once Identity confirms, start in parallel:
   ├─ Reputation (initial feedback submission)
   │   POST /api/reputation/submit-initial
   │   └─ Calls giveFeedback(agent_id, 0, 2, "init", "", "", "", 0x00...)
   │
   └─ TEE Verification
       POST /api/tee/prepare
       └─ then POST /api/tee/register
```

## UI Component: Status Cards

Three cards replace Steps 2-4:

```
┌─────────────────────────────────────────────────────────────┐
│  Register Your Agent                                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Identity Registry                      [status]   │   │
│  │   Status message...                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ Reputation                             [status]   │   │
│  │   Status message...                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ TEE Verification                       [status]   │   │
│  │   Status message...                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [ Register Agent ]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Card States

| State | Icon | Color | Description |
|-------|------|-------|-------------|
| `waiting` | ○ | Gray | Waiting for dependency |
| `in_progress` | ◐ (spinner) | Blue | Transaction in progress |
| `success` | ✓ | Green | Completed successfully |
| `error` | ✕ | Red | Failed (with retry option) |

### Status Messages

**Identity Registry:**
- "Waiting..." → "Broadcasting tx..." → "Confirming..." → "Registered (ID: 42)"

**Reputation:**
- "Waiting for identity..." → "Submitting initial entry..." → "Confirmed"

**TEE Verification:**
- "Waiting for identity..." → "Preparing attestation..." → "Submitting proof..." → "Verified"

## Final Button Behavior

### Button States

**During Registration:**
- Disabled, shows "Registering..."

**After Identity + Reputation Complete (TEE still running):**
- Enabled, green "Go to Developer Dashboard →"
- Shows warning: "TEE verification still in progress (completes in background)"

**After All Complete:**
- Enabled, green "Go to Developer Dashboard →"
- Shows: "All registrations complete"

### On Click Validation

1. Verify `agent_id` exists in state
2. Verify Identity status is `success`
3. Verify Reputation status is `success`
4. If valid → Navigate to `/developer`
5. If invalid → Show error toast

## Error Handling

### Per-Card Recovery

Each card can fail and retry independently:

```
┌─────────────────────────────────────────────────────────────┐
│  ✕ Reputation                                [error]       │
│    Transaction failed: insufficient gas                    │
│    [ Retry ]                                               │
└─────────────────────────────────────────────────────────────┘
```

### Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Identity fails | Stop all. Show retry button. Must retry identity first. |
| Reputation fails | TEE continues. Retry button on Reputation card. Final button disabled. |
| TEE fails | Reputation continues. Retry button on TEE card. Final button enables when Identity + Reputation succeed. |

### Transaction Links

Each card shows block explorer link after tx broadcast: "View tx: 0xabc...123 ↗"

## New Backend Endpoint

```python
POST /api/reputation/submit-initial
Request: { agent_id: int }
Response: { tx_hash: string, confirmed: bool }

# Calls:
giveFeedback(
    agentId=agent_id,
    value=0,           # Neutral value
    valueDecimals=2,
    tag1="init",       # Marks as initialization entry
    tag2="",
    endpoint="",
    feedbackURI="",
    feedbackHash=bytes32(0)
)
```

## Files to Modify

| File | Changes |
|------|---------|
| `deployment/local_agent_server.py` | Add `POST /api/reputation/submit-initial` endpoint |
| `src/agent/registry.py` | Add `submit_initial_reputation()` method |
| `static/dashboard.html` | Replace Steps 2-4 with unified registration component |
| `static/wallet-utils.js` | Add `submitInitialReputation()` API client method |

## Timing Expectations

- Identity: ~15-30 seconds (1 blockchain tx)
- Reputation: ~15-30 seconds (1 blockchain tx, parallel with TEE)
- TEE: ~60-120 seconds (attestation + blockchain tx, parallel with Reputation)

Total time: ~60-120 seconds (Identity + max(Reputation, TEE))
