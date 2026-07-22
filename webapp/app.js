const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const T = {
    greet: "Здравствуйте! Задайте медицинский вопрос — я постараюсь помочь.",
    aiUnavailable: "Чат временно недоступен.",
    errGeneric: "Что-то пошло не так. Попробуйте позже.",
    loadingHistory: "Загрузка…",
    emptyHistory: "Пока нет чатов",
};

const els = {
    loading: document.getElementById("loading"),
    register: document.getElementById("screen-register"),
    app: document.getElementById("app"),
    registerBtn: document.getElementById("register-btn"),
    pageSearch: document.getElementById("page-search"),
    pageHistory: document.getElementById("page-history"),
    pageChatView: document.getElementById("page-chat-view"),
    messages: document.getElementById("messages"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    chatSend: document.getElementById("chat-send"),
    chatReset: document.getElementById("chat-reset"),
    historyBtn: document.getElementById("history-btn"),
    historyBack: document.getElementById("history-back"),
    chatList: document.getElementById("chat-list"),
    chatViewBack: document.getElementById("chat-view-back"),
    chatViewTitle: document.getElementById("chat-view-title"),
    chatViewMessages: document.getElementById("chat-view-messages"),
};

let state = { registered: false, aiEnabled: false, user: null, screen: "loading" };

// ---------- Общее ----------

async function api(path, extra = {}) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData, ...extra }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) throw new Error(data.error || T.errGeneric);
    return data;
}

// ---------- Тема ----------

function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("mi_theme", theme); } catch (e) { /* игнор */ }
    const icon = theme === "dark" ? "☀️" : "🌙";
    document.querySelectorAll(".theme-toggle").forEach((b) => { b.textContent = icon; });
}

function initTheme() {
    let theme;
    try { theme = localStorage.getItem("mi_theme"); } catch (e) { theme = null; }
    if (!theme) theme = tg?.colorScheme === "dark" ? "dark" : "light";
    applyTheme(theme);
}

function toggleTheme() {
    const cur = document.documentElement.getAttribute("data-theme");
    applyTheme(cur === "dark" ? "light" : "dark");
}

// ---------- Экраны и страницы ----------

function showScreen(name) {
    state.screen = name;
    els.loading.hidden = name !== "loading";
    els.register.hidden = name !== "register";
    els.app.hidden = name !== "app";
    tg?.BackButton?.hide();
}

// Страницы внутри приложения: поисковик / список чатов / просмотр чата
function showPage(name) {
    els.pageSearch.hidden = name !== "search";
    els.pageHistory.hidden = name !== "history";
    els.pageChatView.hidden = name !== "chatview";
}

function openApp() {
    showScreen("app");
    showPage("search");
    greetChat();
}

// ---------- Инициализация ----------

async function init() {
    if (tg) { tg.ready(); tg.expand(); }
    initTheme();
    try {
        const me = await api("/api/me");
        state.registered = !!me.registered;
        state.aiEnabled = !!me.ai_enabled;
        state.user = me.user || null;
    } catch (e) { /* дефолт: не зарегистрирован */ }
    if (state.registered) openApp(); else showScreen("register");
}

// ---------- Регистрация: переход на сайт ----------

let pendingReg = false;   // ушли на страницу /link для регистрации

function openSite() {
    pendingReg = true;
    const url = window.location.origin + "/link";
    if (tg?.openLink) tg.openLink(url); else window.open(url, "_blank");
}

// После ухода на страницу регистрации мини-апп больше не нужен: как только он
// уходит в фон (открылся браузер/чат) — закрываем его. Пользователь откроет заново.
function closeAfterSiteVisit() {
    if (!pendingReg) return;
    pendingReg = false;
    tg?.close?.();
}

document.addEventListener("visibilitychange", () => {
    if (document.hidden) closeAfterSiteVisit();
});
window.addEventListener("blur", closeAfterSiteVisit);

// ---------- Чат ----------

// Чипсы-подсказки: показываются последним элементом внутри области сообщений
// (прокручиваются вместе с диалогом); клик подставляет текст в поле ввода.
const SUGGEST_CHIPS = [
    { label: "Клинические рекомендации по…", fill: "Клинические рекомендации по " },
    { label: "Инструкция по применению…", fill: "Инструкция по применению " },
    { label: "Схема применения…", fill: "Схема применения " },
];
let chipsEl = null;

function fillInput(value) {
    els.chatInput.value = value;
    autoGrow();
    els.chatInput.focus();
}

function makeChip(item) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip-suggest";
    b.textContent = item.label;
    b.title = item.label;
    b.addEventListener("click", () => fillInput(item.fill));
    return b;
}

// Чипсы — последний элемент внутри #messages; новые сообщения вставляются перед ними.
function ensureChipsEl() {
    if (!chipsEl) {
        chipsEl = document.createElement("div");
        chipsEl.className = "chips-row";
    }
    if (chipsEl.parentNode !== els.messages) els.messages.appendChild(chipsEl);
}
function setChips(items) {
    ensureChipsEl();
    chipsEl.innerHTML = "";
    items.forEach((it) => chipsEl.appendChild(makeChip(it)));
    chipsEl.hidden = items.length === 0;
}
function showStaticChips() { setChips(SUGGEST_CHIPS); }
// Динамические уточняющие вопросы от нейросети (подставляются целиком в поле).
function showSuggestChips(list) { setChips(list.map((q) => ({ label: q, fill: q }))); }
function hideChips() { setChips([]); }

function greetChat() {
    if (els.messages.querySelector(".bubble")) return;
    // Приветствие с иконкой робота слева
    const row = document.createElement("div");
    row.className = "greet-row";
    const av = document.createElement("img");
    av.className = "greet-avatar";
    av.src = "/robot.png";
    av.alt = "";
    const bubble = document.createElement("div");
    bubble.className = "bubble ai";
    bubble.textContent = state.aiEnabled === false ? T.aiUnavailable : T.greet;
    row.append(av, bubble);
    insertMsg(row);
    showStaticChips();
}

function insertMsg(el) {
    if (chipsEl && chipsEl.parentNode === els.messages) els.messages.insertBefore(el, chipsEl);
    else els.messages.appendChild(el);
    scrollToBottom();
}

function addBubble(kind, text) {
    const el = document.createElement("div");
    el.className = "bubble " + kind;
    el.textContent = text;
    insertMsg(el);
    return el;
}

function addTyping() {
    const el = document.createElement("div");
    el.className = "bubble ai";
    el.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    insertMsg(el);
    return el;
}

// ---------- Кнопки под ответом: копировать / лайк / дизлайк ----------

const ICON_COPY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
const ICON_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>';
const ICON_DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>';

function legacyCopy(text, done) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.focus(); ta.select();
    try { document.execCommand("copy"); done(); } catch (e) { /* игнор */ }
    ta.remove();
}
function copyAnswer(text, btn) {
    const done = () => {
        btn.classList.add("copied");
        tg?.HapticFeedback?.notificationOccurred?.("success");
        setTimeout(() => btn.classList.remove("copied"), 1400);
    };
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(text).then(done).catch(() => legacyCopy(text, done));
    } else {
        legacyCopy(text, done);
    }
}
// Оценка ответа. Отправка в API будет добавлена позже — пока только состояние кнопок.
function vote(btn, other) {
    const wasActive = btn.classList.contains("active");
    other.classList.remove("active");
    btn.classList.toggle("active", !wasActive);
    tg?.HapticFeedback?.impactOccurred?.("light");
}
function addAnswerActions(bubble) {
    if (bubble.nextSibling?.classList?.contains("msg-actions")) return;
    const row = document.createElement("div");
    row.className = "msg-actions";

    const copyBtn = document.createElement("button");
    copyBtn.type = "button"; copyBtn.className = "act-btn act-copy"; copyBtn.title = "Скопировать ответ";
    copyBtn.innerHTML = ICON_COPY;
    copyBtn.addEventListener("click", () => copyAnswer(bubble.innerText.trim(), copyBtn));

    const likeBtn = document.createElement("button");
    likeBtn.type = "button"; likeBtn.className = "act-btn act-vote act-like"; likeBtn.title = "Нравится";
    likeBtn.innerHTML = ICON_UP;

    const dislikeBtn = document.createElement("button");
    dislikeBtn.type = "button"; dislikeBtn.className = "act-btn act-vote act-dislike"; dislikeBtn.title = "Не нравится";
    dislikeBtn.innerHTML = ICON_DOWN;

    likeBtn.addEventListener("click", () => vote(likeBtn, dislikeBtn));
    dislikeBtn.addEventListener("click", () => vote(dislikeBtn, likeBtn));

    row.append(copyBtn, likeBtn, dislikeBtn);
    bubble.parentNode.insertBefore(row, bubble.nextSibling);
    scrollToBottom();
}

function scrollToBottom() { els.messages.scrollTop = els.messages.scrollHeight; }

// ---------- Лёгкий рендер markdown (для потокового ответа) ----------

function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function mdToHtml(md) {
    let s = escapeHtml(md);
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    s = s.replace(/\*\*([^*\n]+)\*\*/g, "<b>$1</b>");
    const lines = s.split("\n");
    let out = "", inList = false;
    const closeList = () => { if (inList) { out += "</ul>"; inList = false; } };
    for (const line of lines) {
        const h = line.match(/^(#{1,6})\s+(.*)$/);
        const li = line.match(/^\s*[-•]\s+(.*)$/);
        if (h) { closeList(); out += '<div class="md-h">' + h[2] + "</div>"; }
        else if (li) { if (!inList) { out += "<ul>"; inList = true; } out += "<li>" + li[1] + "</li>"; }
        else if (line.trim()) { closeList(); out += "<div>" + line + "</div>"; }
        else { closeList(); }
    }
    closeList();
    return out;
}

function setStatus(el, text) {
    el.innerHTML = '<span class="status-line"></span> '
        + '<span class="typing"><span></span><span></span><span></span></span>';
    el.querySelector(".status-line").textContent = text;
}

let sending = false;
async function sendChat() {
    const text = els.chatInput.value.trim();
    if (!text || sending) return;
    sending = true;
    els.chatSend.disabled = true;
    els.chatInput.value = "";
    autoGrow();
    hideChips();             // прячем подсказки на время запроса
    addBubble("user", text);
    const typing = addTyping();

    let bubble = null;       // пузырь ответа (создаётся при первом тексте)
    let pending = "";        // незавершённая строка (копится, пока не придёт \n)
    const lineQueue = [];    // готовые строки, ждущие плавного появления
    let gotText = false;
    let gotSuggestions = false;
    let streamDone = false;
    let animating = false;

    function ensureBubble() {
        if (!bubble) {
            typing.remove();
            bubble = addBubble("ai", "");
            bubble.style.whiteSpace = "normal";
        }
    }

    function finish() {
        sending = false;
        els.chatSend.disabled = false;
        if (bubble) addAnswerActions(bubble);   // кнопки копировать/лайк/дизлайк
        // Если нейросеть не прислала уточняющих вопросов — возвращаем статичные подсказки
        if (!gotSuggestions) showStaticChips();
    }

    // Копим стрим и выделяем завершённые строки (по \n) — как на сайте.
    function enqueue(chunk) {
        pending += chunk;
        let i;
        while ((i = pending.indexOf("\n")) !== -1) {
            const ln = pending.slice(0, i);
            pending = pending.slice(i + 1);
            if (ln.trim()) lineQueue.push(ln);
        }
        pump();
    }

    // Появление ПО СТРОЧНО: строка мягко проявляется (CSS .ai-line), потом
    // следующая. При большой очереди (ответ пришёл пачкой) — быстрее, но всё
    // равно строка за строкой, а не всё разом.
    function pump() {
        if (animating) return;
        if (!lineQueue.length) {
            if (streamDone) finish();
            return;
        }
        animating = true;
        ensureBubble();
        const ln = lineQueue.shift();
        const el = document.createElement("div");
        el.className = "ai-line";
        el.innerHTML = mdToHtml(ln);
        bubble.appendChild(el);
        scrollToBottom();
        const delay = Math.max(80, 300 - lineQueue.length * 24);
        setTimeout(() => { animating = false; pump(); }, delay);
    }

    try {
        const res = await fetch("/api/ai/message/stream", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ initData, message: text }),
        });
        if (!res.ok || !res.body) {
            const d = await res.json().catch(() => ({}));
            throw new Error(d.error || T.errGeneric);
        }
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        for (;;) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let i;
            while ((i = buf.indexOf("\n\n")) !== -1) {
                const evt = buf.slice(0, i).trim();
                buf = buf.slice(i + 2);
                if (!evt.startsWith("data:")) continue;
                let obj;
                try { obj = JSON.parse(evt.slice(5).trim()); } catch (e) { continue; }
                if (obj.kind === "action" && !bubble) {
                    setStatus(typing, obj.value);
                    scrollToBottom();
                } else if (obj.kind === "text") {
                    gotText = true;
                    enqueue(obj.value);
                } else if (obj.kind === "suggestions") {
                    if (Array.isArray(obj.value) && obj.value.length) {
                        gotSuggestions = true;
                        showSuggestChips(obj.value.slice(0, 3));
                    }
                } else if (obj.kind === "error") {
                    if (!bubble) typing.remove();
                    addBubble("error", obj.value);
                }
            }
        }
    } catch (e) {
        typing.remove();
        if (!gotText) addBubble("error", e.message || T.errGeneric);
    } finally {
        streamDone = true;
        if (gotText) {
            if (pending.trim()) lineQueue.push(pending);   // остаток — последняя строка
            pending = "";
            pump();
        } else {
            typing.remove();
            finish();
        }
    }
}

async function resetChat() {
    if (sending) return;
    try { await api("/api/ai/reset"); } catch (e) { /* не критично */ }
    els.messages.innerHTML = "";
    chipsEl = null;
    greetChat();
    tg?.HapticFeedback?.impactOccurred("light");
}

function autoGrow() {
    const box = els.chatInput;
    box.style.height = "auto";
    box.style.height = Math.min(box.scrollHeight, 120) + "px";
}

// ---------- История: список чатов и просмотр переписки ----------
// Загружается ТОЛЬКО по нажатию кнопки истории, не при старте Mini App.

function historyNote(container, text) {
    container.innerHTML = "";
    const e = document.createElement("div");
    e.className = "history-empty";
    e.textContent = text;
    container.appendChild(e);
}

function fmtDate(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return "";
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" })
        + ", " + d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
}

async function openHistory() {
    showPage("history");
    historyNote(els.chatList, T.loadingHistory);
    try {
        const data = await api("/api/history/chats");
        renderChatList(data.chats || []);
    } catch (e) {
        historyNote(els.chatList, e.message || T.errGeneric);
    }
}

function renderChatList(chats) {
    if (!chats.length) { historyNote(els.chatList, T.emptyHistory); return; }
    els.chatList.innerHTML = "";
    chats.forEach((chat) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "chat-item";
        const title = document.createElement("div");
        title.className = "chat-item-title";
        title.textContent = chat.title;
        const date = document.createElement("div");
        date.className = "chat-item-date";
        date.textContent = fmtDate(chat.created_at);
        b.append(title, date);
        b.addEventListener("click", () => openChatView(chat));
        els.chatList.appendChild(b);
    });
}

async function openChatView(chat) {
    showPage("chatview");
    els.chatViewTitle.textContent = chat.title;
    historyNote(els.chatViewMessages, T.loadingHistory);
    try {
        const data = await api("/api/history/messages", { chat_id: chat.id });
        renderChatMessages(data.messages || []);
    } catch (e) {
        historyNote(els.chatViewMessages, e.message || T.errGeneric);
    }
}

function renderChatMessages(messages) {
    els.chatViewMessages.innerHTML = "";
    messages.forEach((m) => {
        const el = document.createElement("div");
        if (m.role === "user") {
            el.className = "bubble user";
            el.textContent = m.content;
        } else {
            el.className = "bubble ai";
            el.style.whiteSpace = "normal";
            el.innerHTML = mdToHtml(m.content);
        }
        els.chatViewMessages.appendChild(el);
    });
    els.chatViewMessages.scrollTop = 0;
}

// ---------- События ----------

els.registerBtn.addEventListener("click", openSite);

els.chatForm.addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
els.chatReset.addEventListener("click", resetChat);

els.historyBtn.addEventListener("click", openHistory);
els.historyBack.addEventListener("click", () => showPage("search"));
els.chatViewBack.addEventListener("click", () => showPage("history"));

els.chatInput.addEventListener("input", autoGrow);
els.chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
document.querySelectorAll(".theme-toggle").forEach((b) => b.addEventListener("click", toggleTheme));

init();
