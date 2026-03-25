/**
 * Weekly menu planner: sidebar, multi-menu CRUD, generation, save, clear.
 * Supports own menus and shared menus (via MenuShare).
 */

// --- Helpers ---

function _findActiveOrFirstId(menuList) {
    var active = menuList.find(function (m) { return m.is_active === true; });
    return active ? active.id : menuList[0].id;
}

function _getMenuById(menuId) {
    return menus.find(function (m) { return m.id === menuId; });
}

function _isOwnMenu(menu) {
    return !menu || menu.owner === null || menu.owner === undefined;
}

function canEditCurrentMenu() {
    var menu = _getMenuById(activeMenuId);
    if (!menu) return false;
    if (_isOwnMenu(menu)) return true;
    return menu.permission === 'edit';
}

function _initEmptyWeekMenu() {
    weekMenu = {};
    for (var d = 0; d < 7; d++) {
        for (var m = 0; m < 4; m++) {
            weekMenu[d + '-' + m] = [];
        }
    }
}

// --- Sidebar rendering and interactions ---

function renderMenuSidebar() {
    var list = document.getElementById('menuSidebarList');
    var createBtn = document.getElementById('menuSidebarCreateBtn');
    if (!list) return;
    list.innerHTML = '';

    var ownMenus = menus.filter(function (m) { return _isOwnMenu(m); });
    var sharedMenus = menus.filter(function (m) { return !_isOwnMenu(m); });

    if (ownMenus.length > 0) {
        _renderMenuGroup(list, ownMenus, true, false);
    }
    if (createBtn) {
        list.appendChild(createBtn);
    }
    if (sharedMenus.length > 0) {
        if (ownMenus.length > 0 || createBtn) {
            _renderMenuGroupDivider(list);
        }
        _renderMenuGroup(list, sharedMenus, false, true, 'Доступные меню');
    }

    updateActiveMenuTitle();
    updateMenuSidebarVisibility();
}

function _renderMenuGroup(container, menuList, isOwn, renderHeading, headingText) {
    if (renderHeading) {
        var heading = document.createElement('h3');
        heading.className = 'menu-sidebar-group-heading';
        heading.textContent = headingText;
        container.appendChild(heading);
    }

    menuList.forEach(function (m) {
        var item = document.createElement('div');
        item.className = 'menu-sidebar-item' + (m.id === activeMenuId ? ' active' : '');
        item.dataset.menuId = m.id;

        var nameSpan = document.createElement('span');
        nameSpan.className = 'menu-sidebar-item-name';
        nameSpan.textContent = m.name;
        if (!isOwn && m.owner) {
            nameSpan.textContent += ' (' + m.owner.username + ')';
        }
        nameSpan.onclick = function () { selectMenu(m.id); };
        item.appendChild(nameSpan);

        var actions = document.createElement('span');
        actions.className = 'menu-sidebar-item-actions';

        var activeBtn = document.createElement('button');
        activeBtn.className = 'btn-icon btn-primary-star' + (m.is_active ? ' active' : '');
        activeBtn.title = m.is_active ? 'Активное меню' : 'Сделать активным';
        activeBtn.textContent = m.is_active ? '★' : '☆';
        activeBtn.onclick = function (e) { e.stopPropagation(); setActiveMenu(m.id); };
        actions.appendChild(activeBtn);

        if (isOwn) {
            var duplicateBtn = document.createElement('button');
            duplicateBtn.className = 'btn-icon';
            duplicateBtn.title = 'Дублировать';
            duplicateBtn.textContent = '\uD83D\uDCCB';
            duplicateBtn.onclick = function (e) { e.stopPropagation(); duplicateMenu(m.id); };
            actions.appendChild(duplicateBtn);

            var renameBtn = document.createElement('button');
            renameBtn.className = 'btn-icon';
            renameBtn.title = 'Переименовать';
            renameBtn.textContent = '\u270F\uFE0F';
            renameBtn.onclick = function (e) { e.stopPropagation(); renameMenu(m.id, m.name); };
            actions.appendChild(renameBtn);

            var deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn-icon';
            deleteBtn.title = 'Удалить';
            deleteBtn.textContent = '\uD83D\uDDD1\uFE0F';
            deleteBtn.onclick = function (e) { e.stopPropagation(); deleteMenu(m.id); };
            actions.appendChild(deleteBtn);

            var shareBtn = document.createElement('button');
            shareBtn.className = 'btn-icon';
            shareBtn.title = 'Поделиться';
            shareBtn.textContent = '\uD83D\uDD17';
            shareBtn.onclick = function (e) { e.stopPropagation(); openSharePanel(m.id); };
            actions.appendChild(shareBtn);
        }

        item.appendChild(actions);
        container.appendChild(item);
    });
}

function _renderMenuGroupDivider(container) {
    var divider = document.createElement('div');
    divider.className = 'menu-sidebar-group-divider';
    container.appendChild(divider);
}

function updateActiveMenuTitle() {
    var titleEl = document.getElementById('activeMenuTitle');
    if (!titleEl) return;
    var activeMenu = _getMenuById(activeMenuId);
    if (activeMenu) {
        var label = activeMenu.name;
        if (!_isOwnMenu(activeMenu) && activeMenu.owner) {
            label += ' (' + activeMenu.owner.username + ')';
        }
        titleEl.textContent = label;
    } else {
        titleEl.textContent = 'Планирование меню на неделю';
    }
}

function updateMenuSidebarVisibility() {
    var sidebar = document.getElementById('menuSidebar');
    var toggle = document.getElementById('menuSidebarToggle');
    var createBtn = document.getElementById('menuSidebarCreateBtn');
    if (!sidebar) return;

    sidebar.classList.toggle('hidden', false);
    if (toggle) toggle.classList.toggle('hidden', false);
    if (createBtn) createBtn.style.display = '';
}

function toggleMenuSidebar() {
    var sidebar = document.getElementById('menuSidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
}

async function selectMenu(menuId) {
    try {
        var results = await Promise.all([
            apiFetch('/api/menus/' + menuId + '/'),
            apiFetch('/api/menus/' + menuId + '/members/')
        ]);
        activeMenuId = menuId;
        weekMenu = results[0];
        menuMembers = results[1];
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
        var newMenu = await apiFetch('/api/menus/', {
            method: 'POST',
            body: { name: name }
        });
        menus.push(newMenu);
        activeMenuId = newMenu.id;
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
    var ownMenus = menus.filter(function (m) { return _isOwnMenu(m); });
    if (ownMenus.length <= 1) {
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

async function duplicateMenu(menuId) {
    try {
        var newMenu = await apiFetch('/api/menus/' + menuId + '/duplicate/', { method: 'POST' });
        menus.push(newMenu);
        activeMenuId = newMenu.id;
        var menuData = await apiFetch('/api/menus/' + newMenu.id + '/');
        weekMenu = menuData;
        renderMenuSidebar();
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        showToast('Меню продублировано');
        _closeSidebarIfOpen();
    } catch (e) {
        showError(e.message || 'Ошибка дублирования меню');
    }
}

async function setActiveMenu(menuId) {
    try {
        await apiFetch('/api/menus/' + menuId + '/set-active/', { method: 'POST' });
        menus.forEach(function (m) { m.is_active = (m.id === menuId); });
        renderMenuSidebar();
        showToast('Активное меню установлено');
    } catch (e) {
        showError(e.message || 'Ошибка установки активного меню');
    }
}

// --- Sharing panel ---

async function openSharePanel(menuId) {
    try {
        var shares = await apiFetch('/api/menus/' + menuId + '/shares/');
        _renderShareModal(menuId, shares);
    } catch (e) {
        showError(e.message || 'Ошибка загрузки шарингов');
    }
}

function _renderShareModal(menuId, shares) {
    var existingModal = document.getElementById('menuShareModal');
    if (existingModal) existingModal.remove();

    var modal = document.createElement('div');
    modal.id = 'menuShareModal';
    // Reuse the existing modal styles from `recipe_manager.css` (`.modal`).
    modal.className = 'modal active';

    var content = document.createElement('div');
    content.className = 'modal-content';

    var title = document.createElement('h3');
    title.textContent = 'Доступ к меню';
    content.appendChild(title);

    if (shares.length > 0) {
        var list = document.createElement('div');
        list.className = 'share-list';
        shares.forEach(function (s) {
            var row = document.createElement('div');
            row.className = 'share-row';
            row.innerHTML = '<span class="share-row-label">' + s.shared_with.username + ' (' + s.permission + ')</span>';

            var revokeBtn = document.createElement('button');
            revokeBtn.type = 'button';
            revokeBtn.className = 'btn-icon btn-remove-recipe';
            revokeBtn.title = 'Убрать доступ';
            revokeBtn.textContent = '\u2715';
            revokeBtn.onclick = function () { revokeShare(menuId, s.id); };
            row.appendChild(revokeBtn);
            list.appendChild(row);
        });
        content.appendChild(list);
    } else {
        var empty = document.createElement('p');
        empty.textContent = 'Меню ни с кем не разделено.';
        content.appendChild(empty);
    }

    var hr = document.createElement('hr');
    content.appendChild(hr);

    var addTitle = document.createElement('h4');
    addTitle.textContent = 'Поделиться с другом';
    content.appendChild(addTitle);

    var friendSelect = document.createElement('select');
    friendSelect.id = 'shareMenuFriendSelect';
    var defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = 'Выберите друга';
    friendSelect.appendChild(defaultOpt);
    if (typeof friends !== 'undefined' && friends.length > 0) {
        friends.forEach(function (f) {
            var existingShare = shares.find(function (s) { return s.shared_with.id === f.user_id; });
            if (!existingShare) {
                var opt = document.createElement('option');
                opt.value = f.user_id;
                opt.textContent = f.username;
                friendSelect.appendChild(opt);
            }
        });
    }
    content.appendChild(friendSelect);

    var permSelect = document.createElement('select');
    permSelect.id = 'shareMenuPermSelect';
    var readOpt = document.createElement('option');
    readOpt.value = 'read';
    readOpt.textContent = 'Чтение';
    var editOpt = document.createElement('option');
    editOpt.value = 'edit';
    editOpt.textContent = 'Редактирование';
    permSelect.appendChild(readOpt);
    permSelect.appendChild(editOpt);
    content.appendChild(permSelect);

    var addBtn = document.createElement('button');
    addBtn.className = 'btn btn-primary';
    addBtn.textContent = 'Поделиться';
    addBtn.onclick = function () { addShare(menuId); };
    content.appendChild(addBtn);

    var closeBtn = document.createElement('button');
    closeBtn.className = 'btn btn-secondary';
    closeBtn.textContent = 'Закрыть';
    closeBtn.style.marginLeft = '8px';
    closeBtn.onclick = function () { modal.remove(); };
    content.appendChild(closeBtn);

    modal.appendChild(content);
    modal.onclick = function (e) { if (e.target === modal) modal.remove(); };
    document.body.appendChild(modal);
}

async function addShare(menuId) {
    var friendSelect = document.getElementById('shareMenuFriendSelect');
    var permSelect = document.getElementById('shareMenuPermSelect');
    if (!friendSelect || !friendSelect.value) {
        showError('Выберите друга');
        return;
    }
    try {
        await apiFetch('/api/menus/' + menuId + '/shares/', {
            method: 'POST',
            body: { user_id: parseInt(friendSelect.value), permission: permSelect.value }
        });
        showToast('Доступ предоставлен');
        openSharePanel(menuId);
    } catch (e) {
        showError(e.message || 'Ошибка предоставления доступа');
    }
}

async function revokeShare(menuId, shareId) {
    try {
        await apiFetch('/api/menus/' + menuId + '/shares/' + shareId + '/', { method: 'DELETE' });
        showToast('Доступ отозван');
        openSharePanel(menuId);
    } catch (e) {
        showError(e.message || 'Ошибка отзыва доступа');
    }
}

// --- Shopping owner label ---

function updateShoppingOwnerLabel() {
    var label = document.getElementById('shoppingOwnerLabel');
    if (!label) return;
    var activeMenu = _getMenuById(activeMenuId);
    if (activeMenu) {
        var text = activeMenu.name;
        if (!_isOwnMenu(activeMenu) && activeMenu.owner) {
            text += ' — ' + activeMenu.owner.username;
        }
        label.textContent = '(' + text + ')';
    } else {
        label.textContent = '(моё меню)';
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

// --- Assignment helpers ---

var _ASSIGNMENT_COLORS = [
    '#2ecc71', '#3498db', '#e74c3c', '#f39c12', '#9b59b6',
    '#1abc9c', '#e67e22', '#2980b9', '#c0392b', '#8e44ad'
];

function _userColor(userId) {
    return _ASSIGNMENT_COLORS[userId % _ASSIGNMENT_COLORS.length];
}

function _userInitial(userId) {
    var member = menuMembers.find(function (m) { return m.id === userId; });
    return member ? member.username.charAt(0).toUpperCase() : '?';
}

function _buildAssignmentCircles(dayIndex, mealIndex, slotIndex, servings, assignments, isReadOnly) {
    if (menuMembers.length <= 1) return '';
    var html = '<span class="assignment-circles">';
    for (var i = 0; i < servings; i++) {
        var userId = assignments && assignments[i] ? assignments[i] : null;
        if (userId) {
            var color = _userColor(userId);
            var initial = _userInitial(userId);
            html += '<span class="assignment-circle assignment-circle-filled" ' +
                'style="background:' + color + '"' +
                (isReadOnly ? '' : ' onclick="openAssignmentDropdown(event,' + dayIndex + ',' + mealIndex + ',' + slotIndex + ',' + i + ')"') +
                ' title="' + (menuMembers.find(function(m){return m.id===userId;}) || {username:'?'}).username + '">' +
                initial + '</span>';
        } else {
            html += '<span class="assignment-circle assignment-circle-empty"' +
                (isReadOnly ? '' : ' onclick="openAssignmentDropdown(event,' + dayIndex + ',' + mealIndex + ',' + slotIndex + ',' + i + ')"') +
                '>?</span>';
        }
    }
    html += '</span>';
    return html;
}

function openAssignmentDropdown(event, day, meal, slot, servingIndex) {
    event.stopPropagation();
    var existing = document.getElementById('assignmentDropdown');
    if (existing) existing.remove();

    var dropdown = document.createElement('div');
    dropdown.id = 'assignmentDropdown';
    dropdown.className = 'assignment-dropdown';
    dropdown.style.left = event.clientX + 'px';
    dropdown.style.top = event.clientY + 'px';

    menuMembers.forEach(function (m) {
        var item = document.createElement('div');
        item.className = 'assignment-dropdown-item';
        item.innerHTML = '<span class="assignment-circle assignment-circle-filled" style="background:' +
            _userColor(m.id) + '">' + m.username.charAt(0).toUpperCase() + '</span> ' + m.username;
        item.onclick = function () { setAssignment(day, meal, slot, servingIndex, m.id); dropdown.remove(); };
        dropdown.appendChild(item);
    });

    var removeItem = document.createElement('div');
    removeItem.className = 'assignment-dropdown-item';
    removeItem.innerHTML = '<span class="assignment-circle assignment-circle-empty">?</span> Убрать';
    removeItem.onclick = function () { setAssignment(day, meal, slot, servingIndex, null); dropdown.remove(); };
    dropdown.appendChild(removeItem);

    document.body.appendChild(dropdown);
    document.addEventListener('click', function handler() {
        if (document.getElementById('assignmentDropdown')) {
            dropdown.remove();
        }
        document.removeEventListener('click', handler);
    }, { once: true });
}

function setAssignment(day, meal, slot, servingIndex, userId) {
    var key = day + '-' + meal;
    var entries = weekMenu[key] || [];
    var entry = entries[slot];
    if (!entry) return;
    if (typeof entry !== 'object') {
        entry = { recipe_id: entry, servings: 1, assignments: [] };
        entries[slot] = entry;
    }
    if (!entry.assignments) entry.assignments = [];
    while (entry.assignments.length < entry.servings) {
        entry.assignments.push(null);
    }
    entry.assignments[servingIndex] = userId;
    generateWeekPlanner();
}

function getDayNutritionByPerson(dayIndex) {
    var source = getRecipeSource();
    var byPerson = {};
    var unassigned = { calories: 0, protein: 0, fat: 0, carbs: 0 };
    var hasAnyAssignment = false;

    for (var m = 0; m < 4; m++) {
        var slotEntries = weekMenu[dayIndex + '-' + m] || [];
        slotEntries.forEach(function (entry) {
            if (typeof entry !== 'object') return;
            var recipeId = entry.recipe_id;
            var servings = entry.servings || 1;
            var assignments = entry.assignments || [];
            var r = source.find(function (x) { return x.id === recipeId; });
            if (!r) return;

            for (var i = 0; i < servings; i++) {
                var uid = assignments[i] || null;
                var cal = r.total_calories || 0;
                var pro = r.total_protein || 0;
                var fat = r.total_fat || 0;
                var carb = r.total_carbs || 0;
                if (uid) {
                    hasAnyAssignment = true;
                    if (!byPerson[uid]) {
                        var member = menuMembers.find(function(mm){return mm.id===uid;});
                        byPerson[uid] = { username: member ? member.username : '?', calories: 0, protein: 0, fat: 0, carbs: 0 };
                    }
                    byPerson[uid].calories += cal;
                    byPerson[uid].protein += pro;
                    byPerson[uid].fat += fat;
                    byPerson[uid].carbs += carb;
                } else {
                    unassigned.calories += cal;
                    unassigned.protein += pro;
                    unassigned.fat += fat;
                    unassigned.carbs += carb;
                }
            }
        });
    }
    return { byPerson: byPerson, unassigned: unassigned, hasAnyAssignment: hasAnyAssignment };
}

function formatDaySummaryByPerson(dayIndex) {
    if (menuMembers.length <= 1) {
        return formatDaySummary(getDayNutritionTotals(dayIndex));
    }
    var data = getDayNutritionByPerson(dayIndex);
    if (!data.hasAnyAssignment) {
        return formatDaySummary(getDayNutritionTotals(dayIndex));
    }
    var lines = [];
    Object.keys(data.byPerson).forEach(function (uid) {
        var p = data.byPerson[uid];
        var color = _userColor(parseInt(uid));
        lines.push('<div class="day-summary-person">' +
            '<span class="assignment-circle assignment-circle-filled" style="background:' + color + '">' +
            p.username.charAt(0).toUpperCase() + '</span> ' +
            Math.round(p.calories) + ' ккал \u00B7 Б ' + Math.round(p.protein) +
            ' \u00B7 Ж ' + Math.round(p.fat) + ' \u00B7 У ' + Math.round(p.carbs) + '</div>');
    });
    var u = data.unassigned;
    if (u.calories > 0 || u.protein > 0 || u.fat > 0 || u.carbs > 0) {
        lines.push('<div class="day-summary-person">' +
            '<span class="assignment-circle assignment-circle-empty">?</span> ' +
            Math.round(u.calories) + ' ккал \u00B7 Б ' + Math.round(u.protein) +
            ' \u00B7 Ж ' + Math.round(u.fat) + ' \u00B7 У ' + Math.round(u.carbs) + '</div>');
    }
    return lines.length > 0 ? lines.join('') : '\u2014';
}

function getDayNutritionTotals(dayIndex) {
    var source = getRecipeSource();
    var calories = 0, protein = 0, fat = 0, carbs = 0;
    for (var m = 0; m < 4; m++) {
        var slotEntries = weekMenu[dayIndex + '-' + m] || [];
        slotEntries.forEach(function (entry) {
            var recipeId = typeof entry === 'object' ? entry.recipe_id : entry;
            var servings = typeof entry === 'object' ? (entry.servings || 1) : 1;
            var r = source.find(function (x) { return x.id === recipeId; });
            if (r) {
                calories += (r.total_calories || 0) * servings;
                protein += (r.total_protein || 0) * servings;
                fat += (r.total_fat || 0) * servings;
                carbs += (r.total_carbs || 0) * servings;
            }
        });
    }
    return { calories: calories, protein: protein, fat: fat, carbs: carbs };
}

function formatDaySummary(totals) {
    if (totals.calories === 0 && totals.protein === 0 && totals.fat === 0 && totals.carbs === 0) {
        return '\u2014';
    }
    return Math.round(totals.calories) + ' ккал \u00B7 Б ' + Math.round(totals.protein) + ' \u00B7 Ж ' + Math.round(totals.fat) + ' \u00B7 У ' + Math.round(totals.carbs);
}

function _buildRecipeSelect(dayIndex, mealIndex, entry, isReadOnly, recipeSource, slotIndex) {
    var selectedId = typeof entry === 'object' && entry ? entry.recipe_id : entry;
    var servings = typeof entry === 'object' && entry ? (entry.servings || 1) : 1;
    var assignments = typeof entry === 'object' && entry ? (entry.assignments || []) : [];

    var selectAttrs = isReadOnly ? 'disabled' : 'onchange="updateWeekMenuAndRerender()"';
    var options = recipeSource.map(function (r) {
        return '<option value="' + r.id + '"' + (selectedId == r.id ? ' selected' : '') + '>' + r.name + '</option>';
    }).join('');

    var servingsInput = '';
    if (!isReadOnly) {
        servingsInput = '<input type="number" class="servings-input" data-day="' + dayIndex +
            '" data-meal="' + mealIndex + '" data-slot="' + slotIndex +
            '" min="1" max="99" value="' + servings +
            '" title="Порций" onchange="updateWeekMenuAndRerender()">';
    } else {
        servingsInput = '<span class="servings-display" title="Порций">\u00D7' + servings + '</span>';
    }

    var circlesHtml = selectedId ? _buildAssignmentCircles(dayIndex, mealIndex, slotIndex, servings, assignments, isReadOnly) : '';

    var removeBtn = '';
    if (!isReadOnly) {
        removeBtn = '<button type="button" class="btn-icon btn-remove-recipe" title="Убрать блюдо" onclick="removeRecipeFromSlot(' + dayIndex + ',' + mealIndex + ',' + slotIndex + ')">\u2715</button>';
    }
    return '<div class="meal-slot-recipe">' +
        '<select data-day="' + dayIndex + '" data-meal="' + mealIndex + '" ' + selectAttrs + '>' +
        '<option value="">Не выбрано</option>' + options + '</select>' +
        servingsInput + circlesHtml + removeBtn + '</div>';
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
            var entries = weekMenu[key] || [];
            var selects = '';
            if (entries.length === 0) {
                selects = _buildRecipeSelect(dayIndex, mealIndex, null, isReadOnly, recipeSource, 0);
            } else {
                selects = entries.map(function (entry, idx) {
                    return _buildRecipeSelect(dayIndex, mealIndex, entry, isReadOnly, recipeSource, idx);
                }).join('');
            }
            var addBtn = '';
            if (!isReadOnly) {
                addBtn = '<button type="button" class="btn-add-recipe" title="Добавить блюдо" onclick="addRecipeToSlot(' + dayIndex + ',' + mealIndex + ')">+ Блюдо</button>';
            }
            return '<div class="meal-slot" data-day="' + dayIndex + '" data-meal="' + mealIndex + '">' +
                '<h4>' + meal + '</h4>' +
                '<div class="meal-slot-recipes">' + selects + '</div>' +
                addBtn + '</div>';
        }).join('');
        var summaryHtml = formatDaySummaryByPerson(dayIndex);
        return '<div class="day-card"><h3>' + day + '</h3>' + mealSlots +
            '<div class="day-summary" data-day-index="' + dayIndex + '">' + summaryHtml + '</div></div>';
    }).join('');
    updateSaveClearButtonsState();
}

function updateWeekMenu() {
    var container = document.getElementById('weekPlanner');
    var oldMenu = {};
    Object.keys(weekMenu).forEach(function (k) { oldMenu[k] = weekMenu[k]; });

    weekMenu = {};
    for (var d = 0; d < 7; d++) {
        for (var m = 0; m < 4; m++) {
            weekMenu[d + '-' + m] = [];
        }
    }

    var mealSlots = container.querySelectorAll('.meal-slot');
    mealSlots.forEach(function (slotEl) {
        var day = slotEl.dataset.day;
        var meal = slotEl.dataset.meal;
        var key = day + '-' + meal;

        var recipeEls = slotEl.querySelectorAll('.meal-slot-recipe');
        recipeEls.forEach(function (recipeEl, idx) {
            var select = recipeEl.querySelector('select');
            var servingsInput = recipeEl.querySelector('.servings-input');
            if (select && select.value) {
                var recipeId = parseInt(select.value);
                var servings = servingsInput ? parseInt(servingsInput.value, 10) || 1 : 1;
                var oldEntries = oldMenu[key] || [];
                var oldEntry = oldEntries[idx];
                var assignments = [];
                if (oldEntry && typeof oldEntry === 'object' && oldEntry.recipe_id === recipeId && oldEntry.assignments) {
                    assignments = oldEntry.assignments.slice(0, servings);
                }
                weekMenu[key].push({ recipe_id: recipeId, servings: servings, assignments: assignments });
            }
        });
    });

    document.querySelectorAll('#weekPlanner .day-summary').forEach(function (el) {
        var dayIndex = parseInt(el.dataset.dayIndex, 10);
        el.innerHTML = formatDaySummaryByPerson(dayIndex);
    });
}

function updateWeekMenuAndRerender() {
    updateWeekMenu();
    generateWeekPlanner();
}

function addRecipeToSlot(dayIndex, mealIndex) {
    updateWeekMenu();
    var key = dayIndex + '-' + mealIndex;
    weekMenu[key].push({ recipe_id: null, servings: 1 });
    generateWeekPlanner();
}

function removeRecipeFromSlot(dayIndex, mealIndex, slotIndex) {
    updateWeekMenu();
    var key = dayIndex + '-' + mealIndex;
    weekMenu[key].splice(slotIndex, 1);
    generateWeekPlanner();
}

// --- Cook Today ---

function openCookToday() {
    if (!activeMenuId) {
        showError('Сначала выберите меню');
        return;
    }
    window.location.href = '/cook-today/?menu_id=' + activeMenuId;
}

// --- Save and clear ---

async function saveWeekMenu() {
    if (!canEditCurrentMenu()) {
        showError('Нет прав на редактирование этого меню');
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
    if (!canEditCurrentMenu()) {
        showError('Нет прав на редактирование этого меню');
        return;
    }
    if (!activeMenuId) return;
    if (!confirm('Очистить все слоты этого меню?')) return;
    _initEmptyWeekMenu();
    try {
        await apiFetch('/api/menus/' + activeMenuId + '/', { method: 'PUT', body: weekMenu });
        generateWeekPlanner();
    } catch (e) {
        showError(e.message || 'Ошибка очистки меню');
    }
}
