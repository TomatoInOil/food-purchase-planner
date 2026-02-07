/**
 * Friends tab: API-backed friends and requests management.
 *
 * High-level flows:
 *  - loadFriendsTabData
 *  - sendFriendRequestByCode
 *  - handleFriendRequestAccept / handleFriendRequestDecline
 *  - handleFriendRemove
 *  - handleToggleEditRecipes
 */

let friends = [];
let friendRequests = [];
let currentFriendRequestId = null;
let currentFriendRemoveId = null;
let currentFriendRequestName = '';
let currentFriendRemoveName = '';
let currentFriendCanEditRecipes = false;

// High-level: load all data for the Friends tab.
async function loadFriendsTabData() {
    try {
        const myCodeData = await apiFetch('/api/friends/my-code/');
        const myCodeEl = document.getElementById('myCodeDisplay');
        if (myCodeEl && myCodeData && typeof myCodeData.code === 'string') {
            myCodeEl.textContent = myCodeData.code;
        }

        friends = await apiFetch('/api/friends/');
        friendRequests = await apiFetch('/api/friend-requests/');

        renderFriends();
        renderFriendRequests();
    } catch (e) {
        showError(e.message || 'Не удалось загрузить данные друзей');
    }
}

// High-level: send friend request using friend code.
async function sendFriendRequestByCode() {
    const input = document.getElementById('friendCodeInput');
    const code = input ? input.value.trim() : '';

    if (!code) {
        showError('Введите код друга');
        return;
    }

    try {
        await apiFetch('/api/friends/send-request/', {
            method: 'POST',
            body: { code: code }
        });
        if (input) {
            input.value = '';
        }
        showToast('Запрос в друзья отправлен');
    } catch (e) {
        showError(e.message || 'Не удалось отправить запрос в друзья');
    }
}

// High-level: accept friend request from modal.
async function handleFriendRequestAccept() {
    const requestId = currentFriendRequestId;
    if (!requestId) {
        showError('Не выбран запрос в друзья');
        return;
    }

    try {
        await apiFetch(`/api/friend-requests/${requestId}/accept/`, {
            method: 'POST'
        });
        showToast('Запрос в друзья принят');

        friendRequests = await apiFetch('/api/friend-requests/');
        friends = await apiFetch('/api/friends/');
        renderFriendRequests();
        renderFriends();
        if (typeof populateMenuOwnerSelect === 'function') {
            populateMenuOwnerSelect();
        }
        if (typeof updateShoppingOwnerLabel === 'function') {
            updateShoppingOwnerLabel();
        }
    } catch (e) {
        showError(e.message || 'Не удалось принять запрос в друзья');
    } finally {
        closeFriendModal();
        currentFriendRequestId = null;
    }
}

// High-level: decline friend request from modal.
async function handleFriendRequestDecline() {
    const requestId = currentFriendRequestId;
    if (!requestId) {
        showError('Не выбран запрос в друзья');
        return;
    }

    try {
        await apiFetch(`/api/friend-requests/${requestId}/decline/`, {
            method: 'POST'
        });
        showToast('Запрос в друзья отклонён');

        friendRequests = await apiFetch('/api/friend-requests/');
        renderFriendRequests();
    } catch (e) {
        showError(e.message || 'Не удалось отклонить запрос в друзья');
    } finally {
        closeFriendModal();
        currentFriendRequestId = null;
    }
}

// High-level: remove friend from modal.
async function handleFriendRemove() {
    const userId = currentFriendRemoveId;
    if (!userId) {
        showError('Не выбран друг для удаления');
        return;
    }

    try {
        await apiFetch(`/api/friends/${userId}/remove/`, {
            method: 'POST'
        });
        showToast('Друг удалён');

        friends = await apiFetch('/api/friends/');
        renderFriends();
        if (typeof populateMenuOwnerSelect === 'function') {
            populateMenuOwnerSelect();
        }
        if (typeof updateShoppingOwnerLabel === 'function') {
            updateShoppingOwnerLabel();
        }
    } catch (e) {
        showError(e.message || 'Не удалось удалить друга');
    } finally {
        closeFriendRemoveModal();
        currentFriendRemoveId = null;
    }
}

// Medium-level: render friends list.
function renderFriends() {
    const listEl = document.getElementById('friendsList');
    if (!listEl) {
        return;
    }

    listEl.innerHTML = '';

    if (!friends || friends.length === 0) {
        return;
    }

    friends.forEach((friend) => {
        const li = document.createElement('li');
        li.className = 'friend-item';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = friend.username || '';

        li.appendChild(nameSpan);

        if (friend.can_edit_recipes) {
            const badge = document.createElement('span');
            badge.className = 'friend-edit-badge';
            badge.textContent = 'совместное редактирование';
            li.appendChild(badge);
        }

        if (friend.user_id !== undefined && friend.user_id !== null) {
            li.dataset.userId = String(friend.user_id);
        }
        if (friend.username) {
            li.dataset.friendName = friend.username;
        }
        li.onclick = function () {
            openFriendActionsFromList(friend);
        };
        listEl.appendChild(li);
    });
}

// Medium-level: render incoming friend requests.
function renderFriendRequests() {
    const listEl = document.getElementById('friendRequestsList');
    if (!listEl) {
        return;
    }

    listEl.innerHTML = '';

    if (!friendRequests || friendRequests.length === 0) {
        return;
    }

    friendRequests.forEach((req) => {
        const li = document.createElement('li');
        li.className = 'friend-item';
        li.textContent = req.from_username || '';
        if (req.id !== undefined && req.id !== null) {
            li.dataset.requestId = String(req.id);
        }
        if (req.from_username) {
            li.dataset.fromUsername = req.from_username;
        }
        li.onclick = function () {
            openFriendRequestFromList(req);
        };
        listEl.appendChild(li);
    });
}

// Medium-level: open request modal from list item.
function openFriendRequestFromList(req) {
    if (!req) {
        return;
    }
    currentFriendRequestId = req.id;
    currentFriendRequestName = req.from_username || '';
    openFriendRequestModal(currentFriendRequestName);
}

// Medium-level: open actions modal from list item.
function openFriendActionsFromList(friend) {
    if (!friend) {
        return;
    }
    currentFriendRemoveId = friend.user_id;
    currentFriendRemoveName = friend.username || '';
    currentFriendCanEditRecipes = !!friend.can_edit_recipes;
    openFriendActionsModal(currentFriendRemoveName, currentFriendCanEditRecipes);
}

// High-level: toggle friend recipe editing permission.
async function handleToggleEditRecipes() {
    const userId = currentFriendRemoveId;
    if (!userId) {
        showError('Не выбран друг');
        return;
    }

    try {
        const result = await apiFetch(`/api/friends/${userId}/toggle-edit-recipes/`, {
            method: 'POST'
        });
        const newState = result.can_edit_recipes;
        showToast(newState
            ? 'Совместное редактирование рецептов включено'
            : 'Совместное редактирование рецептов отключено'
        );

        friends = await apiFetch('/api/friends/');
        renderFriends();
        recipes = await apiFetch('/api/recipes/');
        renderRecipes();
    } catch (e) {
        showError(e.message || 'Не удалось изменить настройку');
    } finally {
        closeFriendActionsModal();
        currentFriendRemoveId = null;
    }
}

// Low-level: copy code helpers and modal UI.

function copyMyCode() {
    const el = document.getElementById('myCodeDisplay');
    const code = (el && el.textContent) ? el.textContent.trim() : '';
    if (!code) {
        return;
    }
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
    const titleEl = document.getElementById('modalFriendTitle');
    const modalEl = document.getElementById('friendModal');
    if (titleEl) {
        titleEl.textContent = userDisplayName || 'Запрос в друзья';
    }
    if (modalEl) {
        modalEl.classList.add('active');
    }
}

function closeFriendModal() {
    const modalEl = document.getElementById('friendModal');
    if (modalEl) {
        modalEl.classList.remove('active');
    }
    currentFriendRequestName = '';
}

function openFriendActionsModal(friendDisplayName, canEditRecipes) {
    const titleEl = document.getElementById('modalFriendActionsTitle');
    const modalEl = document.getElementById('friendActionsModal');
    const toggleBtn = document.getElementById('btnToggleEditRecipes');
    if (titleEl) {
        titleEl.textContent = friendDisplayName || 'Друг';
    }
    if (toggleBtn) {
        toggleBtn.textContent = canEditRecipes
            ? 'Запретить редактирование рецептов'
            : 'Разрешить редактирование рецептов';
        toggleBtn.className = canEditRecipes
            ? 'btn btn-secondary'
            : 'btn btn-primary';
        toggleBtn.style.width = '100%';
    }
    if (modalEl) {
        modalEl.classList.add('active');
    }
}

function closeFriendActionsModal() {
    const modalEl = document.getElementById('friendActionsModal');
    if (modalEl) {
        modalEl.classList.remove('active');
    }
}

function openFriendRemoveConfirm() {
    closeFriendActionsModal();
    openFriendRemoveModal(currentFriendRemoveName);
}

function openFriendRemoveModal(friendDisplayName) {
    currentFriendRemoveName = friendDisplayName;
    const titleEl = document.getElementById('modalFriendRemoveTitle');
    const modalEl = document.getElementById('friendRemoveModal');
    if (titleEl) {
        titleEl.textContent = friendDisplayName || 'Друг';
    }
    if (modalEl) {
        modalEl.classList.add('active');
    }
}

function closeFriendRemoveModal() {
    const modalEl = document.getElementById('friendRemoveModal');
    if (modalEl) {
        modalEl.classList.remove('active');
    }
    currentFriendRemoveName = '';
}
