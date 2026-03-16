const API = "";

// Config is now passed directly to marked.parse
let currentSessionId = null;

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chat-form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat");
const sessionListEl = document.getElementById("session-list");

async function loadSessions() {
    const res = await fetch(`${API}/api/sessions`);
    const sessions = await res.json();
    sessionListEl.innerHTML = "";
    for (const s of sessions) {
        const div = document.createElement("div");
        div.className = "session-item" + (s.id === currentSessionId ? " active" : "");
        const title = document.createElement("span");
        title.textContent = s.title || "New Chat";
        title.style.overflow = "hidden";
        title.style.textOverflow = "ellipsis";
        title.style.whiteSpace = "nowrap";
        title.style.flex = "1";
        div.appendChild(title);
        const del = document.createElement("button");
        del.className = "delete-btn";
        del.textContent = "\u00d7";
        del.onclick = async (e) => {
            e.stopPropagation();
            await fetch(`${API}/api/sessions/${s.id}`, { method: "DELETE" });
            if (currentSessionId === s.id) {
                currentSessionId = null;
                messagesEl.innerHTML = "";
            }
            loadSessions();
        };
        div.appendChild(del);
        div.onclick = () => loadSession(s.id);
        sessionListEl.appendChild(div);
    }
}

async function loadSession(id) {
    currentSessionId = id;
    const res = await fetch(`${API}/api/sessions/${id}/messages`);
    const msgs = await res.json();
    messagesEl.innerHTML = "";
    for (const m of msgs) {
        appendMessage(m.role, m.content);
    }
    loadSessions();
}

function formatInlineSources(text) {
    if (!text) return "";
    return text.replace(/\[([A-Z0-9]+),\s*([^,\]]+),\s*([^\]]+)\]/g, '<span class="inline-source">$1 &middot; $2 &middot; $3</span>');
}

function appendMessage(role, content) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    if (role === "assistant") {
        div.innerHTML = content ? marked.parse(formatInlineSources(content), { breaks: true, gfm: true }) : "";
    } else {
        div.textContent = content;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
}

function appendSources(sources) {
    if (!sources || sources.length === 0) return;
    const last = messagesEl.querySelector(".message.assistant:last-child");
    if (!last) return;
    const div = document.createElement("div");
    div.className = "sources";
    div.innerHTML = "<strong>Sources:</strong> " + sources.map(
        (s) => `<span class="inline-source">${s.ticker} &middot; ${s.filing_type} &middot; ${s.filing_date}</span>`
    ).join("");
    last.appendChild(div);
}

async function sendMessage(question) {
    appendMessage("user", question);
    const assistantEl = appendMessage("assistant", "");
    sendBtn.disabled = true;

    // --- Loading Status Indicator ---
    const statuses = [
        "Understanding your question...",
        "Searching documents...",
        "Ranking relevant sources...",
        "Building context...",
        "Generating answer..."
    ];
    let currentStatusIdx = 0;
    assistantEl.innerHTML = `<div class="status-indicator"><div class="spinner"></div><span class="status-text">${statuses[0]}</span></div>`;
    
    let statusTimer = setInterval(() => {
        if (currentStatusIdx < statuses.length - 1) {
            currentStatusIdx++;
            const textEl = assistantEl.querySelector('.status-text');
            if (textEl) textEl.textContent = statuses[currentStatusIdx];
        }
    }, 2000);
    let isFirstToken = true;

    // Live markdown rendering state
    let rawText = "";
    let renderPending = false;

    function scheduleRender() {
        if (renderPending) return;
        renderPending = true;
        requestAnimationFrame(() => {
            assistantEl.innerHTML = marked.parse(formatInlineSources(rawText), { breaks: true, gfm: true });
            messagesEl.scrollTop = messagesEl.scrollHeight;
            renderPending = false;
        });
    }

    try {
        const res = await fetch(`${API}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question, session_id: currentSessionId }),
        });

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith("data: ")) continue;
                const data = JSON.parse(line.slice(6));
                if (data.token) {
                    if (isFirstToken) {
                        clearInterval(statusTimer);
                        isFirstToken = false;
                    }
                    rawText += data.token;
                    scheduleRender();
                }
                if (data.done) {
                    // Final render to ensure completeness
                    assistantEl.innerHTML = marked.parse(formatInlineSources(rawText), { breaks: true, gfm: true });
                    messagesEl.scrollTop = messagesEl.scrollHeight;
                    currentSessionId = data.session_id;
                    appendSources(data.sources);
                    loadSessions();
                }
            }
        }
    } catch (err) {
        if (typeof statusTimer !== 'undefined') clearInterval(statusTimer);
        assistantEl.textContent = "Error: " + err.message;
    }

    sendBtn.disabled = false;
    input.focus();
}

form.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = input.value.trim();
    if (!q) return;
    input.value = "";
    sendMessage(q);
});

newChatBtn.addEventListener("click", () => {
    currentSessionId = null;
    messagesEl.innerHTML = "";
    input.focus();
});

loadSessions();
