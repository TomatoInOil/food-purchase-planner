/**
 * Common API helpers: CSRF token retrieval, fetch wrapper, error display.
 */

function getCsrfToken() {
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
}

async function apiFetch(url, options = {}) {
    const init = {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            ...options.headers
        },
        ...options
    };
    if (options.body && typeof options.body !== 'string') {
        init.body = JSON.stringify(options.body);
    }
    const response = await fetch(url, init);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        const msg = data.error || data.errors || data.detail || JSON.stringify(data) || 'Ошибка запроса';
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
}

function showError(msg) {
    alert(msg);
}

function showToast(msg, durationMs) {
    durationMs = durationMs ?? 2500;
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('toast-show'));
    setTimeout(() => {
        toast.classList.remove('toast-show');
        setTimeout(() => toast.remove(), 300);
    }, durationMs);
}
