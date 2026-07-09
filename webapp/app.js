const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const els = {
    loading: document.getElementById("loading"),
    register: document.getElementById("screen-register"),
    chat: document.getElementById("screen-chat"),
    regForm: document.getElementById("reg-form"),
    regError: document.getElementById("reg-error"),
    regSubmit: document.getElementById("reg-submit"),
    fullName: document.getElementById("full_name"),
    phone: document.getElementById("phone"),
    email: document.getElementById("email"),
    birthDate: document.getElementById("birth_date"),
    messages: document.getElementById("messages"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    chatSend: document.getElementById("chat-send"),
    chatReset: document.getElementById("chat-reset"),
};

// ---------- Общее ----------

async function api(path, extra = {}) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData, ...extra }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
        throw new Error(data.error || "Что-то пошло не так. Попробуйте позже.");
    }
    return data;
}

function showScreen(name) {
    els.loading.hidden = name !== "loading";
    els.register.hidden = name !== "register";
    els.chat.hidden = name !== "chat";
    // Кнопку Telegram не используем — у формы своя кнопка «Зарегистрироваться»
    tg?.MainButton?.hide();
}

// ---------- Инициализация ----------

async function init() {
    if (tg) { tg.ready(); tg.expand(); }
    try {
        const me = await api("/api/me");
        showScreen(me.registered ? "chat" : "register");
        if (me.registered) greet(me.ai_enabled);
    } catch (e) {
        // Если проверка не прошла — показываем регистрацию как безопасный дефолт
        showScreen("register");
    }
    prefillName();
}

function prefillName() {
    const u = tg?.initDataUnsafe?.user;
    if (u) {
        const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
        if (name && !els.fullName.value) els.fullName.value = name;
    }
    updateRegButton();
}

// Кнопка активна (синяя), только когда все поля заполнены и email корректен
function regValid() {
    const email = els.email.value.trim();
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
    return Boolean(
        els.fullName.value.trim() &&
        els.phone.value.trim() &&
        email && emailOk &&
        els.birthDate.value
    );
}

function updateRegButton() {
    els.regSubmit.disabled = !regValid();
}

// ---------- Регистрация ----------

async function submitRegistration() {
    els.regError.hidden = true;

    if (!regValid()) return;

    const payload = {
        full_name: els.fullName.value.trim(),
        phone: els.phone.value.trim(),
        email: els.email.value.trim(),
        birth_date: els.birthDate.value,
    };

    els.regSubmit.disabled = true;
    els.regSubmit.textContent = "Отправка…";
    try {
        await api("/api/register", payload);
        tg?.HapticFeedback?.notificationOccurred("success");
        showScreen("chat");
        greet(true);
    } catch (e) {
        showRegError(e.message);
    } finally {
        els.regSubmit.textContent = "Зарегистрироваться";
        updateRegButton();
    }
}

function showRegError(msg) {
    els.regError.textContent = msg;
    els.regError.hidden = false;
}

// ---------- Чат ----------

function greet(aiEnabled) {
    if (els.messages.childElementCount > 0) return;
    if (aiEnabled === false) {
        addBubble("error", "Чат с нейросетью временно недоступен.");
        return;
    }
    addBubble("ai", "Здравствуйте! Задайте медицинский вопрос — я постараюсь помочь.");
}

function addBubble(kind, text) {
    const el = document.createElement("div");
    el.className = "bubble " + kind;
    el.textContent = text;
    els.messages.appendChild(el);
    scrollToBottom();
    return el;
}

function addTyping() {
    const el = document.createElement("div");
    el.className = "bubble ai";
    el.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    els.messages.appendChild(el);
    scrollToBottom();
    return el;
}

function renderAnswer(el, data) {
    el.innerHTML = "";
    const content = document.createElement("div");
    if (data.answer_html) {
        // Ответ приходит из доверенного API RXCode AI в готовом HTML
        content.innerHTML = data.answer_html;
    } else {
        content.style.whiteSpace = "pre-wrap";
        content.textContent = data.answer_md || "Пустой ответ.";
    }
    el.appendChild(content);

    if (Array.isArray(data.sources) && data.sources.length) {
        const box = document.createElement("div");
        box.className = "sources";
        const title = document.createElement("div");
        title.className = "sources-title";
        title.textContent = "Источники:";
        box.appendChild(title);
        for (const s of data.sources) {
            if (!s || (!s.url && !s.title)) continue;
            if (s.url) {
                const a = document.createElement("a");
                a.href = s.url;
                a.target = "_blank";
                a.rel = "noopener noreferrer";
                a.textContent = s.title || s.url;
                box.appendChild(a);
            } else {
                const span = document.createElement("div");
                span.textContent = s.title;
                box.appendChild(span);
            }
        }
        el.appendChild(box);
    }
    scrollToBottom();
}

function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
}

let sending = false;

async function sendChat() {
    const text = els.chatInput.value.trim();
    if (!text || sending) return;

    sending = true;
    els.chatSend.disabled = true;
    els.chatInput.value = "";
    autoGrow();
    addBubble("user", text);
    const typing = addTyping();

    try {
        const data = await api("/api/ai/message", { message: text });
        typing.remove();
        renderAnswer(addBubble("ai", ""), data);
    } catch (e) {
        typing.remove();
        addBubble("error", e.message);
    } finally {
        sending = false;
        els.chatSend.disabled = false;
    }
}

async function resetChat() {
    if (sending) return;
    try { await api("/api/ai/reset"); } catch (e) { /* не критично */ }
    els.messages.innerHTML = "";
    greet(true);
    tg?.HapticFeedback?.impactOccurred("light");
}

function autoGrow() {
    const t = els.chatInput;
    t.style.height = "auto";
    t.style.height = Math.min(t.scrollHeight, 120) + "px";
}

// ---------- События ----------

els.regForm.addEventListener("submit", (e) => { e.preventDefault(); submitRegistration(); });
// Живая подсветка кнопки при заполнении полей
for (const f of [els.fullName, els.phone, els.email, els.birthDate]) {
    f.addEventListener("input", updateRegButton);
    f.addEventListener("change", updateRegButton);
}

els.chatForm.addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
els.chatReset.addEventListener("click", resetChat);
els.chatInput.addEventListener("input", autoGrow);
els.chatInput.addEventListener("keydown", (e) => {
    // Enter — отправка, Shift+Enter — перенос строки (удобно на десктопе)
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendChat();
    }
});

init();
