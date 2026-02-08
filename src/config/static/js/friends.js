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
let editRecipesRequests = [];
let currentFriendRequestId = null;
let currentFriendRemoveId = null;
let currentFriendRequestName = '';
let currentFriendRemoveName = '';
let currentFriendCanEditRecipes = false;
let currentFriendEditRecipesStatus = 'none';
let currentEditRecipesRequestId = null;

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
        editRecipesRequests = await apiFetch('/api/edit-recipes-requests/');

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

        const editStatus = friend.can_edit_recipes_status || 'none';
        if (editStatus === 'accepted') {
            const badge = document.createElement('span');
            badge.className = 'friend-edit-badge';
            badge.textContent = 'совместное редактирование';
            li.appendChild(badge);
        } else if (editStatus === 'pending') {
            const badge = document.createElement('span');
            badge.className = 'friend-edit-badge friend-edit-badge--pending';
            badge.textContent = 'запрос на редактирование';
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

// Medium-level: render incoming friend requests and edit-recipes requests.
function renderFriendRequests() {
    const listEl = document.getElementById('friendRequestsList');
    if (!listEl) {
        return;
    }

    listEl.innerHTML = '';

    if (friendRequests && friendRequests.length > 0) {
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

    if (editRecipesRequests && editRecipesRequests.length > 0) {
        editRecipesRequests.forEach((req) => {
            const li = document.createElement('li');
            li.className = 'friend-item friend-item--edit-request';

            const nameSpan = document.createElement('span');
            nameSpan.textContent = req.from_username || '';
            li.appendChild(nameSpan);

            const badge = document.createElement('span');
            badge.className = 'friend-edit-badge friend-edit-badge--pending';
            badge.textContent = 'совместное редактирование';
            li.appendChild(badge);

            li.dataset.requestId = String(req.friend_request_id);
            li.onclick = function () {
                openEditRecipesRequestFromList(req);
            };
            listEl.appendChild(li);
        });
    }
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
    currentFriendEditRecipesStatus = friend.can_edit_recipes_status || 'none';
    openFriendActionsModal(currentFriendRemoveName, currentFriendEditRecipesStatus);
}

// Medium-level: open edit-recipes request modal from list item.
function openEditRecipesRequestFromList(req) {
    if (!req) {
        return;
    }
    currentEditRecipesRequestId = req.friend_request_id;
    currentFriendRequestName = req.from_username || '';
    openEditRecipesRequestModal(currentFriendRequestName);
}

// High-level: send edit-recipes sharing request to a friend.
async function handleSendEditRecipesRequest() {
    const userId = currentFriendRemoveId;
    if (!userId) {
        showError('Не выбран друг');
        return;
    }

    try {
        await apiFetch(`/api/friends/${userId}/send-edit-recipes-request/`, {
            method: 'POST'
        });
        showToast('Запрос на совместное редактирование отправлен');

        friends = await apiFetch('/api/friends/');
        renderFriends();
    } catch (e) {
        showError(e.message || 'Не удалось отправить запрос');
    } finally {
        closeFriendActionsModal();
        currentFriendRemoveId = null;
    }
}

// High-level: revoke edit-recipes sharing with a friend.
async function handleRevokeEditRecipes() {
    const userId = currentFriendRemoveId;
    if (!userId) {
        showError('Не выбран друг');
        return;
    }

    try {
        await apiFetch(`/api/friends/${userId}/revoke-edit-recipes/`, {
            method: 'POST'
        });
        showToast('Совместное редактирование рецептов отключено');

        friends = await apiFetch('/api/friends/');
        renderFriends();
        recipes = await apiFetch('/api/recipes/');
        renderRecipes();
    } catch (e) {
        showError(e.message || 'Не удалось отключить совместное редактирование');
    } finally {
        closeFriendActionsModal();
        currentFriendRemoveId = null;
    }
}

// High-level: accept edit-recipes sharing request.
async function handleEditRecipesRequestAccept() {
    const requestId = currentEditRecipesRequestId;
    if (!requestId) {
        showError('Не выбран запрос');
        return;
    }

    try {
        await apiFetch(`/api/edit-recipes-requests/${requestId}/accept/`, {
            method: 'POST'
        });
        showToast('Совместное редактирование рецептов включено');

        friends = await apiFetch('/api/friends/');
        editRecipesRequests = await apiFetch('/api/edit-recipes-requests/');
        renderFriends();
        renderFriendRequests();
        recipes = await apiFetch('/api/recipes/');
        renderRecipes();
    } catch (e) {
        showError(e.message || 'Не удалось принять запрос');
    } finally {
        closeEditRecipesRequestModal();
        currentEditRecipesRequestId = null;
    }
}

// High-level: decline edit-recipes sharing request.
async function handleEditRecipesRequestDecline() {
    const requestId = currentEditRecipesRequestId;
    if (!requestId) {
        showError('Не выбран запрос');
        return;
    }

    try {
        await apiFetch(`/api/edit-recipes-requests/${requestId}/decline/`, {
            method: 'POST'
        });
        showToast('Запрос на совместное редактирование отклонён');

        editRecipesRequests = await apiFetch('/api/edit-recipes-requests/');
        renderFriendRequests();
    } catch (e) {
        showError(e.message || 'Не удалось отклонить запрос');
    } finally {
        closeEditRecipesRequestModal();
        currentEditRecipesRequestId = null;
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

function openFriendActionsModal(friendDisplayName, editRecipesStatus) {
    const titleEl = document.getElementById('modalFriendActionsTitle');
    const modalEl = document.getElementById('friendActionsModal');
    const toggleBtn = document.getElementById('btnToggleEditRecipes');
    if (titleEl) {
        titleEl.textContent = friendDisplayName || 'Друг';
    }
    if (toggleBtn) {
        if (editRecipesStatus === 'accepted') {
            toggleBtn.textContent = 'Отключить совместное редактирование';
            toggleBtn.className = 'btn btn-secondary';
            toggleBtn.onclick = handleRevokeEditRecipes;
            toggleBtn.disabled = false;
        } else if (editRecipesStatus === 'pending') {
            toggleBtn.textContent = 'Запрос на редактирование отправлен';
            toggleBtn.className = 'btn btn-secondary';
            toggleBtn.onclick = handleRevokeEditRecipes;
            toggleBtn.disabled = false;
        } else {
            toggleBtn.textContent = 'Запросить совместное редактирование';
            toggleBtn.className = 'btn btn-primary';
            toggleBtn.onclick = handleSendEditRecipesRequest;
            toggleBtn.disabled = false;
        }
        toggleBtn.style.width = '100%';
    }
    if (modalEl) {
        modalEl.classList.add('active');
    }
}

function openEditRecipesRequestModal(userDisplayName) {
    const titleEl = document.getElementById('modalEditRecipesTitle');
    const modalEl = document.getElementById('editRecipesRequestModal');
    if (titleEl) {
        titleEl.textContent = userDisplayName || 'Запрос на совместное редактирование';
    }
    if (modalEl) {
        modalEl.classList.add('active');
    }
}

function closeEditRecipesRequestModal() {
    const modalEl = document.getElementById('editRecipesRequestModal');
    if (modalEl) {
        modalEl.classList.remove('active');
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
