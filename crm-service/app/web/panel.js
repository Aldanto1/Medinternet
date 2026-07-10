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
    if (pollTimer) clearInterval(pollTimer);
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

async function doSend() {
    els("send-error").hidden = true;
    const text = els("message").value.trim();
    if (!text) {
        els("send-error").textContent = "Введите текст сообщения";
        els("send-error").hidden = false;
        return;
    }
    if (!confirm("Отправить рассылку выбранному сегменту?")) return;

    const btn = els("send-btn");
    btn.disabled = true;
    try {
        const data = await apiRaw("/api/broadcast", {
            method: "POST",
            body: JSON.stringify({ filters: collectFilters(), text }),
        });
        els("bcast-id").textContent = data.broadcast_id;
        els("status-card").hidden = false;
        startPolling(data.broadcast_id);
    } catch (err) {
        els("send-error").textContent = err.message;
        els("send-error").hidden = false;
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

if (token) showPanel(); else showLogin();
