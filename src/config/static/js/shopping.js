/**
 * Shopping list generation and item toggling.
 */

async function generateShoppingList() {
    var startDate = document.getElementById('shoppingStartDate').value;
    var endDate = document.getElementById('shoppingEndDate').value;
    var peopleInput = document.getElementById('shoppingPeopleCount');
    var peopleCount = parseInt(peopleInput.value, 10);
    if (isNaN(peopleCount) || peopleCount < 1 || peopleCount > 20) {
        peopleCount = 2;
    }

    if (!startDate || !endDate) {
        showError('Выберите даты!');
        return;
    }

    var url;
    var body = { start_date: startDate, end_date: endDate, people_count: peopleCount };

    if (currentMenuOwnerId !== null) {
        url = '/api/friends/' + currentMenuOwnerId + '/shopping-list/';
        if (activeFriendMenuId) {
            body.menu_id = activeFriendMenuId;
        }
    } else {
        url = '/api/shopping-list/';
        if (activeMenuId) {
            body.menu_id = activeMenuId;
        }
    }

    try {
        var items = await apiFetch(url, { method: 'POST', body: body });

        var container = document.getElementById('shoppingList');
        if (items.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>Нет ингредиентов для выбранного периода</p></div>';
            return;
        }

        container.innerHTML = items.map(function (item, index) {
            return '<div class="shopping-item">' +
                '<input type="checkbox" id="shop-' + index + '" onchange="toggleShoppingItem(this)">' +
                '<label for="shop-' + index + '"><strong>' + item.name + '</strong> - ' + item.weight_grams + 'г</label>' +
                '</div>';
        }).join('');
    } catch (e) {
        showError(e.message || 'Ошибка формирования списка покупок');
    }
}

function toggleShoppingItem(checkbox) {
    checkbox.parentElement.classList.toggle('checked', checkbox.checked);
}
