const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

const T = {
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
    register: document.getElementById("screen-register"),
    app: document.getElementById("app"),
    regForm: document.getElementById("reg-form"),
    regError: document.getElementById("reg-error"),
    regSubmit: document.getElementById("reg-submit"),
    medId: document.getElementById("med_id"),
    messages: document.getElementById("messages"),
    chatForm: document.getElementById("chat-form"),
    chatInput: document.getElementById("chat-input"),
    chatSend: document.getElementById("chat-send"),
    chatReset: document.getElementById("chat-reset"),
};

let state = { registered: false, aiEnabled: false, user: null, screen: "loading", tab: "search" };

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

// ---------- Экраны и вкладки ----------

function showScreen(name) {
    state.screen = name;
    els.loading.hidden = name !== "loading";
    els.register.hidden = name !== "register";
    els.app.hidden = name !== "app";
    tg?.BackButton?.hide();
}

function switchTab(name) {
    state.tab = name;
    document.getElementById("tab-search").hidden = name !== "search";
    document.getElementById("tab-profile").hidden = name !== "profile";
    document.getElementById("tab-info").hidden = name !== "info";
    document.querySelectorAll(".nav-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.tab === name);
    });
    if (name === "search" && els.messages.childElementCount === 0) greetChat();
    if (name === "profile") renderProfile();
}

function openApp() {
    showScreen("app");
    switchTab("search");
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
    updateRegButton();
    if (state.registered) openApp(); else showScreen("register");
}

// ---------- Регистрация (по MedID) ----------

function regValid() {
    return /^\d{1,6}$/.test(els.medId.value.trim());
}

function updateRegButton() { els.regSubmit.disabled = !regValid(); }

async function submitRegistration() {
    els.regError.hidden = true;
    if (!regValid()) {
        els.regError.textContent = "MedID — это число от 1 до 6 цифр.";
        els.regError.hidden = false;
        return;
    }
    const medId = els.medId.value.trim();
    els.regSubmit.disabled = true;
    els.regSubmit.textContent = T.submitting;
    try {
        await api("/api/register", { med_id: medId });
        tg?.HapticFeedback?.notificationOccurred("success");
        state.registered = true;
        state.user = { med_id: Number(medId), created_at: new Date().toISOString(), tariff: "Обычный" };
        openApp();
    } catch (e) {
        els.regError.textContent = e.message;
        els.regError.hidden = false;
    } finally {
        els.regSubmit.textContent = T.submit;
        updateRegButton();
    }
}

// ---------- Личный кабинет ----------

function tgDisplayName() {
    const u = tg?.initDataUnsafe?.user;
    const name = u ? [u.first_name, u.last_name].filter(Boolean).join(" ") : "";
    return name || "Пользователь";
}

function renderProfile() {
    const u = state.user || {};
    const name = tgDisplayName();
    document.getElementById("pf-name").textContent = name;
    document.getElementById("pf-initial").textContent = (name.trim()[0] || "?");
    document.getElementById("pf-medid").textContent = (u.med_id != null ? String(u.med_id) : "—");
    document.getElementById("pf-since").textContent = fmtDate(u.created_at);
    const tariff = u.tariff || "Обычный";
    document.getElementById("pf-tariff").textContent = tariff;
    document.getElementById("pf-tariff-name").textContent = tariff;
}

function fmtDate(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return "—";
    return d.toLocaleDateString("ru-RU");
}

// ---------- Чат ----------

function greetChat() {
    if (els.messages.childElementCount > 0) return;
    addBubble("ai", state.aiEnabled === false ? T.aiUnavailable : T.greet);
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
        content.innerHTML = data.answer_html;
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
    greetChat();
    tg?.HapticFeedback?.impactOccurred("light");
}

function autoGrow() {
    const box = els.chatInput;
    box.style.height = "auto";
    box.style.height = Math.min(box.scrollHeight, 120) + "px";
}

// ---------- Информация ----------

function comingSoon(what) {
    const msg = what + " — скоро будет доступно.";
    if (tg?.showAlert) tg.showAlert(msg); else alert(msg);
}

function logout() {
    const doClose = () => tg?.close?.();
    if (tg?.showConfirm) {
        tg.showConfirm("Выйти из аккаунта?", (ok) => { if (ok) doClose(); });
    } else if (confirm("Выйти из аккаунта?")) {
        doClose();
    }
}

// ---------- События ----------

els.regForm.addEventListener("submit", (e) => { e.preventDefault(); submitRegistration(); });
els.medId.addEventListener("input", () => {
    // оставляем только цифры, максимум 6
    const cleaned = els.medId.value.replace(/\D/g, "").slice(0, 6);
    if (cleaned !== els.medId.value) els.medId.value = cleaned;
    updateRegButton();
});

els.chatForm.addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
els.chatReset.addEventListener("click", resetChat);
els.chatInput.addEventListener("input", autoGrow);
els.chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
document.querySelectorAll(".theme-toggle").forEach((b) => b.addEventListener("click", toggleTheme));

document.querySelectorAll(".nav-btn").forEach((b) => {
    b.addEventListener("click", () => switchTab(b.dataset.tab));
});

document.getElementById("subscription-btn").addEventListener("click", () => comingSoon("Подписка и оплата"));
document.getElementById("upgrade-btn").addEventListener("click", () => comingSoon("Тариф «Плюс»"));
document.getElementById("logout-btn").addEventListener("click", logout);

init();
