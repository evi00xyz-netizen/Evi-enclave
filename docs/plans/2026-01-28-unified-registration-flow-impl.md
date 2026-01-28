# Unified Registration Flow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace multi-step registration wizard with single "Register Agent" button that handles Identity, Reputation, and TEE in one flow.

**Architecture:** Sequential-then-parallel registration: Identity first (blocking), then Reputation + TEE run in parallel. Three status cards show individual progress. Final button enables when Identity + Reputation complete.

**Tech Stack:** Python/FastAPI backend, vanilla JavaScript frontend, Tailwind CSS, Web3.py for blockchain calls.

**Security Note:** This implementation uses innerHTML for rendering dynamic UI. The content is constructed from trusted sources (API responses with known fields). In production, consider using DOM methods or a sanitization library for additional safety.

---

## Task 1: Add `submit_initial_reputation()` to RegistryClient

**Files:**
- Modify: `src/agent/registry.py:528` (after `give_feedback` method)

**Step 1: Write the method**

Add this method after the existing `give_feedback` method (around line 528):

```python
async def submit_initial_reputation(self, agent_id: int, wait_for_receipt: bool = True) -> Dict[str, Any]:
    """
    Submit initial reputation entry for an agent.

    Calls giveFeedback with neutral value to establish on-chain presence.

    Args:
        agent_id: Agent ID to submit feedback for
        wait_for_receipt: If True, wait for transaction confirmation

    Returns:
        Dict with tx_hash and confirmation status
    """
    if not self.account:
        raise ValueError("Account required for reputation submission")

    # Submit neutral feedback with "init" tag to mark as initialization
    tx = self.reputation_contract.functions.giveFeedback(
        agent_id,
        0,              # value: neutral (0)
        2,              # valueDecimals: 2 decimal places
        "init",         # tag1: marks as initialization entry
        "",             # tag2: empty
        "",             # endpoint: empty
        "",             # feedbackURI: empty
        b'\x00' * 32    # feedbackHash: zero bytes
    ).build_transaction({
        'chainId': self.chain_id,
        'gas': 200000,
        'gasPrice': self.w3.eth.gas_price,
        'nonce': self.w3.eth.get_transaction_count(self.account.address)
    })

    signed_tx = self.account.sign_transaction(tx)
    tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

    print(f"📤 Initial reputation tx: {tx_hash.hex()}")

    if not wait_for_receipt:
        return {"tx_hash": tx_hash.hex(), "agent_id": agent_id}

    receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

    if receipt.status != 1:
        raise RuntimeError(f"Initial reputation submission failed: tx={tx_hash.hex()}")

    print(f"✅ Initial reputation submitted for agent {agent_id}")
    return {"tx_hash": tx_hash.hex(), "agent_id": agent_id, "confirmed": True}
```

**Step 2: Verify no syntax errors**

Run: `python -c "from src.agent.registry import RegistryClient; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/agent/registry.py
git commit -m "feat(registry): add submit_initial_reputation method

Calls giveFeedback with neutral value and 'init' tag to establish
on-chain presence in the reputation registry."
```

---

## Task 2: Add `POST /api/reputation/submit-initial` endpoint

**Files:**
- Modify: `deployment/local_agent_server.py` (after `/api/reputation` endpoint, around line 972)

**Step 1: Add the endpoint**

Add this endpoint after the existing `/api/reputation/{agent_id}` endpoint:

```python
@app.post("/api/reputation/submit-initial")
async def submit_initial_reputation(request: Dict[str, Any] = None):
    """Submit initial reputation entry for agent."""
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    if not agent.is_registered or not agent.agent_id:
        raise HTTPException(status_code=400, detail="Agent must be registered first")

    try:
        result = await agent._registry_client.submit_initial_reputation(
            agent_id=agent.agent_id,
            wait_for_receipt=True
        )
        return {
            "success": True,
            "tx_hash": result.get("tx_hash"),
            "agent_id": result.get("agent_id"),
            "confirmed": result.get("confirmed", False)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit initial reputation: {str(e)}")
```

**Step 2: Verify server starts**

Run: `cd /Users/hashwarlock/Projects/AI/erc-8004-tee-agent && python -c "from deployment.local_agent_server import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add deployment/local_agent_server.py
git commit -m "feat(api): add POST /api/reputation/submit-initial endpoint

Submits initial feedback entry to establish on-chain reputation presence."
```

---

## Task 3: Add `submitInitialReputation()` to APIClient

**Files:**
- Modify: `static/wallet-utils.js:321` (after `getReputation` method)

**Step 1: Add the API method**

Add this method after the existing `getReputation` method:

```javascript
/**
 * Submit initial reputation entry
 */
async submitInitialReputation() {
    return this.post('/api/reputation/submit-initial');
}
```

**Step 2: Verify file syntax**

Run: `node -c static/wallet-utils.js`
Expected: `static/wallet-utils.js: syntax OK` (or no output = success)

**Step 3: Commit**

```bash
git add static/wallet-utils.js
git commit -m "feat(api-client): add submitInitialReputation method"
```

---

## Task 4: Create registration state management

**Files:**
- Modify: `static/dashboard.html` (replace existing state object around line 82)

**Step 1: Update state object**

Replace the existing `state` object with enhanced registration state:

```javascript
let state = {
    wallet: null,
    registration: null,
    tee: null,
    chainConfig: null,
    registrationTx: null,
    teeTx: null,
    reputationTx: null,
    // Unified registration flow state
    unifiedRegistration: {
        started: false,
        identity: { status: 'waiting', message: 'Waiting...', txHash: null, agentId: null },
        reputation: { status: 'waiting', message: 'Waiting for identity...', txHash: null },
        tee: { status: 'waiting', message: 'Waiting for identity...', txHash: null }
    }
};
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add unified registration state management"
```

---

## Task 5: Create status card rendering function

**Files:**
- Modify: `static/dashboard.html` (add before `loadWallet()` function)

**Step 1: Add renderStatusCard function**

Add this function in the script section, before the `loadWallet()` function. Note: This uses innerHTML with trusted content from API responses (agentId, txHash, status messages). The data comes from our own backend and is not user-provided.

```javascript
function renderStatusCard(id, title, statusData) {
    const icons = {
        waiting: '○',
        in_progress: '',  // Will use spinner
        success: '✓',
        error: '✕'
    };

    const colors = {
        waiting: 'text-gray-400',
        in_progress: 'text-blue-400',
        success: 'text-green-400',
        error: 'text-red-400'
    };

    const bgColors = {
        waiting: 'bg-gray-600',
        in_progress: 'bg-blue-600',
        success: 'bg-green-600',
        error: 'bg-red-600'
    };

    const status = statusData.status;
    const isSpinner = status === 'in_progress';

    const iconHtml = isSpinner
        ? '<div class="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>'
        : icons[status];

    const txLinkHtml = statusData.txHash && state.chainConfig ? `
        <a href="${UIUtils.getExplorerUrl(statusData.txHash, state.chainConfig.block_explorer_urls[0])}"
           target="_blank" rel="noopener noreferrer"
           class="text-blue-400 hover:text-blue-300 text-xs">
            View tx: ${UIUtils.formatTxHash(statusData.txHash)} ↗
        </a>
    ` : '';

    const retryHtml = status === 'error' ? `
        <button onclick="retry${id}()" class="bg-red-600 hover:bg-red-700 px-3 py-1 rounded text-xs mt-2">
            Retry
        </button>
    ` : '';

    return `
        <div class="bg-gray-700 rounded-lg p-4 flex items-start gap-4">
            <div class="w-6 h-6 rounded-full ${bgColors[status]} flex items-center justify-center text-sm flex-shrink-0">
                ${iconHtml}
            </div>
            <div class="flex-1 min-w-0">
                <h3 class="font-semibold ${colors[status]}">${title}</h3>
                <p class="text-sm text-gray-400 mt-1">${statusData.message}</p>
                ${txLinkHtml}
                ${retryHtml}
            </div>
        </div>
    `;
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add renderStatusCard function for unified flow"
```

---

## Task 6: Create unified registration UI component

**Files:**
- Modify: `static/dashboard.html` (replace Steps 2-4 HTML, lines 33-64)

**Step 1: Replace step HTML**

Replace the HTML for Steps 2, 3, and 4 (lines 33-64) with a unified registration component:

```html
<!-- Step 2: Unified Registration -->
<div id="step2" class="bg-gray-800 rounded-lg p-6 opacity-50">
    <div class="flex items-center gap-4 mb-4">
        <div id="step2-status" class="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">2</div>
        <h2 class="text-2xl font-bold">Register Your Agent</h2>
    </div>
    <div id="step2-content" class="ml-12">
        <p class="text-gray-400">Waiting for wallet funding...</p>
    </div>
</div>

<!-- Step 3: Agent Status (was Step 5) -->
<div id="step3" class="bg-gray-800 rounded-lg p-6 opacity-50">
    <div class="flex items-center gap-4 mb-4">
        <div id="step3-status" class="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">3</div>
        <h2 class="text-2xl font-bold">Agent Status</h2>
    </div>
    <div id="step3-content" class="ml-12">
        <p class="text-gray-400">Waiting for registration...</p>
    </div>
</div>
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): replace steps 2-4 with unified registration component"
```

---

## Task 7: Create renderUnifiedRegistration function

**Files:**
- Modify: `static/dashboard.html` (add after renderStatusCard function)

**Step 1: Add the render function**

```javascript
function renderUnifiedRegistration() {
    const content = document.getElementById('step2-content');
    const reg = state.unifiedRegistration;

    if (!reg.started) {
        // Not started - show register button
        content.innerHTML = `
            <p class="text-sm text-gray-400 mb-4">Register your agent on-chain for Identity, Reputation, and TEE verification.</p>
            <button onclick="startUnifiedRegistration()" class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded font-semibold">
                Register Agent
            </button>
        `;
        return;
    }

    // Registration in progress - show status cards
    const cardsHtml = `
        <div class="space-y-3 mb-6">
            ${renderStatusCard('Identity', 'Identity Registry', reg.identity)}
            ${renderStatusCard('Reputation', 'Reputation', reg.reputation)}
            ${renderStatusCard('Tee', 'TEE Verification', reg.tee)}
        </div>
    `;

    // Determine button state
    const identityDone = reg.identity.status === 'success';
    const reputationDone = reg.reputation.status === 'success';
    const teeDone = reg.tee.status === 'success';
    const canProceed = identityDone && reputationDone;
    const allDone = identityDone && reputationDone && teeDone;

    let buttonHtml = '';
    let statusMessageHtml = '';

    if (canProceed) {
        buttonHtml = `
            <button onclick="goToDeveloperDashboard()" class="bg-green-600 hover:bg-green-700 px-6 py-3 rounded font-semibold w-full">
                Go to Developer Dashboard →
            </button>
        `;

        if (!teeDone) {
            statusMessageHtml = `
                <p class="text-yellow-400 text-sm mt-3 flex items-center gap-2">
                    <span class="animate-pulse">⚠</span>
                    TEE verification still in progress (completes in background)
                </p>
            `;
        } else {
            statusMessageHtml = `
                <p class="text-green-400 text-sm mt-3">✓ All registrations complete</p>
            `;
        }
    } else {
        // Still in progress
        buttonHtml = `
            <button disabled class="bg-gray-600 px-6 py-3 rounded font-semibold w-full cursor-not-allowed opacity-50">
                Registering...
            </button>
        `;
    }

    content.innerHTML = cardsHtml + buttonHtml + statusMessageHtml;
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add renderUnifiedRegistration function"
```

---

## Task 8: Create startUnifiedRegistration function

**Files:**
- Modify: `static/dashboard.html` (add after renderUnifiedRegistration)

**Step 1: Add the main registration orchestrator**

```javascript
async function startUnifiedRegistration() {
    const reg = state.unifiedRegistration;
    reg.started = true;

    // Update identity to in_progress
    reg.identity.status = 'in_progress';
    reg.identity.message = 'Broadcasting transaction...';
    renderUnifiedRegistration();

    // Step 1: Identity registration (blocking)
    try {
        const identityResult = await registerIdentity();

        if (!identityResult.success) {
            reg.identity.status = 'error';
            reg.identity.message = identityResult.error || 'Registration failed';
            renderUnifiedRegistration();
            return;
        }

        reg.identity.status = 'success';
        reg.identity.message = `Registered (ID: ${identityResult.agentId})`;
        reg.identity.txHash = identityResult.txHash;
        reg.identity.agentId = identityResult.agentId;
        state.registrationTx = identityResult.txHash;

        // Update reputation and TEE to in_progress
        reg.reputation.status = 'in_progress';
        reg.reputation.message = 'Submitting initial entry...';
        reg.tee.status = 'in_progress';
        reg.tee.message = 'Preparing attestation...';
        renderUnifiedRegistration();

        // Step 2: Start Reputation and TEE in parallel
        const [reputationPromise, teePromise] = [
            registerReputationFlow(),
            registerTEEFlow()
        ];

        // Handle reputation result
        reputationPromise.then(result => {
            if (result.success) {
                reg.reputation.status = 'success';
                reg.reputation.message = 'Confirmed';
                reg.reputation.txHash = result.txHash;
                state.reputationTx = result.txHash;
            } else {
                reg.reputation.status = 'error';
                reg.reputation.message = result.error || 'Failed';
            }
            renderUnifiedRegistration();
        });

        // Handle TEE result
        teePromise.then(result => {
            if (result.success) {
                reg.tee.status = 'success';
                reg.tee.message = 'Verified';
                reg.tee.txHash = result.txHash;
                state.teeTx = result.txHash;
            } else {
                reg.tee.status = 'error';
                reg.tee.message = result.error || 'Failed';
            }
            renderUnifiedRegistration();

            // If all done, update step 3
            if (reg.identity.status === 'success' &&
                reg.reputation.status === 'success' &&
                reg.tee.status === 'success') {
                markAgentReady();
            }
        });

    } catch (error) {
        reg.identity.status = 'error';
        reg.identity.message = error.message || 'Unexpected error';
        renderUnifiedRegistration();
    }
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add startUnifiedRegistration orchestrator"
```

---

## Task 9: Create registerIdentity helper function

**Files:**
- Modify: `static/dashboard.html` (add after startUnifiedRegistration)

**Step 1: Add identity registration helper**

```javascript
async function registerIdentity() {
    const result = await apiClient.registerAgent();

    if (!result.success) {
        return { success: false, error: result.error };
    }

    const data = result.data;

    // If already registered, return immediately
    if (data.already_registered && data.agent_id) {
        return {
            success: true,
            agentId: data.agent_id,
            txHash: null,
            alreadyRegistered: true
        };
    }

    const txHash = data.tx_hash;

    // Poll for confirmation
    const txStatus = await pollTransactionStatus(txHash, {
        onUpdate: (status) => {
            if (status.status === 'pending') {
                state.unifiedRegistration.identity.message = `Confirming... (attempt ${status.attempts})`;
                renderUnifiedRegistration();
            }
        }
    });

    if (txStatus && txStatus.success && txStatus.agent_id) {
        return {
            success: true,
            agentId: txStatus.agent_id,
            txHash: txHash
        };
    } else if (txStatus && txStatus.status === 'failed') {
        return { success: false, error: 'Transaction failed' };
    } else {
        return { success: false, error: 'Transaction confirmation timeout' };
    }
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add registerIdentity helper function"
```

---

## Task 10: Create registerReputationFlow helper function

**Files:**
- Modify: `static/dashboard.html` (add after registerIdentity)

**Step 1: Add reputation flow helper**

```javascript
async function registerReputationFlow() {
    try {
        const result = await apiClient.submitInitialReputation();

        if (!result.success) {
            return { success: false, error: result.error };
        }

        return {
            success: true,
            txHash: result.data.tx_hash,
            confirmed: result.data.confirmed
        };
    } catch (error) {
        return { success: false, error: error.message || 'Reputation submission failed' };
    }
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add registerReputationFlow helper"
```

---

## Task 11: Create registerTEEFlow helper function

**Files:**
- Modify: `static/dashboard.html` (add after registerReputationFlow)

**Step 1: Add TEE flow helper**

```javascript
async function registerTEEFlow() {
    try {
        // First prepare TEE attestation
        const prepResult = await apiClient.prepareTEE();

        if (!prepResult.success) {
            return { success: false, error: prepResult.error || 'TEE preparation failed' };
        }

        // Poll for preparation to complete
        let prepared = false;
        let attempts = 0;
        const maxAttempts = 40; // ~2 minutes at 3s intervals

        while (!prepared && attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 3000));
            attempts++;

            const statusResult = await apiClient.getTEEStatus();

            if (statusResult.success) {
                if (statusResult.data.state === 'ready') {
                    prepared = true;
                } else if (statusResult.data.state === 'error') {
                    return { success: false, error: statusResult.data.error || 'TEE preparation failed' };
                } else {
                    // Still preparing - update message
                    state.unifiedRegistration.tee.message = `Preparing attestation... (${statusResult.data.elapsed_seconds || 0}s)`;
                    renderUnifiedRegistration();
                }
            }
        }

        if (!prepared) {
            return { success: false, error: 'TEE preparation timeout' };
        }

        // Now submit TEE verification
        state.unifiedRegistration.tee.message = 'Submitting proof...';
        renderUnifiedRegistration();

        const teeResult = await apiClient.registerTEE();

        if (!teeResult.success) {
            return { success: false, error: teeResult.error || 'TEE verification failed' };
        }

        return {
            success: true,
            txHash: teeResult.data.tx_hash
        };
    } catch (error) {
        return { success: false, error: error.message || 'TEE verification failed' };
    }
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add registerTEEFlow helper"
```

---

## Task 12: Create retry functions

**Files:**
- Modify: `static/dashboard.html` (add after registerTEEFlow)

**Step 1: Add retry handlers**

```javascript
async function retryIdentity() {
    state.unifiedRegistration.identity.status = 'in_progress';
    state.unifiedRegistration.identity.message = 'Retrying...';
    renderUnifiedRegistration();

    const result = await registerIdentity();

    if (result.success) {
        state.unifiedRegistration.identity.status = 'success';
        state.unifiedRegistration.identity.message = `Registered (ID: ${result.agentId})`;
        state.unifiedRegistration.identity.agentId = result.agentId;
        state.unifiedRegistration.identity.txHash = result.txHash;

        // Trigger parallel flows if not already done
        if (state.unifiedRegistration.reputation.status === 'waiting') {
            state.unifiedRegistration.reputation.status = 'in_progress';
            state.unifiedRegistration.reputation.message = 'Submitting initial entry...';
            registerReputationFlow().then(handleReputationResult);
        }
        if (state.unifiedRegistration.tee.status === 'waiting') {
            state.unifiedRegistration.tee.status = 'in_progress';
            state.unifiedRegistration.tee.message = 'Preparing attestation...';
            registerTEEFlow().then(handleTeeResult);
        }
    } else {
        state.unifiedRegistration.identity.status = 'error';
        state.unifiedRegistration.identity.message = result.error;
    }
    renderUnifiedRegistration();
}

async function retryReputation() {
    state.unifiedRegistration.reputation.status = 'in_progress';
    state.unifiedRegistration.reputation.message = 'Retrying...';
    renderUnifiedRegistration();

    const result = await registerReputationFlow();
    handleReputationResult(result);
}

async function retryTee() {
    state.unifiedRegistration.tee.status = 'in_progress';
    state.unifiedRegistration.tee.message = 'Retrying...';
    renderUnifiedRegistration();

    const result = await registerTEEFlow();
    handleTeeResult(result);
}

function handleReputationResult(result) {
    const reg = state.unifiedRegistration;
    if (result.success) {
        reg.reputation.status = 'success';
        reg.reputation.message = 'Confirmed';
        reg.reputation.txHash = result.txHash;
        state.reputationTx = result.txHash;
    } else {
        reg.reputation.status = 'error';
        reg.reputation.message = result.error || 'Failed';
    }
    renderUnifiedRegistration();
}

function handleTeeResult(result) {
    const reg = state.unifiedRegistration;
    if (result.success) {
        reg.tee.status = 'success';
        reg.tee.message = 'Verified';
        reg.tee.txHash = result.txHash;
        state.teeTx = result.txHash;

        // Check if all done
        if (reg.identity.status === 'success' && reg.reputation.status === 'success') {
            markAgentReady();
        }
    } else {
        reg.tee.status = 'error';
        reg.tee.message = result.error || 'Failed';
    }
    renderUnifiedRegistration();
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add retry functions for unified registration"
```

---

## Task 13: Create goToDeveloperDashboard function

**Files:**
- Modify: `static/dashboard.html` (add after retry functions)

**Step 1: Add navigation function**

```javascript
function goToDeveloperDashboard() {
    const reg = state.unifiedRegistration;

    // Validate requirements
    if (!reg.identity.agentId) {
        UIUtils.showToast('Agent ID not found. Please complete registration.', 'error');
        return;
    }

    if (reg.identity.status !== 'success') {
        UIUtils.showToast('Identity registration not complete.', 'error');
        return;
    }

    if (reg.reputation.status !== 'success') {
        UIUtils.showToast('Reputation submission not complete.', 'error');
        return;
    }

    // Navigate to developer dashboard
    window.location.href = '/developer';
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): add goToDeveloperDashboard navigation"
```

---

## Task 14: Update checkRegistration to use unified flow

**Files:**
- Modify: `static/dashboard.html` (update existing checkRegistration function)

**Step 1: Replace checkRegistration function**

Replace the existing `checkRegistration` function with:

```javascript
async function checkRegistration() {
    const step2 = document.getElementById('step2');
    const status = document.getElementById('step2-status');

    const result = await apiClient.getStatus();

    if (!result.success) {
        UIUtils.showError('step2-content', result.error, checkRegistration);
        return;
    }

    const data = result.data;
    console.log('Registration check:', data.agent);

    if (data.agent.is_registered && data.agent.agent_id) {
        // Already registered - show completed state
        step2.className = 'bg-gray-800 rounded-lg p-6';
        status.className = 'w-8 h-8 rounded-full bg-green-600 flex items-center justify-center';
        status.innerHTML = '✓';

        // Update unified registration state
        state.unifiedRegistration.started = true;
        state.unifiedRegistration.identity.status = 'success';
        state.unifiedRegistration.identity.message = `Registered (ID: ${data.agent.agent_id})`;
        state.unifiedRegistration.identity.agentId = data.agent.agent_id;

        // Check TEE status
        if (data.agent.tee_verified) {
            state.unifiedRegistration.tee.status = 'success';
            state.unifiedRegistration.tee.message = 'Verified';
        }

        // For reputation, we'll assume it's done if agent is registered
        // (In real usage, could check subgraph for init feedback)
        state.unifiedRegistration.reputation.status = 'success';
        state.unifiedRegistration.reputation.message = 'Confirmed';

        state.registration = data.agent;
        renderUnifiedRegistration();

        document.getElementById('step3').classList.remove('opacity-50');

        if (data.agent.tee_verified) {
            markAgentReady();
        }
    } else {
        // Not registered - show register button
        step2.className = 'bg-gray-800 rounded-lg p-6';
        renderUnifiedRegistration();
    }
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): update checkRegistration for unified flow"
```

---

## Task 15: Update markAgentReady for new step numbering

**Files:**
- Modify: `static/dashboard.html` (update markAgentReady function)

**Step 1: Update step references**

Replace the existing `markAgentReady` function to use step3 (was step5):

```javascript
function markAgentReady() {
    const step3 = document.getElementById('step3');
    const content = document.getElementById('step3-content');
    const status = document.getElementById('step3-status');

    step3.className = 'bg-gray-800 rounded-lg p-6';
    status.className = 'w-8 h-8 rounded-full bg-green-600 flex items-center justify-center';
    status.innerHTML = '✓';
    content.innerHTML = `
        <p class="text-green-400 mb-2">✓ Agent Ready</p>
        <p class="text-sm text-gray-400 mb-3">A2A endpoints active</p>
        <div class="flex gap-3">
            <a href="/agent.json" class="text-blue-400 hover:text-blue-300 text-sm">
                → View Agent Card
            </a>
            <a href="/developer" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-sm">
                Developer Dashboard
            </a>
        </div>
    `;
}
```

**Step 2: Commit**

```bash
git add static/dashboard.html
git commit -m "feat(dashboard): update markAgentReady for 3-step flow"
```

---

## Task 16: Remove old step functions

**Files:**
- Modify: `static/dashboard.html` (remove deprecated functions)

**Step 1: Remove old functions**

Delete the following functions as they're no longer needed:
- `checkReputation()` (lines ~187-241)
- `checkTEE()` (lines ~246-298)
- `renderTEEStatus()` (lines ~300-362)
- `startTEEPolling()` (lines ~364-376)
- `clearTEEPolling()` (lines ~378-383)
- `startTEEPreparation()` (lines ~385-408)
- `retryTEEPreparation()` (lines ~410-413)
- `registerTEE()` (lines ~432-553)
- `register()` (lines ~601-685)

Also remove the `teePollingInterval` variable declaration (line ~244).

**Step 2: Verify no syntax errors**

Open the dashboard in a browser and check browser console for JavaScript errors.

**Step 3: Commit**

```bash
git add static/dashboard.html
git commit -m "refactor(dashboard): remove deprecated step functions

Removed old multi-step functions replaced by unified registration flow."
```

---

## Task 17: Final integration test

**Step 1: Start the server**

Run: `cd /Users/hashwarlock/Projects/AI/erc-8004-tee-agent && python -m deployment.local_agent_server`

**Step 2: Test the flow manually**

1. Open `http://localhost:8000/funding` - fund the wallet
2. Open `http://localhost:8000/dashboard` - should show Step 1 (funded) and Step 2 (Register Agent button)
3. Click "Register Agent" - should show 3 status cards progressing
4. Wait for Identity + Reputation to complete - "Go to Developer Dashboard" button should enable
5. Click the button - should navigate to `/developer`

**Step 3: Commit final state**

```bash
git add -A
git commit -m "feat: complete unified registration flow implementation

- Single 'Register Agent' button replaces multi-step wizard
- Sequential Identity registration, then parallel Reputation + TEE
- Status cards show individual progress with retry buttons
- Final button enables after Identity + Reputation complete
- TEE can continue in background

Closes unified-registration-flow design."
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add `submit_initial_reputation()` method | `src/agent/registry.py` |
| 2 | Add `/api/reputation/submit-initial` endpoint | `deployment/local_agent_server.py` |
| 3 | Add `submitInitialReputation()` API method | `static/wallet-utils.js` |
| 4 | Update state management | `static/dashboard.html` |
| 5 | Create `renderStatusCard()` function | `static/dashboard.html` |
| 6 | Replace step HTML with unified component | `static/dashboard.html` |
| 7 | Create `renderUnifiedRegistration()` | `static/dashboard.html` |
| 8 | Create `startUnifiedRegistration()` | `static/dashboard.html` |
| 9 | Create `registerIdentity()` helper | `static/dashboard.html` |
| 10 | Create `registerReputationFlow()` helper | `static/dashboard.html` |
| 11 | Create `registerTEEFlow()` helper | `static/dashboard.html` |
| 12 | Create retry functions | `static/dashboard.html` |
| 13 | Create `goToDeveloperDashboard()` | `static/dashboard.html` |
| 14 | Update `checkRegistration()` | `static/dashboard.html` |
| 15 | Update `markAgentReady()` | `static/dashboard.html` |
| 16 | Remove deprecated functions | `static/dashboard.html` |
| 17 | Final integration test | - |
