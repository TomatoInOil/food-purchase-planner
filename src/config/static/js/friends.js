/**
 * Friends tab: friend request modal and placeholder actions.
 */

let currentFriendRequestName = '';

function copyMyCode() {
    const el = document.getElementById('myCodeDisplay');
    const code = (el && el.textContent) ? el.textContent.trim() : '';
    if (!code) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(() => {
            showToast('Код скопирован');
        }).catch(() => {
            copyMyCodeFallback(code);
        });
    } else {
        copyMyCodeFallback(code);
    }
}

function copyMyCodeFallback(text) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '0';
    textarea.style.fontSize = '16px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.setSelectionRange(0, text.length);
    try {
        document.execCommand('copy');
        showToast('Код скопирован');
    } catch (e) {
        showError('Не удалось скопировать');
    }
    document.body.removeChild(textarea);
}

function openFriendRequestModal(userDisplayName) {
    currentFriendRequestName = userDisplayName;
    document.getElementById('modalFriendTitle').textContent = userDisplayName || 'Запрос в друзья';
    document.getElementById('friendModal').classList.add('active');
}

function closeFriendModal() {
    document.getElementById('friendModal').classList.remove('active');
    currentFriendRequestName = '';
}

function handleFriendRequestAccept() {
    closeFriendModal();
    showError('Запрос принят');
}

function handleFriendRequestDecline() {
    closeFriendModal();
    showError('Запрос отклонён');
}

let currentFriendRemoveName = '';

function openFriendRemoveModal(friendDisplayName) {
    currentFriendRemoveName = friendDisplayName;
    document.getElementById('modalFriendRemoveTitle').textContent = friendDisplayName || 'Друг';
    document.getElementById('friendRemoveModal').classList.add('active');
}

function closeFriendRemoveModal() {
    document.getElementById('friendRemoveModal').classList.remove('active');
    currentFriendRemoveName = '';
}

function handleFriendRemove() {
    closeFriendRemoveModal();
    showError('Друг удалён');
}
