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
    showLogin();
}

// ---------- Фильтры ----------

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
    return f;
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
    const text = els("message").value.trim();
    const file = els("attachment").files[0];
    if (!text && !file) {
        showSendError("Введите текст или прикрепите файл");
        return;
    }
    if (!confirm("Отправить рассылку выбранному сегменту?")) return;

    // multipart/form-data: текст + фильтры + необязательный файл
    const fd = new FormData();
    fd.append("filters", JSON.stringify(collectFilters()));
    fd.append("text", text);
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

if (token) showPanel(); else showLogin();
