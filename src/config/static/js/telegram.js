/**
 * Telegram integration: account linking status and link flow.
 *
 * High-level flows:
 *  - loadTelegramStatus
 *  - linkTelegram
 *  - unlinkTelegram
 */

// High-level: load Telegram link status and render the section.
async function loadTelegramStatus() {
    const section = document.getElementById('telegramSection');
    if (!section) {
        return;
    }

    try {
        const data = await apiFetch('/api/telegram/status/');
        renderTelegramSection(section, data);
    } catch (e) {
        section.innerHTML = '<p>Не удалось загрузить статус Telegram.</p>';
    }
}

// High-level: generate a link token and open the Telegram bot link.
async function linkTelegram() {
    try {
        const data = await apiFetch('/api/telegram/generate-link/', { method: 'POST' });
        if (data && data.link) {
            window.open(data.link, '_blank');
        }
    } catch (e) {
        showError(e.message || 'Не удалось получить ссылку для привязки Telegram');
    }
}

// High-level: unlink Telegram account.
function unlinkTelegram() {
    console.log('unlink TODO');
}

// Medium-level: render Telegram section based on link status.
function renderTelegramSection(section, data) {
    if (data && data.linked) {
        section.innerHTML =
            '<p>Аккаунт Telegram привязан.</p>' +
            '<button class="btn btn-subtle" onclick="unlinkTelegram()">Отвязать</button>';
    } else {
        section.innerHTML =
            '<p>Привяжите Telegram-аккаунт, чтобы получать уведомления.</p>' +
            '<button class="btn btn-primary" onclick="linkTelegram()">Привязать Telegram</button>';
    }
}
