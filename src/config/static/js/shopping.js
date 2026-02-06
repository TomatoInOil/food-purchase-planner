/**
 * Shopping list generation and item toggling.
 */

async function generateShoppingList() {
    const startDate = document.getElementById('shoppingStartDate').value;
    const endDate = document.getElementById('shoppingEndDate').value;
    const peopleInput = document.getElementById('shoppingPeopleCount');
    let peopleCount = parseInt(peopleInput.value, 10);
    if (isNaN(peopleCount) || peopleCount < 1 || peopleCount > 20) {
        peopleCount = 2;
    }

    if (!startDate || !endDate) {
        showError('Выберите даты!');
        return;
    }

    const url = currentMenuOwnerId === null
        ? '/api/shopping-list/'
        : `/api/friends/${currentMenuOwnerId}/shopping-list/`;

    try {
        const items = await apiFetch(url, {
            method: 'POST',
            body: { start_date: startDate, end_date: endDate, people_count: peopleCount }
        });

        const container = document.getElementById('shoppingList');
        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>Нет ингредиентов для выбранного периода</p></div>';
            return;
        }

        container.innerHTML = items.map((item, index) => `
            <div class="shopping-item">
                <input type="checkbox" id="shop-${index}" onchange="toggleShoppingItem(this)">
                <label for="shop-${index}">
                    <strong>${item.name}</strong> - ${item.weight_grams}г
                </label>
            </div>
        `).join('');
    } catch (e) {
        showError(e.message || 'Ошибка формирования списка покупок');
    }
}

function toggleShoppingItem(checkbox) {
    checkbox.parentElement.classList.toggle('checked', checkbox.checked);
}
