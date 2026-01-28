/**
 * Chat Interface Client Module
 *
 * Provides chat functionality for the TEE Agent developer page.
 *
 * Security: All user content is sanitized via escapeHtml() before rendering
 * to prevent XSS attacks.
 */

/**
 * Escape HTML to prevent XSS attacks.
 * This MUST be called on any user-provided content before rendering.
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}


class ChatClient {
    constructor(options = {}) {
        this.sessionId = this.getOrCreateSessionId();
        this.isLoading = false;
        this.onMessage = options.onMessage || (() => {});
        this.onError = options.onError || ((err) => console.error(err));
        this.onLoadingChange = options.onLoadingChange || (() => {});
    }

    /**
     * Get or create a session ID from localStorage
     */
    getOrCreateSessionId() {
        const SESSION_KEY = 'tee_agent_session_id';
        let sessionId = localStorage.getItem(SESSION_KEY);
        if (!sessionId) {
            sessionId = crypto.randomUUID();
            localStorage.setItem(SESSION_KEY, sessionId);
        }
        return sessionId;
    }

    /**
     * Clear the current session
     */
    clearSession() {
        const SESSION_KEY = 'tee_agent_session_id';
        localStorage.removeItem(SESSION_KEY);
        this.sessionId = this.getOrCreateSessionId();
    }

    /**
     * Send a chat message
     */
    async sendMessage(message) {
        if (this.isLoading) return null;

        this.isLoading = true;
        this.onLoadingChange(true);

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    message: message
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Chat request failed');
            }

            const data = await response.json();

            // Update session ID if server assigned a new one
            if (data.session_id && data.session_id !== this.sessionId) {
                this.sessionId = data.session_id;
                localStorage.setItem('tee_agent_session_id', data.session_id);
            }

            this.onMessage({
                role: 'assistant',
                content: data.response,
                toolCalls: data.tool_calls
            });

            return data;

        } catch (error) {
            this.onError(error);
            return null;

        } finally {
            this.isLoading = false;
            this.onLoadingChange(false);
        }
    }

    /**
     * Execute a quick action (tool call without LLM)
     */
    async quickAction(tool, args = {}) {
        if (this.isLoading) return null;

        this.isLoading = true;
        this.onLoadingChange(true);

        try {
            const response = await fetch('/api/quick-action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    tool: tool,
                    arguments: args
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Quick action failed');
            }

            const data = await response.json();

            // Update session ID if needed
            if (data.session_id) {
                this.sessionId = data.session_id;
                localStorage.setItem('tee_agent_session_id', data.session_id);
            }

            this.onMessage({
                role: 'assistant',
                content: data.response,
                toolCalls: data.tool_calls
            });

            return data;

        } catch (error) {
            this.onError(error);
            return null;

        } finally {
            this.isLoading = false;
            this.onLoadingChange(false);
        }
    }

    /**
     * Get session history
     */
    async getHistory() {
        try {
            const response = await fetch('/api/session/' + this.sessionId + '/history');

            if (!response.ok) {
                if (response.status === 404) {
                    return { messages: [] };
                }
                throw new Error('Failed to get history');
            }

            return await response.json();

        } catch (error) {
            console.error('Failed to get history:', error);
            return { messages: [] };
        }
    }

    /**
     * Create a new session
     */
    async newSession() {
        try {
            const response = await fetch('/api/session/new', {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to create session');
            }

            const data = await response.json();
            this.sessionId = data.session_id;
            localStorage.setItem('tee_agent_session_id', data.session_id);

            return data;

        } catch (error) {
            this.onError(error);
            return null;
        }
    }
}


/**
 * Chat UI Manager
 *
 * Handles rendering and interaction for the chat interface.
 */
class ChatUI {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.messagesContainer = null;
        this.inputElement = null;
        this.sendButton = null;
        this.messages = [];

        this.client = new ChatClient({
            onMessage: (msg) => this.addMessage(msg),
            onError: (err) => this.showError(err.message),
            onLoadingChange: (loading) => this.setLoading(loading)
        });

        this.render();
        this.loadHistory();
    }

    /**
     * Render the chat interface using safe DOM methods
     */
    render() {
        // Clear container safely
        while (this.container.firstChild) {
            this.container.removeChild(this.container.firstChild);
        }

        // Create chat container
        const chatContainer = document.createElement('div');
        chatContainer.className = 'chat-container';

        // Quick actions
        const quickActions = document.createElement('div');
        quickActions.className = 'quick-actions';

        const quickActionButtons = [
            { tool: 'get_wallet_info', icon: '\uD83D\uDCB0', label: 'Wallet Info' },
            { tool: 'get_agent_card', icon: '\uD83D\uDCCB', label: 'Agent Card' },
            { tool: 'generate_attestation', icon: '\uD83D\uDD10', label: 'Attestation' },
            { tool: 'get_registration_status', icon: '\uD83D\uDCDD', label: 'Registration' },
            { tool: 'get_reputation', icon: '\u2B50', label: 'Reputation' }
        ];

        quickActionButtons.forEach(btn => {
            const button = document.createElement('button');
            button.className = 'quick-action-btn';
            button.dataset.tool = btn.tool;
            button.textContent = btn.icon + ' ' + btn.label;
            button.addEventListener('click', () => this.quickAction(btn.tool));
            quickActions.appendChild(button);
        });

        // Messages area
        const messagesArea = document.createElement('div');
        messagesArea.className = 'chat-messages';
        messagesArea.id = 'chatMessages';

        // Input area
        const inputArea = document.createElement('div');
        inputArea.className = 'chat-input-area';

        const textarea = document.createElement('textarea');
        textarea.className = 'chat-input';
        textarea.id = 'chatInput';
        textarea.placeholder = 'Type your message...';
        textarea.rows = 1;

        const sendBtn = document.createElement('button');
        sendBtn.className = 'chat-send-btn';
        sendBtn.id = 'chatSendBtn';
        sendBtn.textContent = 'Send';

        inputArea.appendChild(textarea);
        inputArea.appendChild(sendBtn);

        chatContainer.appendChild(quickActions);
        chatContainer.appendChild(messagesArea);
        chatContainer.appendChild(inputArea);

        this.container.appendChild(chatContainer);

        this.messagesContainer = messagesArea;
        this.inputElement = textarea;
        this.sendButton = sendBtn;

        // Auto-resize textarea
        this.inputElement.addEventListener('input', () => {
            this.inputElement.style.height = 'auto';
            this.inputElement.style.height = Math.min(this.inputElement.scrollHeight, 150) + 'px';
        });

        // Enter to send (Shift+Enter for newline)
        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Send button click
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Show initial greeting (static content, safe)
        this.addMessage({
            role: 'assistant',
            content: 'Hello! I\'m your TEE agent assistant running in a secure enclave.\n\nI can help you:\n- Check wallet balance and sign messages\n- Generate attestation proofs\n- Query registration and reputation status\n- Run Python or shell scripts\n- Explore agent capabilities\n\nWhat would you like to do?'
        });
    }

    /**
     * Load chat history from server
     */
    async loadHistory() {
        const history = await this.client.getHistory();
        if (history.messages && history.messages.length > 0) {
            // Clear default greeting if we have history
            while (this.messagesContainer.firstChild) {
                this.messagesContainer.removeChild(this.messagesContainer.firstChild);
            }
            this.messages = [];

            history.messages.forEach(msg => {
                this.addMessage({
                    role: msg.role,
                    content: msg.content,
                    toolCalls: msg.tool_calls
                });
            });
        }
    }

    /**
     * Add a message to the chat using safe DOM methods
     */
    addMessage(message) {
        this.messages.push(message);

        const messageEl = document.createElement('div');
        messageEl.className = 'message ' + message.role;

        const avatar = message.role === 'user' ? '\uD83D\uDC64' : '\uD83E\uDD16';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.textContent = avatar;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        // Format and sanitize content before rendering
        // formatContent escapes HTML first, then applies markdown
        const formattedContent = this.formatContent(message.content);
        contentDiv.innerHTML = formattedContent;

        // Add tool results if present
        if (message.toolCalls && message.toolCalls.length > 0) {
            message.toolCalls.forEach(tc => {
                const toolResult = this.createToolResultElement(tc);
                contentDiv.appendChild(toolResult);
            });
        }

        messageEl.appendChild(avatarDiv);
        messageEl.appendChild(contentDiv);

        // Remove typing indicator if present
        const typingIndicator = this.messagesContainer.querySelector('.typing');
        if (typingIndicator) {
            typingIndicator.remove();
        }

        this.messagesContainer.appendChild(messageEl);
        this.scrollToBottom();
    }

    /**
     * Format message content (basic markdown with XSS protection)
     * SECURITY: escapeHtml is called FIRST to sanitize all content
     */
    formatContent(content) {
        // First escape HTML to prevent XSS - this is critical
        let html = escapeHtml(content);

        // Code blocks (```...```)
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
            return '<pre><code class="language-' + escapeHtml(lang) + '">' + code.trim() + '</code></pre>';
        });

        // Inline code (`...`)
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold (**...**)
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Bullet points (- ...)
        html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
        html = html.replace(/(<li>.*<\/li>)+/g, '<ul>$&</ul>');

        // Line breaks
        html = html.replace(/\n/g, '<br>');

        return html;
    }

    /**
     * Create a tool result element using safe DOM methods
     */
    createToolResultElement(toolCall) {
        const toolResult = document.createElement('div');
        toolResult.className = 'tool-result';
        toolResult.addEventListener('click', () => toolResult.classList.toggle('collapsed'));

        const toolHeader = document.createElement('div');
        toolHeader.className = 'tool-header';

        const toolNameSpan = document.createElement('span');
        // Sanitize tool name
        const toolName = escapeHtml(
            toolCall.tool.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); })
        );
        toolNameSpan.innerHTML = '\uD83D\uDCCB ' + toolName;

        const toggleSpan = document.createElement('span');
        toggleSpan.className = 'toggle';
        toggleSpan.textContent = '\u25BC';

        toolHeader.appendChild(toolNameSpan);
        toolHeader.appendChild(toggleSpan);

        const toolOutput = document.createElement('pre');
        toolOutput.className = 'tool-output';
        // Sanitize the JSON output
        toolOutput.textContent = JSON.stringify(toolCall.result, null, 2);

        toolResult.appendChild(toolHeader);
        toolResult.appendChild(toolOutput);

        return toolResult;
    }

    /**
     * Send a message
     */
    async sendMessage() {
        const message = this.inputElement.value.trim();
        if (!message) return;

        // Add user message to UI
        this.addMessage({ role: 'user', content: message });

        // Clear input
        this.inputElement.value = '';
        this.inputElement.style.height = 'auto';

        // Show typing indicator
        this.showTyping();

        // Send to server
        await this.client.sendMessage(message);
    }

    /**
     * Execute a quick action
     */
    async quickAction(tool) {
        // Add pseudo user message
        const toolNames = {
            'get_wallet_info': 'Wallet Info',
            'get_agent_card': 'Agent Card',
            'generate_attestation': 'Attestation',
            'get_registration_status': 'Registration Status',
            'get_reputation': 'Reputation'
        };

        this.addMessage({
            role: 'user',
            content: '[Quick Action: ' + (toolNames[tool] || tool) + ']'
        });

        // Show typing indicator
        this.showTyping();

        // Execute
        await this.client.quickAction(tool);
    }

    /**
     * Show typing indicator using safe DOM methods
     */
    showTyping() {
        const typingEl = document.createElement('div');
        typingEl.className = 'message assistant typing';

        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.textContent = '\uD83E\uDD16';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'content';

        const dotsDiv = document.createElement('div');
        dotsDiv.className = 'typing-dots';
        for (let i = 0; i < 3; i++) {
            const span = document.createElement('span');
            dotsDiv.appendChild(span);
        }
        contentDiv.appendChild(dotsDiv);

        typingEl.appendChild(avatarDiv);
        typingEl.appendChild(contentDiv);

        this.messagesContainer.appendChild(typingEl);
        this.scrollToBottom();
    }

    /**
     * Set loading state
     */
    setLoading(loading) {
        this.sendButton.disabled = loading;
        this.inputElement.disabled = loading;

        document.querySelectorAll('.quick-action-btn').forEach(btn => {
            btn.disabled = loading;
        });
    }

    /**
     * Show error message
     */
    showError(message) {
        // Remove typing indicator
        const typingIndicator = this.messagesContainer.querySelector('.typing');
        if (typingIndicator) {
            typingIndicator.remove();
        }

        this.addMessage({
            role: 'assistant',
            content: '\u26A0\uFE0F Error: ' + message + '\n\nPlease try again.'
        });

        if (typeof UIUtils !== 'undefined') {
            UIUtils.showToast(message, 'error');
        }
    }

    /**
     * Scroll to bottom of messages
     */
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    /**
     * Start a new session
     */
    async newSession() {
        await this.client.newSession();
        while (this.messagesContainer.firstChild) {
            this.messagesContainer.removeChild(this.messagesContainer.firstChild);
        }
        this.messages = [];
        this.render();
    }
}

// Export for use
if (typeof window !== 'undefined') {
    window.ChatClient = ChatClient;
    window.ChatUI = ChatUI;
    window.escapeHtml = escapeHtml;
}
