(function () {
    const config = document.getElementById('inbox-config');
    if (!config) return;

    const CONVERSATION_ID = parseInt(config.dataset.conversationId);
    const CURRENT_USER = config.dataset.currentUser;

    const thread = document.getElementById('message-thread');
    const composeInput = document.getElementById('compose-input');

    // Scroll to bottom on load
    if (thread) thread.scrollTop = thread.scrollHeight;

    // Auto-resize textarea
    if (composeInput) {
        composeInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });

        // Send on Enter, newline on Shift+Enter
        composeInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                document.getElementById('compose-form').submit();
            }
        });
    }

    // WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/inbox/`);

    socket.onmessage = function (e) {
        const data = JSON.parse(e.data);

        if (data.event === 'new_message' && data.conversation_id === CONVERSATION_ID) {
            appendMessage(data);
        }
    };

    socket.onclose = function () {
        console.log('Inbox WS closed');
    };

    function appendMessage(data) {
        if (!thread) return;

        const isMine = data.sender === CURRENT_USER;
        const row = document.createElement('div');
        row.className = `message-row ${isMine ? 'mine' : 'theirs'}`;
        row.innerHTML = `
            <div class="message-bubble">${escapeHtml(data.body)}</div>
            <div class="message-meta">${data.created_at}</div>
        `;
        thread.appendChild(row);
        thread.scrollTop = thread.scrollHeight;
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
})();
