const tg = window.Telegram?.WebApp;
const initData = tg?.initData || "";

// ---------- Переводы ----------

const I18N = {
    ru: {
        welcome: "Добро пожаловать в Мединтернет",
        chooseLang: "Выбрать язык",
        register: "Регистрация",
        searcher: "Медицинский поисковик",
        regTitle: "Регистрация",
        regSubtitle: "Заполните данные, чтобы продолжить работу с Мединтернет.",
        fioLabel: "ФИО", fioPh: "Иванов Иван Иванович",
        phoneLabel: "Телефон", phonePh: "+7 900 000-00-00",
        emailLabel: "Email", emailPh: "you@example.com",
        birthLabel: "Дата рождения",
        submit: "Зарегистрироваться", submitting: "Отправка…",
        errFio: "Пожалуйста, укажите ФИО.",
        errEmail: "Проверьте корректность email.",
        chatTitle: "Медицинский поисковик",
        newDialog: "Новый диалог",
        inputPh: "Задайте вопрос…",
        greet: "Здравствуйте! Задайте медицинский вопрос — я постараюсь помочь.",
        aiUnavailable: "Чат временно недоступен.",
        errGeneric: "Что-то пошло не так. Попробуйте позже.",
        sources: "Источники:",
        emptyAnswer: "Пустой ответ.",
    },
    en: {
        welcome: "Welcome to Medinternet",
        chooseLang: "Choose language",
        register: "Sign up",
        searcher: "Medical search",
        regTitle: "Sign up",
        regSubtitle: "Fill in your details to continue with Medinternet.",
        fioLabel: "Full name", fioPh: "John Smith",
        phoneLabel: "Phone", phonePh: "+1 555 000-0000",
        emailLabel: "Email", emailPh: "you@example.com",
        birthLabel: "Date of birth",
        submit: "Sign up", submitting: "Sending…",
        errFio: "Please enter your full name.",
        errEmail: "Please check the email.",
        chatTitle: "Medical search",
        newDialog: "New chat",
        inputPh: "Ask a question…",
        greet: "Hello! Ask a medical question — I'll do my best to help.",
        aiUnavailable: "Chat is temporarily unavailable.",
        errGeneric: "Something went wrong. Please try again later.",
        sources: "Sources:",
        emptyAnswer: "Empty response.",
    },
};

let lang = detectLang();
function detectLang() {
    try {
        const saved = localStorage.getItem("mi_lang");
        if (saved && I18N[saved]) return saved;
    } catch (e) { /* localStorage может быть недоступен */ }
    const code = tg?.initDataUnsafe?.user?.language_code || "ru";
    return code.startsWith("ru") ? "ru" : "en";
}
function t(key) { return (I18N[lang] && I18N[lang][key]) || key; }

// ---------- Элементы ----------

const els = {
    loading: document.getElementById("loading"),
    home: document.getElementById("screen-home"),
    register: document.getElementById("screen-register"),
    chat: document.getElementById("screen-chat"),
    homePrimary: document.getElementById("home-primary"),
    langButton: document.getElementById("lang-button"),
    langMenu: document.getElementById("lang-menu"),
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
        throw new Error(data.error || t("errGeneric"));
    }
    return data;
}

function applyLang() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
        el.placeholder = t(el.dataset.i18nPh);
    });
    updateHomePrimary();
    els.langMenu.querySelectorAll(".lang-option").forEach((o) => {
        o.classList.toggle("active", o.dataset.lang === lang);
    });
}

function setLang(next) {
    lang = next;
    try { localStorage.setItem("mi_lang", next); } catch (e) { /* игнор */ }
    applyLang();
}

// ---------- Навигация ----------

function showScreen(name) {
    state.screen = name;
    els.loading.hidden = name !== "loading";
    els.home.hidden = name !== "home";
    els.register.hidden = name !== "register";
    els.chat.hidden = name !== "chat";

    els.langMenu.hidden = true; // прячем список языков при смене экрана

    if (tg?.BackButton) {
        if (name === "register" || name === "chat") tg.BackButton.show();
        else tg.BackButton.hide();
    }
}

function goHome() { showScreen("home"); }

function updateHomePrimary() {
    els.homePrimary.textContent = state.registered ? t("searcher") : t("register");
}

function onHomePrimary() {
    if (state.registered) openChat();
    else showScreen("register");
}

// ---------- Инициализация ----------

async function init() {
    if (tg) { tg.ready(); tg.expand(); }
    applyLang();
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
    els.regSubmit.textContent = t("submitting");
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
        els.regSubmit.textContent = t("submit");
        updateRegButton();
    }
}

// ---------- Чат ----------

function openChat() {
    showScreen("chat");
    if (els.messages.childElementCount === 0) {
        addBubble("ai", state.aiEnabled === false ? t("aiUnavailable") : t("greet"));
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
        content.textContent = data.answer_md || t("emptyAnswer");
    }
    el.appendChild(content);

    if (Array.isArray(data.sources) && data.sources.length) {
        const box = document.createElement("div");
        box.className = "sources";
        const title = document.createElement("div");
        title.className = "sources-title";
        title.textContent = t("sources");
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
    addBubble("ai", t("greet"));
    tg?.HapticFeedback?.impactOccurred("light");
}

function autoGrow() {
    const t2 = els.chatInput;
    t2.style.height = "auto";
    t2.style.height = Math.min(t2.scrollHeight, 120) + "px";
}

// ---------- События ----------

els.homePrimary.addEventListener("click", onHomePrimary);

els.langButton.addEventListener("click", () => {
    els.langMenu.hidden = !els.langMenu.hidden;
});
els.langMenu.querySelectorAll(".lang-option").forEach((opt) => {
    opt.addEventListener("click", () => {
        setLang(opt.dataset.lang);
        els.langMenu.hidden = true;
    });
});

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
