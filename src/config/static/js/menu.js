/**
 * Weekly menu planner: sidebar, multi-menu CRUD, generation, save, clear.
 * Supports both own menus and friend menus (when collaborative editing is accepted).
 */

// --- Helpers ---

function isViewingFriendMenu() {
    return currentMenuOwnerId !== null;
}

function canEditCurrentMenu() {
    if (!isViewingFriendMenu()) return true;
    return friendCanEditMenus;
}

function getActiveMenuList() {
    return isViewingFriendMenu() ? friendMenus : menus;
}

function getActiveMenuId() {
    return isViewingFriendMenu() ? activeFriendMenuId : activeMenuId;
}

function buildMenuApiUrl(menuId) {
    if (isViewingFriendMenu()) {
        return '/api/friends/' + currentMenuOwnerId + '/menus/' + menuId + '/';
    }
    return '/api/menus/' + menuId + '/';
}

function buildMenuListApiUrl() {
    if (isViewingFriendMenu()) {
        return '/api/friends/' + currentMenuOwnerId + '/menus/';
    }
    return '/api/menus/';
}

function _findPrimaryOrFirstId(menuList) {
    var primary = menuList.find(function (m) { return m.is_primary; });
    return primary ? primary.id : menuList[0].id;
}

function _initEmptyWeekMenu() {
    weekMenu = {};
    for (var d = 0; d < 7; d++) {
        for (var m = 0; m < 4; m++) {
            weekMenu[d + '-' + m] = null;
        }
    }
}

// --- Sidebar rendering and interactions ---

function renderMenuSidebar() {
    var list = document.getElementById('menuSidebarList');
    if (!list) return;
    list.innerHTML = '';
    var menuList = getActiveMenuList();
    var currentId = getActiveMenuId();
    var editable = canEditCurrentMenu();

    menuList.forEach(function (m) {
        var item = document.createElement('div');
        item.className = 'menu-sidebar-item' + (m.id === currentId ? ' active' : '');
        item.dataset.menuId = m.id;

        var nameSpan = document.createElement('span');
        nameSpan.className = 'menu-sidebar-item-name';
        nameSpan.textContent = m.name;
        nameSpan.onclick = function () { selectMenu(m.id); };

        item.appendChild(nameSpan);

        if (editable) {
            var actions = document.createElement('span');
            actions.className = 'menu-sidebar-item-actions';

            if (!isViewingFriendMenu()) {
                var primaryBtn = document.createElement('button');
                primaryBtn.className = 'btn-icon btn-primary-star' + (m.is_primary ? ' active' : '');
                primaryBtn.title = m.is_primary ? 'Основное меню' : 'Сделать основным';
                primaryBtn.textContent = m.is_primary ? '★' : '☆';
                primaryBtn.onclick = function (e) { e.stopPropagation(); setPrimaryMenu(m.id); };
                actions.appendChild(primaryBtn);
            }

            var renameBtn = document.createElement('button');
            renameBtn.className = 'btn-icon';
            renameBtn.title = 'Переименовать';
            renameBtn.textContent = '✏️';
            renameBtn.onclick = function (e) { e.stopPropagation(); renameMenu(m.id, m.name); };

            var deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-icon';
            deleteBtn.title = 'Удалить';
            deleteBtn.textContent = '🗑️';
            deleteBtn.onclick = function (e) { e.stopPropagation(); deleteMenu(m.id); };

            actions.appendChild(renameBtn);
            actions.appendChild(deleteBtn);
            item.appendChild(actions);
        }

        list.appendChild(item);
    });
    updateActiveMenuTitle();
    updateMenuSidebarVisibility();
}

function updateActiveMenuTitle() {
    var titleEl = document.getElementById('activeMenuTitle');
    if (!titleEl) return;
    if (isViewingFriendMenu()) {
        var friend = friends.find(function (f) { return f.user_id === currentMenuOwnerId; });
        var friendName = friend ? friend.username : 'друга';
        var activeMenu = friendMenus.find(function (m) { return m.id === activeFriendMenuId; });
        if (activeMenu) {
            titleEl.textContent = activeMenu.name + ' (' + friendName + ')';
        } else {
            titleEl.textContent = 'Меню ' + friendName;
        }
        return;
    }
    var activeMenu = menus.find(function (m) { return m.id === activeMenuId; });
    titleEl.textContent = activeMenu ? activeMenu.name : 'Планирование меню на неделю';
}

function updateMenuSidebarVisibility() {
    var sidebar = document.getElementById('menuSidebar');
    var toggle = document.getElementById('menuSidebarToggle');
    var titleEl = document.getElementById('menuSidebarTitle');
    var createBtn = document.getElementById('menuSidebarCreateBtn');
    if (!sidebar) return;

    var hasFriendMenus = isViewingFriendMenu() && friendMenus.length > 0;
    var showSidebar = !isViewingFriendMenu() || hasFriendMenus;
    sidebar.classList.toggle('hidden', !showSidebar);
    if (toggle) toggle.classList.toggle('hidden', !showSidebar);

    if (titleEl) {
        if (isViewingFriendMenu()) {
            var friend = friends.find(function (f) { return f.user_id === currentMenuOwnerId; });
            titleEl.textContent = friend ? 'Меню ' + friend.username : 'Меню друга';
        } else {
            titleEl.textContent = 'Мои меню';
        }
    }
    if (createBtn) {
        createBtn.style.display = canEditCurrentMenu() ? '' : 'none';
    }
}

function toggleMenuSidebar() {
    var sidebar = document.getElementById('menuSidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
}

async function selectMenu(menuId) {
    if (!isViewingFriendMenu()) {
        try {
            var menuData = await apiFetch('/api/menus/' + menuId + '/');
            activeMenuId = menuId;
            weekMenu = menuData;
            renderMenuSidebar();
            generateWeekPlanner();
            updateShoppingOwnerLabel();
            _closeSidebarIfOpen();
        } catch (e) {
            showError(e.message || 'Ошибка загрузки меню');
        }
        return;
    }

    try {
        var menuData = await apiFetch('/api/friends/' + currentMenuOwnerId + '/menus/' + menuId + '/');
        activeFriendMenuId = menuId;
        weekMenu = menuData;
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        _closeSidebarIfOpen();
    } catch (e) {
        showError(e.message || 'Ошибка загрузки меню');
    }
}

function _closeSidebarIfOpen() {
    var sidebar = document.getElementById('menuSidebar');
    if (sidebar && sidebar.classList.contains('open')) {
        sidebar.classList.remove('open');
    }
}

async function createNewMenu() {
    var name = prompt('Название нового меню:', 'Меню на неделю');
    if (name === null) return;
    name = name.trim() || 'Меню на неделю';
    try {
        var newMenu = await apiFetch(buildMenuListApiUrl(), {
            method: 'POST',
            body: { name: name }
        });
        var menuList = getActiveMenuList();
        menuList.push(newMenu);

        if (isViewingFriendMenu()) {
            activeFriendMenuId = newMenu.id;
        } else {
            activeMenuId = newMenu.id;
        }

        _initEmptyWeekMenu();
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        showToast('Меню «' + name + '» создано');
        _closeSidebarIfOpen();
    } catch (e) {
        showError(e.message || 'Ошибка создания меню');
    }
}

async function renameMenu(menuId, currentName) {
    var newName = prompt('Новое название меню:', currentName);
    if (newName === null || newName.trim() === '' || newName.trim() === currentName) return;
    newName = newName.trim();
    try {
        var updated = await apiFetch(buildMenuApiUrl(menuId), {
            method: 'PATCH',
            body: { name: newName }
        });
        var menuList = getActiveMenuList();
        var idx = menuList.findIndex(function (m) { return m.id === menuId; });
        if (idx !== -1) menuList[idx].name = updated.name;
        renderMenuSidebar();
        updateShoppingOwnerLabel();
        showToast('Меню переименовано');
    } catch (e) {
        showError(e.message || 'Ошибка переименования');
    }
}

async function deleteMenu(menuId) {
    var menuList = getActiveMenuList();
    if (menuList.length <= 1) {
        showError('Нельзя удалить единственное меню');
        return;
    }
    if (!confirm('Удалить это меню? Все блюда в нём будут потеряны.')) return;
    try {
        await apiFetch(buildMenuApiUrl(menuId), { method: 'DELETE' });

        if (isViewingFriendMenu()) {
            friendMenus = friendMenus.filter(function (m) { return m.id !== menuId; });
            if (activeFriendMenuId === menuId) {
                activeFriendMenuId = friendMenus[0].id;
                var menuData = await apiFetch(buildMenuApiUrl(activeFriendMenuId));
                weekMenu = menuData;
            }
        } else {
            menus = menus.filter(function (m) { return m.id !== menuId; });
            if (activeMenuId === menuId) {
                activeMenuId = menus[0].id;
                var menuData = await apiFetch(buildMenuApiUrl(activeMenuId));
                weekMenu = menuData;
            }
        }

        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        showToast('Меню удалено');
    } catch (e) {
        showError(e.message || 'Ошибка удаления меню');
    }
}

async function setPrimaryMenu(menuId) {
    try {
        await apiFetch('/api/menus/' + menuId + '/set-primary/', { method: 'POST' });
        menus.forEach(function (m) { m.is_primary = (m.id === menuId); });
        renderMenuSidebar();
        showToast('Основное меню установлено');
    } catch (e) {
        showError(e.message || 'Ошибка установки основного меню');
    }
}

// --- Friend menu owner select ---

function populateMenuOwnerSelect() {
    var select = document.getElementById('menuOwnerSelect');
    if (!select) return;
    var prevValue = select.value;
    while (select.options.length > 1) {
        select.remove(1);
    }
    if (friends && friends.length > 0) {
        friends.forEach(function (f) {
            var opt = document.createElement('option');
            opt.value = String(f.user_id);
            opt.textContent = f.username || '';
            select.appendChild(opt);
        });
    }
    var validValues = [''].concat((friends || []).map(function (f) { return String(f.user_id); }));
    if (prevValue && validValues.indexOf(prevValue) === -1) {
        select.value = '';
        handleMenuOwnerChange();
    }
}

function updateShoppingOwnerLabel() {
    var label = document.getElementById('shoppingOwnerLabel');
    if (!label) return;
    if (isViewingFriendMenu()) {
        var friend = friends.find(function (f) { return f.user_id === currentMenuOwnerId; });
        label.textContent = friend ? '(меню ' + friend.username + ')' : '(меню друга)';
    } else {
        var activeMenu = menus.find(function (m) { return m.id === activeMenuId; });
        label.textContent = activeMenu ? '(' + activeMenu.name + ')' : '(моё меню)';
    }
}

function handleMenuOwnerChange() {
    var select = document.getElementById('menuOwnerSelect');
    if (!select) return;
    var value = select.value;
    if (!value) {
        _resetToOwnMenu();
        return;
    }
    var friendId = parseInt(value, 10);
    currentMenuOwnerId = friendId;
    _loadFriendMenus(friendId);
}

function _resetToOwnMenu() {
    currentMenuOwnerId = null;
    friendMenus = [];
    activeFriendMenuId = null;
    friendCanEditMenus = false;
    selectMenu(activeMenuId);
}

async function _loadFriendMenus(friendId) {
    try {
        var response = await apiFetch('/api/friends/' + friendId + '/menus/');
        friendMenus = response.menus || [];
        friendCanEditMenus = response.can_edit || false;

        if (friendMenus.length > 0) {
            activeFriendMenuId = _findPrimaryOrFirstId(friendMenus);
            var menuData = await apiFetch('/api/friends/' + friendId + '/menus/' + activeFriendMenuId + '/');
            weekMenu = menuData;
        } else {
            activeFriendMenuId = null;
            _initEmptyWeekMenu();
        }

        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        updateSaveClearButtonsState();
    } catch (e) {
        showError(e.message || 'Ошибка загрузки меню друга');
        currentMenuOwnerId = null;
        friendMenus = [];
        friendCanEditMenus = false;
    }
}

function updateSaveClearButtonsState() {
    var saveBtn = document.querySelector('.menu-main .card-actions .btn-primary');
    var clearBtn = document.getElementById('clear-menu-btn');
    var canEdit = canEditCurrentMenu();
    if (saveBtn) saveBtn.style.display = canEdit ? '' : 'none';
    if (clearBtn) clearBtn.style.display = canEdit ? '' : 'none';
}

// --- Week planner rendering ---

function setDefaultShoppingDates() {
    var start = document.getElementById('shoppingStartDate');
    var end = document.getElementById('shoppingEndDate');
    if (!start.value) {
        var today = new Date();
        var monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));
        var sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        start.value = monday.toISOString().slice(0, 10);
        end.value = sunday.toISOString().slice(0, 10);
    }
}

function getRecipeSource() {
    return recipes;
}

function getDayNutritionTotals(dayIndex) {
    var source = getRecipeSource();
    var calories = 0, protein = 0, fat = 0, carbs = 0;
    for (var m = 0; m < 4; m++) {
        var recipeId = weekMenu[dayIndex + '-' + m];
        if (!recipeId) continue;
        var r = source.find(function (x) { return x.id === recipeId; });
        if (r) {
            calories += r.total_calories || 0;
            protein += r.total_protein || 0;
            fat += r.total_fat || 0;
            carbs += r.total_carbs || 0;
        }
    }
    return { calories: calories, protein: protein, fat: fat, carbs: carbs };
}

function formatDaySummary(totals) {
    if (totals.calories === 0 && totals.protein === 0 && totals.fat === 0 && totals.carbs === 0) {
        return '—';
    }
    return Math.round(totals.calories) + ' ккал · Б ' + Math.round(totals.protein) + ' · Ж ' + Math.round(totals.fat) + ' · У ' + Math.round(totals.carbs);
}

function generateWeekPlanner() {
    var days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    var meals = ['Завтрак', 'Обед', 'Перекус', 'Ужин'];
    var container = document.getElementById('weekPlanner');
    var isReadOnly = !canEditCurrentMenu();
    var recipeSource = getRecipeSource();

    container.innerHTML = days.map(function (day, dayIndex) {
        var totals = getDayNutritionTotals(dayIndex);
        var mealSlots = meals.map(function (meal, mealIndex) {
            var key = dayIndex + '-' + mealIndex;
            var slotVal = weekMenu[key];
            var selectAttrs = isReadOnly ? 'disabled' : 'onchange="updateWeekMenu()"';
            var options = recipeSource.map(function (r) {
                return '<option value="' + r.id + '"' + (slotVal == r.id ? ' selected' : '') + '>' + r.name + '</option>';
            }).join('');
            return '<div class="meal-slot"><h4>' + meal + '</h4>' +
                '<select data-day="' + dayIndex + '" data-meal="' + mealIndex + '" ' + selectAttrs + '>' +
                '<option value="">Не выбрано</option>' + options + '</select></div>';
        }).join('');
        return '<div class="day-card"><h3>' + day + '</h3>' + mealSlots +
            '<div class="day-summary" data-day-index="' + dayIndex + '">' + formatDaySummary(totals) + '</div></div>';
    }).join('');
    updateSaveClearButtonsState();
}

function updateWeekMenu() {
    var selects = document.querySelectorAll('#weekPlanner select');
    weekMenu = {};
    selects.forEach(function (select) {
        var key = select.dataset.day + '-' + select.dataset.meal;
        weekMenu[key] = select.value ? parseInt(select.value) : null;
    });
    document.querySelectorAll('#weekPlanner .day-summary').forEach(function (el) {
        var dayIndex = parseInt(el.dataset.dayIndex, 10);
        el.textContent = formatDaySummary(getDayNutritionTotals(dayIndex));
    });
}

// --- Save and clear ---

async function saveWeekMenu() {
    if (!canEditCurrentMenu()) {
        showError('Нет прав на редактирование этого меню');
        return;
    }
    var menuId = getActiveMenuId();
    if (!menuId) {
        showError('Не выбрано меню');
        return;
    }
    updateWeekMenu();
    try {
        await apiFetch(buildMenuApiUrl(menuId), { method: 'PUT', body: weekMenu });
        showToast('Меню сохранено');
    } catch (e) {
        showError(e.message || 'Ошибка сохранения меню');
    }
}

async function clearWeekMenu() {
    if (!canEditCurrentMenu()) {
        showError('Нет прав на редактирование этого меню');
        return;
    }
    var menuId = getActiveMenuId();
    if (!menuId) return;
    if (!confirm('Очистить все слоты этого меню?')) return;
    _initEmptyWeekMenu();
    try {
        await apiFetch(buildMenuApiUrl(menuId), { method: 'PUT', body: weekMenu });
        generateWeekPlanner();
    } catch (e) {
        showError(e.message || 'Ошибка очистки меню');
    }
}
