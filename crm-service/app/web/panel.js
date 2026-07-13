const els = (id) => document.getElementById(id);
let token = localStorage.getItem("crm_token") || "";
let pollTimer = null;

// ---------- HTTP ----------

async function apiRaw(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(path, { ...options, headers });
    const data = await res.json().catch(() => ({}));
    if (res.status === 401 && path !== "/api/auth/login") {
        logout();
        throw new Error("Сессия истекла, войдите заново");
    }
    if (!res.ok || data.ok === false) throw new Error(data.error || "Ошибка запроса");
    return data;
}

// ---------- Вход ----------

function showLogin() {
    els("login-screen").hidden = false;
    els("panel-screen").hidden = true;
}
function showPanel() {
    els("login-screen").hidden = true;
    els("panel-screen").hidden = false;
    restoreBroadcast();
}

// Восстанавливает окно статуса последней рассылки после перезагрузки страницы
function restoreBroadcast() {
    const id = localStorage.getItem("crm_last_broadcast");
    if (!id) return;
    els("bcast-id").textContent = id;
    els("status-card").hidden = false;
    startPolling(id);
}

async function doLogin(e) {
    e.preventDefault();
    els("login-error").hidden = true;
    try {
        const data = await apiRaw("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: els("login-email").value.trim(),
                password: els("login-password").value,
            }),
        });
        token = data.token;
        localStorage.setItem("crm_token", token);
        showPanel();
    } catch (err) {
        els("login-error").textContent = err.message;
        els("login-error").hidden = false;
    }
}

function logout() {
    token = "";
    localStorage.removeItem("crm_token");
    localStorage.removeItem("crm_last_broadcast");
    if (pollTimer) clearInterval(pollTimer);
    els("status-card").hidden = true;
    selectedEmails = [];
    renderChips();
    hideSuggest();
    blocks = [{ type: "title", text: "" }];
    renderBlocks();
    showLogin();
}

// ---------- Фильтры ----------

let selectedEmails = [];
let emailTimer = null;

function collectFilters() {
    const f = {};
    const from = els("f-created-from").value;
    const to = els("f-created-to").value;
    const email = els("f-has-email").value;
    const phone = els("f-has-phone").value;
    if (from) f.created_from = from;
    if (to) f.created_to = to;
    if (email) f.has_email = email === "yes";
    if (phone) f.has_phone = phone === "yes";
    if (selectedEmails.length) f.emails = selectedEmails.slice();
    return f;
}

// ---------- Мультивыбор получателей по email ----------

function renderChips() {
    const box = els("email-chips");
    box.innerHTML = "";
    selectedEmails.forEach((em) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = em;
        const x = document.createElement("button");
        x.type = "button";
        x.textContent = "✕";
        x.addEventListener("click", () => {
            selectedEmails = selectedEmails.filter((e) => e !== em);
            renderChips();
        });
        chip.appendChild(x);
        box.appendChild(chip);
    });
}

function hideSuggest() {
    els("email-suggest").hidden = true;
    els("email-suggest").innerHTML = "";
}

function renderSuggest(emails) {
    const box = els("email-suggest");
    box.innerHTML = "";
    const list = (emails || []).filter((e) => selectedEmails.indexOf(e) === -1);
    if (!list.length) { hideSuggest(); return; }
    list.forEach((em) => {
        const d = document.createElement("div");
        d.textContent = em;
        // mousedown срабатывает раньше blur — успеваем добавить до скрытия списка
        d.addEventListener("mousedown", (ev) => {
            ev.preventDefault();
            if (selectedEmails.indexOf(em) === -1) selectedEmails.push(em);
            renderChips();
            // Оставляем введённый текст, чтобы быстро выбрать несколько похожих адресов,
            // и обновляем список (уже без только что выбранного).
            const q = els("email-input").value.trim();
            if (q) searchEmails(q); else hideSuggest();
            els("email-input").focus();
        });
        box.appendChild(d);
    });
    box.hidden = false;
}

async function searchEmails(q) {
    try {
        const headers = {};
        if (token) headers["Authorization"] = "Bearer " + token;
        const res = await fetch("/api/segments/emails?q=" + encodeURIComponent(q), { headers });
        if (res.status === 401) { logout(); return; }
        const data = await res.json().catch(() => ({}));
        renderSuggest(data.emails);
    } catch (e) {
        hideSuggest();
    }
}

// ---------- Конструктор сообщения ----------

let blocks = [{ type: "title", text: "" }];
const BLOCK_LABELS = { title: "Заголовок", subtitle: "Подзаголовок", text: "Текст", link: "Ссылка" };

function renderBlocks() {
    const ed = els("editor");
    ed.innerHTML = "";
    blocks.forEach((b, i) => ed.appendChild(renderBlock(b, i)));
}

function iconBtn(sym, fn) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "icon-btn";
    btn.textContent = sym;
    btn.addEventListener("click", fn);
    return btn;
}

function renderBlock(b, i) {
    const wrap = document.createElement("div");
    wrap.className = "block b-" + b.type;

    const head = document.createElement("div");
    head.className = "block-head";
    const lab = document.createElement("span");
    lab.className = "block-label";
    lab.textContent = BLOCK_LABELS[b.type] || "";
    head.appendChild(lab);
    if (b.type !== "title") {
        const ctr = document.createElement("div");
        ctr.className = "block-ctrls";
        ctr.appendChild(iconBtn("↑", () => moveBlock(i, -1)));
        ctr.appendChild(iconBtn("↓", () => moveBlock(i, 1)));
        ctr.appendChild(iconBtn("✕", () => removeBlock(i)));
        head.appendChild(ctr);
    }
    wrap.appendChild(head);

    if (b.type === "link") {
        const t = document.createElement("input");
        t.type = "text"; t.className = "blk-input"; t.placeholder = "Текст ссылки";
        t.value = b.text || "";
        t.addEventListener("input", () => { blocks[i].text = t.value; });
        const u = document.createElement("input");
        u.type = "url"; u.className = "blk-input"; u.placeholder = "https://…";
        u.value = b.url || "";
        u.addEventListener("input", () => { blocks[i].url = u.value; });
        wrap.appendChild(t);
        wrap.appendChild(u);
    } else if (b.type === "text") {
        const ta = document.createElement("textarea");
        ta.className = "blk-input"; ta.rows = 3; ta.placeholder = "Текст…";
        ta.value = b.text || "";
        ta.addEventListener("input", () => { blocks[i].text = ta.value; });
        wrap.appendChild(ta);
    } else {
        const inp = document.createElement("input");
        inp.type = "text";
        inp.className = "blk-input blk-" + b.type;
        inp.placeholder = b.type === "title" ? "Заголовок" : "Подзаголовок";
        inp.value = b.text || "";
        inp.addEventListener("input", () => { blocks[i].text = inp.value; });
        wrap.appendChild(inp);
    }
    return wrap;
}

function addBlock(type) {
    blocks.push(type === "link" ? { type, text: "", url: "" } : { type, text: "" });
    renderBlocks();
}

function removeBlock(i) {
    if (blocks[i] && blocks[i].type === "title") return; // заголовок не удаляем
    blocks.splice(i, 1);
    renderBlocks();
}

function moveBlock(i, dir) {
    const j = i + dir;
    if (j < 1 || j >= blocks.length) return; // заголовок всегда первый
    const tmp = blocks[i];
    blocks[i] = blocks[j];
    blocks[j] = tmp;
    renderBlocks();
}

async function doPreview() {
    const btn = els("preview-btn");
    btn.disabled = true;
    try {
        const data = await apiRaw("/api/segments/preview", {
            method: "POST",
            body: JSON.stringify({ filters: collectFilters() }),
        });
        els("preview-result").innerHTML =
            "Под фильтр попадает: <strong>" + data.count + "</strong> чел.";
        els("preview-result").hidden = false;
    } catch (err) {
        els("preview-result").innerHTML = '<span style="color:var(--danger)">' + err.message + "</span>";
        els("preview-result").hidden = false;
    } finally {
        btn.disabled = false;
    }
}

// ---------- Рассылка ----------

function showSendError(msg) {
    els("send-error").textContent = msg;
    els("send-error").hidden = false;
}

async function doSend() {
    els("send-error").hidden = true;
    const file = els("attachment").files[0];
    const hasContent = blocks.some((b) => (b.text && b.text.trim()) || (b.url && b.url.trim()));
    if (!hasContent && !file) {
        showSendError("Добавьте текст или прикрепите файл");
        return;
    }
    if (!confirm("Отправить рассылку выбранному сегменту?")) return;

    // multipart/form-data: блоки конструктора + фильтры + необязательный файл
    const fd = new FormData();
    fd.append("filters", JSON.stringify(collectFilters()));
    fd.append("blocks", JSON.stringify(blocks));
    if (file) fd.append("file", file);

    const btn = els("send-btn");
    btn.disabled = true;
    try {
        const headers = {};
        if (token) headers["Authorization"] = "Bearer " + token;
        const res = await fetch("/api/broadcast", { method: "POST", headers, body: fd });
        const data = await res.json().catch(() => ({}));
        if (res.status === 401) { logout(); throw new Error("Сессия истекла, войдите заново"); }
        if (!res.ok || data.ok === false) throw new Error(data.error || "Ошибка запроса");

        els("bcast-id").textContent = data.broadcast_id;
        els("status-card").hidden = false;
        localStorage.setItem("crm_last_broadcast", data.broadcast_id);
        startPolling(data.broadcast_id);
    } catch (err) {
        showSendError(err.message);
    } finally {
        btn.disabled = false;
    }
}

function startPolling(id) {
    if (pollTimer) clearInterval(pollTimer);
    const tick = async () => {
        try {
            const s = await apiRaw("/api/broadcast/" + id + "/status");
            els("s-sent").textContent = s.sent;
            els("s-pending").textContent = s.pending;
            els("s-blocked").textContent = s.blocked;
            els("s-failed").textContent = s.failed;
            els("s-total").textContent = s.total;
            if (s.pending === 0) clearInterval(pollTimer);
        } catch (err) {
            clearInterval(pollTimer);
        }
    };
    tick();
    pollTimer = setInterval(tick, 2000);
}

// ---------- Старт ----------

els("login-form").addEventListener("submit", doLogin);
els("logout").addEventListener("click", logout);
els("preview-btn").addEventListener("click", doPreview);
els("send-btn").addEventListener("click", doSend);

// Прикрепление файла
els("attachment").addEventListener("change", () => {
    const f = els("attachment").files[0];
    els("file-name").textContent = f ? f.name : "";
    els("file-clear").hidden = !f;
});
els("file-clear").addEventListener("click", () => {
    els("attachment").value = "";
    els("file-name").textContent = "";
    els("file-clear").hidden = true;
});

// Автодополнение email
els("email-input").addEventListener("input", () => {
    const q = els("email-input").value.trim();
    clearTimeout(emailTimer);
    if (q.length < 1) { hideSuggest(); return; }
    emailTimer = setTimeout(() => searchEmails(q), 250);
});
els("email-input").addEventListener("blur", () => setTimeout(hideSuggest, 150));
els("email-input").addEventListener("focus", () => {
    const q = els("email-input").value.trim();
    if (q) searchEmails(q);
});

// Конструктор: меню «Добавить блок»
els("add-block-btn").addEventListener("click", () => {
    els("block-menu").hidden = !els("block-menu").hidden;
});
document.querySelectorAll("#block-menu [data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
        addBlock(btn.dataset.add);
        els("block-menu").hidden = true;
    });
});

renderBlocks();

if (token) showPanel(); else showLogin();
