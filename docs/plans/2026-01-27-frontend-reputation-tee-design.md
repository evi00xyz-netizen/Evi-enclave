# Frontend Updates: Reputation Display & TEE Optimization

## Overview

Update the dashboard to add reputation display and optimize TEE verification with background pre-preparation.

## Goals

1. Add reputation display as Step 3 in the onboarding flow
2. Optimize TEE verification by pre-fetching attestation in background
3. Improve UX with timeout handling and retry capabilities

## New Dashboard Flow

```
Step 1: Wallet Funding
   ↓ (when funded)

Step 2: Identity Registration
   ↓ (when registered)
   └──→ Backend: Auto-start TEE preparation (background)

Step 3: Reputation Display (NEW)
   - Fetch /api/reputation
   - Show score or "No reputation yet"
   - Poll /api/tee/status every 3s (silent)
   - Auto-complete, enable Step 4
   ↓

Step 4: TEE Verification (was Step 3)
   ├─ If prepared: "Submit TEE Verification" → fast tx only
   └─ If preparing: "Preparing... (45s)" → wait then submit
   ↓ (when verified)

Step 5: Agent Ready (was Step 4)
```

## Backend Changes

### New Global State

```python
tee_preparation = {
    "state": "idle",      # idle | preparing | ready | error
    "started_at": None,
    "proof_data": None,   # Cached offchain proof
    "error": None
}
```

### New Endpoints

#### POST /api/tee/prepare

Start background attestation and offchain proof fetch.

**Response:**
```json
{
  "state": "preparing",
  "message": "TEE preparation started"
}
```

**Behavior:**
- Starts background task to fetch attestation + offchain proof
- Sets state to `preparing`
- On success: caches proof_data, sets state to `ready`
- On failure: sets state to `error` with message
- Idempotent: if already preparing/ready, returns current status

#### GET /api/tee/status

Return current preparation state.

**Response:**
```json
{
  "state": "ready",
  "elapsed_seconds": 28,
  "error": null,
  "cached_until": "2026-01-27T12:00:00Z"
}
```

**States:**
- `idle` - Not started
- `preparing` - In progress
- `ready` - Proof cached, ready to submit
- `error` - Preparation failed

### Modified Endpoints

#### POST /api/register

Auto-trigger TEE preparation after successful registration:

```python
if result.success:
    asyncio.create_task(prepare_tee_attestation())
```

#### POST /api/tee/register

- If `state == "ready"`: use cached proof, skip slow calls (fast path)
- If `state != "ready"`: fall back to full flow (existing behavior)
- After successful tx: reset state to `idle`

## Frontend Changes

### Step Renumbering

| Old | New | Name |
|-----|-----|------|
| 1 | 1 | Wallet Funding |
| 2 | 2 | Identity Registration |
| 3 | 3 | Reputation Display (NEW) |
| 3 | 4 | TEE Verification |
| 4 | 5 | Agent Ready |

### New Step 3 - Reputation Display

```html
<div id="step3" class="bg-gray-800 rounded-lg p-6 opacity-50">
    <div class="flex items-center gap-4 mb-4">
        <div id="step3-status" class="w-8 h-8 rounded-full bg-gray-600">3</div>
        <h2 class="text-2xl font-bold">Reputation</h2>
    </div>
    <div id="step3-content" class="ml-12">
        <!-- Dynamic content -->
    </div>
</div>
```

**Content States:**

| State | Display |
|-------|---------|
| Loading | Spinner + "Fetching reputation..." |
| No reputation | "✓ No feedback yet" + "Build reputation by completing tasks" |
| Has reputation | "✓ Reputation Active" + score + feedback count |

### Step 4 - TEE with Preparation Status

| Preparation State | Button/Display |
|-------------------|----------------|
| `preparing` | "Preparing TEE attestation... (32s)" - disabled |
| `ready` | "Submit TEE Verification" - enabled |
| `error` | "Preparation failed: {error}" + "Retry" button |
| `idle` | "Verify TEE" - starts full flow |

### New JavaScript Functions

```javascript
// Poll TEE preparation status
async function pollTEEStatus() {
    const result = await apiClient.get('/api/tee/status');
    if (result.success) {
        updateTEEUI(result.data);
    }
}

// Check reputation
async function checkReputation() {
    const result = await apiClient.get('/api/reputation');
    // Display reputation, auto-proceed to Step 4
}

// Retry TEE preparation
async function retryTEEPreparation() {
    await apiClient.post('/api/tee/prepare');
    pollTEEStatus();
}
```

### API Client Additions (wallet-utils.js)

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

## Error Handling

### TEE Preparation Errors

| Error | Handling |
|-------|----------|
| Attestation fetch fails | Set state to `error`, show retry button |
| Offchain proof timeout (30s) | Set state to `error`, message: "Offchain service unavailable" |
| Proof expires (5 min cache) | Reset state to `idle`, re-prepare |
| Agent not registered | Don't start preparation, return error |

### Frontend Timeout (Step 4)

- 60s timeout on "Submit TEE Verification"
- Show elapsed timer: "Submitting... (23s)"
- On timeout: "Transaction timed out" + "Retry" button
- On error: Show message + "Retry" button

### State Recovery

- Page refresh during preparation → Poll `/api/tee/status` to restore UI
- Page refresh after registration → Check `/api/status` for TEE verified
- Cached proof + tx fail → Keep proof cached for retry

### Cache Invalidation

- Proof cached for 5 minutes
- Clear on successful TEE registration
- Clear on agent re-registration

## Implementation Tasks

### Phase 1: Backend

1. Add `tee_preparation` global state
2. Implement `POST /api/tee/prepare` endpoint
3. Implement `GET /api/tee/status` endpoint
4. Modify `POST /api/tee/register` to use cached proof
5. Auto-trigger preparation after registration

### Phase 2: Frontend

6. Add Step 3 HTML for reputation
7. Renumber Steps 3→4, 4→5
8. Add `checkReputation()` function
9. Add TEE status polling during Step 3
10. Update `registerTEE()` with timeout + elapsed timer
11. Add retry UI for TEE failures
12. Add API client methods

### Phase 3: Testing & Polish

13. Test full flow in VibeVM
14. Test error scenarios (timeout, preparation failure)
15. Test page refresh recovery
16. Verify cache expiration works

## Files to Modify

- `deployment/local_agent_server.py` - Backend endpoints
- `static/dashboard.html` - UI updates
- `static/wallet-utils.js` - API client methods
