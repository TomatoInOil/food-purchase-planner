/**
 * Weekly menu planner: generation, update, save, clear.
 */

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

function generateWeekPlanner() {
    const days = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    const meals = ['Завтрак', 'Обед', 'Перекус', 'Ужин'];
    const container = document.getElementById('weekPlanner');

    container.innerHTML = days.map((day, dayIndex) => `
        <div class="day-card">
            <h3>${day}</h3>
            ${meals.map((meal, mealIndex) => {
                const key = `${dayIndex}-${mealIndex}`;
                const slotVal = weekMenu[key];
                return `
                <div class="meal-slot">
                    <h4>${meal}</h4>
                    <select data-day="${dayIndex}" data-meal="${mealIndex}" onchange="updateWeekMenu()">
                        <option value="">Не выбрано</option>
                        ${recipes.map(r => `
                            <option value="${r.id}" ${slotVal == r.id ? 'selected' : ''}>${r.name}</option>
                        `).join('')}
                    </select>
                </div>
            `}).join('')}
        </div>
    `).join('');
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
}

async function saveWeekMenu() {
    updateWeekMenu();
    try {
        await apiFetch('/api/menu/', { method: 'PUT', body: weekMenu });
        showError('Меню на неделю сохранено!');
    } catch (e) {
        showError(e.message || 'Ошибка сохранения меню');
    }
}

async function clearWeekMenu() {
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
