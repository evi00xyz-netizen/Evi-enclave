# Frontend Reputation & TEE Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reputation display as Step 3 and optimize TEE verification with background pre-preparation.

**Architecture:** Backend adds TEE preparation state and endpoints. Frontend adds reputation step, renumbers existing steps, and polls TEE status for optimized flow.

**Tech Stack:** Python/FastAPI (backend), Vanilla JS/HTML (frontend), TailwindCSS (styling)

**Security Note:** This implementation uses innerHTML for dynamic content. The content is constructed from trusted API responses and does not include user-generated input. All dynamic values are from the backend API which sanitizes data.

---

## Phase 1: Backend - TEE Preparation System

### Task 1: Add TEE Preparation Global State

**Files:**
- Modify: `deployment/local_agent_server.py:55-80` (after global variables section)

**Step 1: Add global state and helper**

Add after the existing global variables (around line 55):

```python
# TEE Preparation State
tee_preparation = {
    "state": "idle",      # idle | preparing | ready | error
    "started_at": None,
    "proof_data": None,   # Cached: {tee_arch, code_measurement, code_config_uri, proof}
    "error": None,
    "expires_at": None    # Cache expiry time
}

TEE_CACHE_DURATION = 300  # 5 minutes
```

**Step 2: Verify syntax**

Run: `python3 -m py_compile deployment/local_agent_server.py`
Expected: No output (success)

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: add TEE preparation global state"
```

---

### Task 2: Implement Background TEE Preparation Function

**Files:**
- Modify: `deployment/local_agent_server.py` (add after global state, before first endpoint)

**Step 1: Add the background preparation function**

Add this function after the global state (see design doc for full implementation).

Key components:
- Check if already preparing/ready
- Get TEE attestation from tee_auth
- Parse agent domain for app_id and dstack_domain
- Call offchain proof endpoint with 60s timeout
- Cache proof_data on success
- Set error state on failure

**Step 2: Verify syntax**

Run: `python3 -m py_compile deployment/local_agent_server.py`

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: add background TEE preparation function"
```

---

### Task 3: Implement POST /api/tee/prepare Endpoint

**Files:**
- Modify: `deployment/local_agent_server.py` (add before existing `/api/tee/register`)

**Step 1: Add the prepare endpoint**

Endpoint behavior:
- Return current state if already ready/preparing
- Start background preparation task
- Return preparing state

**Step 2: Verify syntax**

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: add POST /api/tee/prepare endpoint"
```

---

### Task 4: Implement GET /api/tee/status Endpoint

**Files:**
- Modify: `deployment/local_agent_server.py` (add after `/api/tee/prepare`)

**Step 1: Add the status endpoint**

Returns:
- state: idle | preparing | ready | error
- elapsed_seconds (if preparing)
- expires_in (if ready)
- error (if error)

**Step 2: Verify syntax**

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: add GET /api/tee/status endpoint"
```

---

### Task 5: Modify /api/tee/register to Use Cached Proof

**Files:**
- Modify: `deployment/local_agent_server.py:528-625` (the register_tee function)

**Step 1: Update register_tee**

Two paths:
1. **Fast path**: If cached proof ready, use it directly for tx
2. **Slow path**: Fall back to existing full attestation flow

Clear cache after successful registration.

**Step 2: Verify syntax**

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: update /api/tee/register to use cached proof"
```

---

### Task 6: Auto-trigger TEE Preparation After Registration

**Files:**
- Modify: `deployment/local_agent_server.py` (the register_agent function)

**Step 1: Add auto-trigger**

For already_registered case: start TEE preparation immediately.
For new registration: add message to call /api/tee/prepare after confirmation.

**Step 2: Verify syntax**

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat: auto-trigger TEE preparation after registration"
```

---

## Phase 2: Frontend - Dashboard Updates

### Task 7: Add API Client Methods for TEE and Reputation

**Files:**
- Modify: `static/wallet-utils.js` (add to APIClient class)

**Step 1: Add new API methods**

```javascript
async getTEEStatus() {
    return this.get('/api/tee/status');
}

async prepareTEE() {
    return this.post('/api/tee/prepare');
}

async getReputation(agentId = null) {
    const endpoint = agentId ? `/api/reputation/${agentId}` : '/api/reputation';
    return this.get(endpoint);
}
```

**Step 2: Commit**

```bash
git add static/wallet-utils.js
git commit -m "feat: add API client methods for TEE status and reputation"
```

---

### Task 8: Add Step 3 Reputation HTML

**Files:**
- Modify: `static/dashboard.html` (add new step between step2 and current step3)

**Step 1: Add the new reputation step HTML**

Add new div with id="step3" for Reputation between Identity Registration and TEE Verification.

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat: add Step 3 reputation HTML structure"
```

---

### Task 9: Renumber Steps 3→4 and 4→5

**Files:**
- Modify: `static/dashboard.html`

**Step 1: Update TEE Verification**
- step3 → step4

**Step 2: Update Agent Ready**
- step4 → step5

**Step 3: Commit**

```bash
git add static/dashboard.html
git commit -m "refactor: renumber steps 3→4 and 4→5"
```

---

### Task 10: Add checkReputation() Function

**Files:**
- Modify: `static/dashboard.html` (in script section)

**Step 1: Add the checkReputation function**

- Fetch from /api/reputation
- Display feedback count and average score
- Show "No feedback yet" for new agents
- Auto-complete and call checkTEE()

**Step 2: Update checkRegistration to call checkReputation**

Change the flow: registration complete → checkReputation() → checkTEE()

**Step 3: Commit**

```bash
git add static/dashboard.html
git commit -m "feat: add checkReputation function and flow"
```

---

### Task 11: Update checkTEE() with Preparation Status

**Files:**
- Modify: `static/dashboard.html` (the checkTEE function)

**Step 1: Replace checkTEE function**

- First check if already verified
- Poll /api/tee/status
- Show different UI based on state:
  - ready: "Submit TEE Verification" button
  - preparing: Progress with elapsed time
  - error: Error message with retry button
  - idle: "Verify TEE" button

**Step 2: Add helper functions**

- startTEEPreparation()
- retryTEEPreparation()

**Step 3: Commit**

```bash
git add static/dashboard.html
git commit -m "feat: update checkTEE with preparation status polling"
```

---

### Task 12: Update registerTEE() with Timeout

**Files:**
- Modify: `static/dashboard.html` (the registerTEE function)

**Step 1: Add timeout handling**

- 60 second timeout
- Show elapsed timer
- Race between API call and timeout
- Show retry button on timeout/error

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat: add timeout and elapsed timer to registerTEE"
```

---

### Task 13: Update markAgentReady() for Step 5

**Files:**
- Modify: `static/dashboard.html`

**Step 1: Update element IDs**

Change step4 → step5 references in markAgentReady function.

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "refactor: update markAgentReady for step5"
```

---

## Phase 3: Testing & Verification

### Task 14: Verify All Python Syntax

Run: `python3 -m py_compile deployment/local_agent_server.py`
Expected: No output (success)

---

### Task 15: Final Commit and Push

**Step 1: Check git status**

Run: `git status`

**Step 2: Push branch**

Run: `git push origin feat/agent0-sdk-migration`

---

## Summary of Changes

### Files Modified

| File | Changes |
|------|---------|
| `deployment/local_agent_server.py` | TEE preparation state, background function, 2 new endpoints |
| `static/dashboard.html` | Step 3 reputation, renumbered steps, updated JS functions |
| `static/wallet-utils.js` | 3 new API client methods |

### New Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/tee/prepare` | Start background TEE attestation |
| `GET /api/tee/status` | Get preparation state |

### New Dashboard Flow

1. Wallet Funding
2. Identity Registration → auto-triggers TEE preparation
3. Reputation Display (NEW) → polls TEE status
4. TEE Verification → uses cached proof if ready
5. Agent Ready
