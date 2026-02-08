/**
 * Weekly menu planner: sidebar, multi-menu CRUD, generation, save, clear.
 */

// --- Sidebar rendering and interactions ---

function renderMenuSidebar() {
    const list = document.getElementById('menuSidebarList');
    if (!list) return;
    list.innerHTML = '';
    menus.forEach(function (m) {
        const item = document.createElement('div');
        item.className = 'menu-sidebar-item' + (m.id === activeMenuId ? ' active' : '');
        item.dataset.menuId = m.id;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'menu-sidebar-item-name';
        nameSpan.textContent = m.name;
        nameSpan.onclick = function () { selectMenu(m.id); };

        const actions = document.createElement('span');
        actions.className = 'menu-sidebar-item-actions';

        const renameBtn = document.createElement('button');
        renameBtn.className = 'btn-icon';
        renameBtn.title = 'Переименовать';
        renameBtn.textContent = '✏️';
        renameBtn.onclick = function (e) { e.stopPropagation(); renameMenu(m.id, m.name); };

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'btn-icon';
        deleteBtn.title = 'Удалить';
        deleteBtn.textContent = '🗑️';
        deleteBtn.onclick = function (e) { e.stopPropagation(); deleteMenu(m.id); };

        actions.appendChild(renameBtn);
        actions.appendChild(deleteBtn);
        item.appendChild(nameSpan);
        item.appendChild(actions);
        list.appendChild(item);
    });
    updateActiveMenuTitle();
    updateMenuSidebarVisibility();
}

function updateActiveMenuTitle() {
    var titleEl = document.getElementById('activeMenuTitle');
    if (!titleEl) return;
    if (currentMenuOwnerId !== null) {
        var friend = friends.find(function (f) { return f.user_id === currentMenuOwnerId; });
        titleEl.textContent = friend ? 'Меню ' + friend.username : 'Меню друга';
        return;
    }
    var activeMenu = menus.find(function (m) { return m.id === activeMenuId; });
    titleEl.textContent = activeMenu ? activeMenu.name : 'Планирование меню на неделю';
}

function updateMenuSidebarVisibility() {
    var sidebar = document.getElementById('menuSidebar');
    var toggle = document.getElementById('menuSidebarToggle');
    if (!sidebar) return;
    var isReadOnly = currentMenuOwnerId !== null;
    sidebar.classList.toggle('hidden', isReadOnly);
    if (toggle) toggle.classList.toggle('hidden', isReadOnly);
}

function toggleMenuSidebar() {
    var sidebar = document.getElementById('menuSidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
}

async function selectMenu(menuId) {
    if (currentMenuOwnerId !== null) {
        currentMenuOwnerId = null;
        var ownerSelect = document.getElementById('menuOwnerSelect');
        if (ownerSelect) ownerSelect.value = '';
    }
    try {
        var menuData = await apiFetch('/api/menus/' + menuId + '/');
        activeMenuId = menuId;
        weekMenu = menuData;
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();

        var sidebar = document.getElementById('menuSidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    } catch (e) {
        showError(e.message || 'Ошибка загрузки меню');
    }
}

async function createNewMenu() {
    var name = prompt('Название нового меню:', 'Меню на неделю');
    if (name === null) return;
    name = name.trim() || 'Меню на неделю';
    try {
        var newMenu = await apiFetch('/api/menus/', {
            method: 'POST',
            body: { name: name }
        });
        menus.push(newMenu);
        activeMenuId = newMenu.id;
        weekMenu = {};
        for (var d = 0; d < 7; d++) {
            for (var m = 0; m < 4; m++) {
                weekMenu[d + '-' + m] = null;
            }
        }
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        showToast('Меню «' + name + '» создано');

        var sidebar = document.getElementById('menuSidebar');
        if (sidebar && sidebar.classList.contains('open')) {
            sidebar.classList.remove('open');
        }
    } catch (e) {
        showError(e.message || 'Ошибка создания меню');
    }
}

async function renameMenu(menuId, currentName) {
    var newName = prompt('Новое название меню:', currentName);
    if (newName === null || newName.trim() === '' || newName.trim() === currentName) return;
    newName = newName.trim();
    try {
        var updated = await apiFetch('/api/menus/' + menuId + '/', {
            method: 'PATCH',
            body: { name: newName }
        });
        var idx = menus.findIndex(function (m) { return m.id === menuId; });
        if (idx !== -1) menus[idx].name = updated.name;
        renderMenuSidebar();
        updateShoppingOwnerLabel();
        showToast('Меню переименовано');
    } catch (e) {
        showError(e.message || 'Ошибка переименования');
    }
}

async function deleteMenu(menuId) {
    if (menus.length <= 1) {
        showError('Нельзя удалить единственное меню');
        return;
    }
    if (!confirm('Удалить это меню? Все блюда в нём будут потеряны.')) return;
    try {
        await apiFetch('/api/menus/' + menuId + '/', { method: 'DELETE' });
        menus = menus.filter(function (m) { return m.id !== menuId; });
        if (activeMenuId === menuId) {
            activeMenuId = menus[0].id;
            var menuData = await apiFetch('/api/menus/' + activeMenuId + '/');
            weekMenu = menuData;
        }
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        showToast('Меню удалено');
    } catch (e) {
        showError(e.message || 'Ошибка удаления меню');
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
    if (currentMenuOwnerId !== null) {
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
        currentMenuOwnerId = null;
        friendMenuRecipes = [];
        selectMenu(activeMenuId);
        return;
    }
    var friendId = parseInt(value, 10);
    currentMenuOwnerId = friendId;
    apiFetch('/api/friends/' + friendId + '/menu/').then(function (response) {
        weekMenu = response.menu || {};
        friendMenuRecipes = response.recipes || [];
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        updateSaveClearButtonsState();
    }).catch(function (e) {
        showError(e.message || 'Ошибка загрузки меню друга');
        currentMenuOwnerId = null;
        friendMenuRecipes = [];
    });
}

function updateSaveClearButtonsState() {
    var saveBtn = document.querySelector('.menu-main .card-actions .btn-primary');
    var clearBtn = document.getElementById('clear-menu-btn');
    var isReadOnly = currentMenuOwnerId !== null;
    if (saveBtn) saveBtn.style.display = isReadOnly ? 'none' : '';
    if (clearBtn) clearBtn.style.display = isReadOnly ? 'none' : '';
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
    return currentMenuOwnerId !== null ? friendMenuRecipes : recipes;
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
    var isReadOnly = currentMenuOwnerId !== null;
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
    if (currentMenuOwnerId !== null) {
        showError('Нельзя изменять меню друга');
        return;
    }
    if (!activeMenuId) {
        showError('Не выбрано меню');
        return;
    }
    updateWeekMenu();
    try {
        await apiFetch('/api/menus/' + activeMenuId + '/', { method: 'PUT', body: weekMenu });
        showToast('Меню сохранено');
    } catch (e) {
        showError(e.message || 'Ошибка сохранения меню');
    }
}

async function clearWeekMenu() {
    if (currentMenuOwnerId !== null) {
        showError('Нельзя изменять меню друга');
        return;
    }
    if (!activeMenuId) return;
    if (!confirm('Очистить все слоты этого меню?')) return;
    weekMenu = {};
    for (var d = 0; d < 7; d++) {
        for (var m = 0; m < 4; m++) {
            weekMenu[d + '-' + m] = null;
        }
    }
    try {
        await apiFetch('/api/menus/' + activeMenuId + '/', { method: 'PUT', body: weekMenu });
        generateWeekPlanner();
    } catch (e) {
        showError(e.message || 'Ошибка очистки меню');
    }
}
