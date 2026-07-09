const tg = window.Telegram?.WebApp;

const form = document.getElementById("reg-form");
const errorEl = document.getElementById("error");
const statusEl = document.getElementById("status");

if (tg) {
    tg.ready();
    tg.expand();

    // Предзаполним ФИО из данных Telegram
    const u = tg.initDataUnsafe?.user;
    if (u) {
        const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
        if (name) document.getElementById("full_name").value = name;
    }
}

function showError(msg) {
    errorEl.textContent = msg;
    errorEl.hidden = false;
}

function clearError() {
    errorEl.hidden = true;
}

async function submit() {
    clearError();

    const payload = {
        initData: tg?.initData || "",
        full_name: document.getElementById("full_name").value.trim(),
        phone: document.getElementById("phone").value.trim(),
        email: document.getElementById("email").value.trim(),
        birth_date: document.getElementById("birth_date").value,
    };

    if (!payload.full_name) {
        showError("Пожалуйста, укажите ФИО.");
        return;
    }
    if (payload.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(payload.email)) {
        showError("Проверьте корректность email.");
        return;
    }

    setBusy(true);
    try {
        const res = await fetch("/api/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));

        if (!res.ok || !data.ok) {
            showError(data.error || "Не удалось сохранить. Попробуйте ещё раз.");
            setBusy(false);
            return;
        }

        form.hidden = true;
        statusEl.hidden = false;
        statusEl.className = "status success";
        statusEl.textContent = "✅ Регистрация прошла успешно!";

        if (tg) {
            tg.HapticFeedback?.notificationOccurred("success");
            setTimeout(() => tg.close(), 1500);
        }
    } catch (e) {
        showError("Нет связи с сервером. Проверьте интернет и попробуйте снова.");
        setBusy(false);
    }
}

function setBusy(busy) {
    if (!tg?.MainButton) return;
    if (busy) {
        tg.MainButton.showProgress();
    } else {
        tg.MainButton.hideProgress();
    }
}

form.addEventListener("submit", (e) => {
    e.preventDefault();
    submit();
});

// Кнопка отправки — нативная кнопка Telegram внизу экрана
if (tg?.MainButton) {
    tg.MainButton.setText("Зарегистрироваться");
    tg.MainButton.show();
    tg.MainButton.onClick(submit);
} else {
    // Фолбэк, если открыто вне Telegram — добавим обычную кнопку
    const btn = document.createElement("button");
    btn.textContent = "Зарегистрироваться";
    btn.type = "submit";
    btn.style.cssText =
        "margin-top:20px;width:100%;padding:14px;font-size:16px;border:none;" +
        "border-radius:10px;background:var(--button);color:var(--button-text);cursor:pointer;";
    form.appendChild(btn);
}
