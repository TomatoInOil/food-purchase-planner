/**
 * Weekly menu planner: generation, update, save, clear.
 */

function populateMenuOwnerSelect() {
    const select = document.getElementById('menuOwnerSelect');
    if (!select) return;
    while (select.options.length > 1) {
        select.remove(1);
    }
    if (friends && friends.length > 0) {
        friends.forEach((f) => {
            const opt = document.createElement('option');
            opt.value = String(f.user_id);
            opt.textContent = f.username || '';
            select.appendChild(opt);
        });
    }
}

function updateShoppingOwnerLabel() {
    const label = document.getElementById('shoppingOwnerLabel');
    if (!label) return;
    if (currentMenuOwnerId === null) {
        label.textContent = '(для меня)';
    } else {
        const friend = friends.find((f) => f.user_id === currentMenuOwnerId);
        label.textContent = friend ? `(для ${friend.username})` : '(для друга)';
    }
}

function handleMenuOwnerChange() {
    const select = document.getElementById('menuOwnerSelect');
    if (!select) return;
    const value = select.value;
    if (!value) {
        currentMenuOwnerId = null;
        friendMenuRecipes = [];
        apiFetch('/api/menu/').then((menuData) => {
            weekMenu = menuData;
            generateWeekPlanner();
            updateShoppingOwnerLabel();
            updateSaveClearButtonsState();
        }).catch((e) => {
            showError(e.message || 'Ошибка загрузки меню');
        });
        return;
    }
    const friendId = parseInt(value, 10);
    currentMenuOwnerId = friendId;
    apiFetch(`/api/friends/${friendId}/menu/`).then((response) => {
        weekMenu = response.menu || {};
        friendMenuRecipes = response.recipes || [];
        generateWeekPlanner();
        updateShoppingOwnerLabel();
        updateSaveClearButtonsState();
    }).catch((e) => {
        showError(e.message || 'Ошибка загрузки меню друга');
        currentMenuOwnerId = null;
        friendMenuRecipes = [];
    });
}

function updateSaveClearButtonsState() {
    const saveBtn = document.querySelector('.card-actions .btn-primary');
    const clearBtn = document.getElementById('clear-menu-btn');
    const isReadOnly = currentMenuOwnerId !== null;
    if (saveBtn) {
        saveBtn.style.display = isReadOnly ? 'none' : '';
    }
    if (clearBtn) {
        clearBtn.style.display = isReadOnly ? 'none' : '';
    }
}

function setDefaultShoppingDates() {
    const start = document.getElementById('shoppingStartDate');
    const end = document.getElementById('shoppingEndDate');
    if (!start.value) {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + (today.getDay() === 0 ? -6 : 1));
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        start.value = monday.toISOString().slice(0, 10);
        end.value = sunday.toISOString().slice(0, 10);
    }
}

function getRecipeSource() {
    return currentMenuOwnerId !== null ? friendMenuRecipes : recipes;
}

function getDayNutritionTotals(dayIndex) {
    const source = getRecipeSource();
    let calories = 0, protein = 0, fat = 0, carbs = 0;
    for (let m = 0; m < 4; m++) {
        const recipeId = weekMenu[`${dayIndex}-${m}`];
        if (!recipeId) continue;
        const r = source.find(x => x.id === recipeId);
        if (r) {
            calories += r.total_calories || 0;
            protein += r.total_protein || 0;
            fat += r.total_fat || 0;
            carbs += r.total_carbs || 0;
        }
    }
    return { calories, protein, fat, carbs };
}

function formatDaySummary(totals) {
    const { calories, protein, fat, carbs } = totals;
    if (calories === 0 && protein === 0 && fat === 0 && carbs === 0) {
        return '—';
    }
    const parts = [`${Math.round(calories)} ккал`, `Б ${Math.round(protein)}`, `Ж ${Math.round(fat)}`, `У ${Math.round(carbs)}`];
    return parts.join(' · ');
}

function generateWeekPlanner() {
    const days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    const meals = ['Завтрак', 'Обед', 'Перекус', 'Ужин'];
    const container = document.getElementById('weekPlanner');
    const isReadOnly = currentMenuOwnerId !== null;
    const recipeSource = getRecipeSource();

    container.innerHTML = days.map((day, dayIndex) => {
        const totals = getDayNutritionTotals(dayIndex);
        return `
        <div class="day-card">
            <h3>${day}</h3>
            ${meals.map((meal, mealIndex) => {
                const key = `${dayIndex}-${mealIndex}`;
                const slotVal = weekMenu[key];
                const selectAttrs = isReadOnly ? 'disabled' : 'onchange="updateWeekMenu()"';
                return `
                <div class="meal-slot">
                    <h4>${meal}</h4>
                    <select data-day="${dayIndex}" data-meal="${mealIndex}" ${selectAttrs}>
                        <option value="">Не выбрано</option>
                        ${recipeSource.map(r => `
                            <option value="${r.id}" ${slotVal == r.id ? 'selected' : ''}>${r.name}</option>
                        `).join('')}
                    </select>
                </div>
            `}).join('')}
            <div class="day-summary" data-day-index="${dayIndex}">${formatDaySummary(totals)}</div>
        </div>
    `}).join('');
    updateSaveClearButtonsState();
}

function updateWeekMenu() {
    const selects = document.querySelectorAll('#weekPlanner select');
    weekMenu = {};
    selects.forEach(select => {
        if (select.value) {
            const key = `${select.dataset.day}-${select.dataset.meal}`;
            weekMenu[key] = parseInt(select.value);
        } else {
            weekMenu[`${select.dataset.day}-${select.dataset.meal}`] = null;
        }
    });
    document.querySelectorAll('#weekPlanner .day-summary').forEach(el => {
        const dayIndex = parseInt(el.dataset.dayIndex, 10);
        el.textContent = formatDaySummary(getDayNutritionTotals(dayIndex));
    });
}

async function saveWeekMenu() {
    if (currentMenuOwnerId !== null) {
        showError('Нельзя изменять меню друга');
        return;
    }
    updateWeekMenu();
    try {
        await apiFetch('/api/menu/', { method: 'PUT', body: weekMenu });
        showToast('Меню на неделю сохранено');
    } catch (e) {
        showError(e.message || 'Ошибка сохранения меню');
    }
}

async function clearWeekMenu() {
    if (currentMenuOwnerId !== null) {
        showError('Нельзя изменять меню друга');
        return;
    }
    if (!confirm('Очистить все меню?')) return;
    weekMenu = {};
    for (let d = 0; d < 7; d++) {
        for (let m = 0; m < 4; m++) {
            weekMenu[`${d}-${m}`] = null;
        }
    }
    try {
        await apiFetch('/api/menu/', { method: 'PUT', body: weekMenu });
        generateWeekPlanner();
    } catch (e) {
        showError(e.message || 'Ошибка очистки меню');
    }
}
