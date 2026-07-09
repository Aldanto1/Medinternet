const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

// Тексты интерфейса (русский)
const T = {
    register: "Регистрация",
    searcher: "Медицинский поисковик",
    submit: "Зарегистрироваться",
    submitting: "Отправка…",
    greet: "Здравствуйте! Задайте медицинский вопрос — я постараюсь помочь.",
    aiUnavailable: "Чат временно недоступен.",
    errGeneric: "Что-то пошло не так. Попробуйте позже.",
    sources: "Источники:",
    emptyAnswer: "Пустой ответ.",
};

const els = {
    loading: document.getElementById("loading"),
    home: document.getElementById("screen-home"),
    register: document.getElementById("screen-register"),
    chat: document.getElementById("screen-chat"),
    homePrimary: document.getElementById("home-primary"),
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

let state = { registered: false, aiEnabled: false, screen: "loading" };

// ---------- Общее ----------

async function api(path, extra = {}) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ initData, ...extra }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
        throw new Error(data.error || T.errGeneric);
    }
    return data;
}

// ---------- Навигация ----------

function showScreen(name) {
    state.screen = name;
    els.loading.hidden = name !== "loading";
    els.home.hidden = name !== "home";
    els.register.hidden = name !== "register";
    els.chat.hidden = name !== "chat";

    if (tg?.BackButton) {
        if (name === "register" || name === "chat") tg.BackButton.show();
        else tg.BackButton.hide();
    }
}

function goHome() { showScreen("home"); }

function updateHomePrimary() {
    els.homePrimary.textContent = state.registered ? T.searcher : T.register;
}

function onHomePrimary() {
    if (state.registered) openChat();
    else showScreen("register");
}

// ---------- Инициализация ----------

async function init() {
    if (tg) { tg.ready(); tg.expand(); }
    try {
        const me = await api("/api/me");
        state.registered = !!me.registered;
        state.aiEnabled = !!me.ai_enabled;
    } catch (e) { /* дефолт: не зарегистрирован */ }
    prefillName();
    updateHomePrimary();
    showScreen("home");
}

function prefillName() {
    const u = tg?.initDataUnsafe?.user;
    if (u) {
        const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
        if (name && !els.fullName.value) els.fullName.value = name;
    }
    updateRegButton();
}

// ---------- Регистрация ----------

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
    els.regSubmit.textContent = T.submitting;
    try {
        await api("/api/register", payload);
        tg?.HapticFeedback?.notificationOccurred("success");
        state.registered = true;
        updateHomePrimary();
        goHome();
    } catch (e) {
        els.regError.textContent = e.message;
        els.regError.hidden = false;
    } finally {
        els.regSubmit.textContent = T.submit;
        updateRegButton();
    }
}

// ---------- Чат ----------

function openChat() {
    showScreen("chat");
    if (els.messages.childElementCount === 0) {
        addBubble("ai", state.aiEnabled === false ? T.aiUnavailable : T.greet);
    }
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
    el.style.whiteSpace = data.answer_html ? "normal" : "pre-wrap";
    const content = document.createElement("div");
    if (data.answer_html) {
        content.innerHTML = data.answer_html; // доверенный API нейросети
    } else {
        content.style.whiteSpace = "pre-wrap";
        content.textContent = data.answer_md || T.emptyAnswer;
    }
    el.appendChild(content);

    if (Array.isArray(data.sources) && data.sources.length) {
        const box = document.createElement("div");
        box.className = "sources";
        const title = document.createElement("div");
        title.className = "sources-title";
        title.textContent = T.sources;
        box.appendChild(title);
        for (const s of data.sources) {
            if (!s || (!s.url && !s.title)) continue;
            if (s.url) {
                const a = document.createElement("a");
                a.href = s.url; a.target = "_blank"; a.rel = "noopener noreferrer";
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

function scrollToBottom() { els.messages.scrollTop = els.messages.scrollHeight; }

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
    addBubble("ai", T.greet);
    tg?.HapticFeedback?.impactOccurred("light");
}

function autoGrow() {
    const box = els.chatInput;
    box.style.height = "auto";
    box.style.height = Math.min(box.scrollHeight, 120) + "px";
}

// ---------- События ----------

els.homePrimary.addEventListener("click", onHomePrimary);
document.querySelectorAll("[data-back]").forEach((b) => b.addEventListener("click", goHome));
tg?.BackButton?.onClick(goHome);

els.regForm.addEventListener("submit", (e) => { e.preventDefault(); submitRegistration(); });
for (const f of [els.fullName, els.phone, els.email, els.birthDate]) {
    f.addEventListener("input", updateRegButton);
    f.addEventListener("change", updateRegButton);
}

els.chatForm.addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
els.chatReset.addEventListener("click", resetChat);
els.chatInput.addEventListener("input", autoGrow);
els.chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

init();
