/**
 * Cook Today page: fetches menu & recipes, renders today's meals with full details.
 */

(async function () {
    var DAY_NAMES = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];
    var MEAL_NAMES = ['Завтрак', 'Обед', 'Перекус', 'Ужин'];

    var params = new URLSearchParams(window.location.search);
    var menuId = params.get('menu_id');
    var friendId = params.get('friend_id');

    if (!menuId) {
        document.getElementById('cookTodayContent').innerHTML =
            '<div class="empty-state"><p>Не указано меню. Вернитесь на главную и попробуйте снова.</p></div>';
        return;
    }

    var jsDay = new Date().getDay();
    var todayIndex = jsDay === 0 ? 6 : jsDay - 1;

    var menuUrl = friendId
        ? '/api/friends/' + friendId + '/menus/' + menuId + '/'
        : '/api/menus/' + menuId + '/';
    var menuListUrl = friendId
        ? '/api/friends/' + friendId + '/menus/'
        : '/api/menus/';

    try {
        var results = await Promise.all([
            apiFetch(menuUrl),
            apiFetch('/api/recipes/'),
            apiFetch(menuListUrl)
        ]);
        var menuData = results[0];
        var recipesData = results[1];
        var menuListData = results[2];

        // Store recipes globally for portion updates
        window._cookTodayRecipes = {};
        recipesData.forEach(function (r) { window._cookTodayRecipes[r.id] = r; });
        var recipeMap = window._cookTodayRecipes;

        // Find menu name
        var menuList = menuListData.menus || menuListData;
        var currentMenu = menuList.find(function (m) { return m.id === parseInt(menuId); });
        var menuName = currentMenu ? currentMenu.name : 'Меню';

        document.getElementById('cookTodaySubtitle').textContent =
            menuName + ' · ' + DAY_NAMES[todayIndex];

        var html = '';
        var hasAnyRecipes = false;

        MEAL_NAMES.forEach(function (mealName, mealIndex) {
            var key = todayIndex + '-' + mealIndex;
            var recipeIds = menuData[key] || [];
            var mealRecipes = recipeIds
                .map(function (id) { return recipeMap[id]; })
                .filter(Boolean);

            html += '<div class="meal-section">';
            html += '<h2 class="meal-section-title">' + mealName + '</h2>';

            if (mealRecipes.length === 0) {
                html += '<p class="empty-meal">Нет запланированных блюд</p>';
            } else {
                hasAnyRecipes = true;
                mealRecipes.forEach(function (recipe) {
                    html += renderRecipeDetailCard(recipe);
                });
            }
            html += '</div>';
        });

        if (!hasAnyRecipes) {
            html = '<div class="empty-state"><p>На сегодня (' + DAY_NAMES[todayIndex] + ') нет запланированных блюд.</p></div>';
        } else {
            html += renderDayTotals(menuData, recipeMap, todayIndex);
        }

        document.getElementById('cookTodayContent').innerHTML = html;

    } catch (e) {
        document.getElementById('cookTodayContent').innerHTML =
            '<div class="empty-state"><p>Ошибка загрузки: ' + (e.message || 'Неизвестная ошибка') + '</p></div>';
    }
})();

function renderRecipeDetailCard(recipe) {
    var categoryBadge = recipe.category_name
        ? '<span class="recipe-card__category">' + recipe.category_name + '</span>'
        : '';

    var description = recipe.description
        ? '<p class="recipe-detail-description">' + recipe.description + '</p>'
        : '';

    var instructions = recipe.instructions
        ? '<div class="recipe-detail-section"><h4>Инструкция:</h4><p class="recipe-detail-instructions">' + recipe.instructions + '</p></div>'
        : '';

    return '<div class="recipe-detail-card" id="recipe-card-' + recipe.id + '">' +
        '<h3>' + recipe.name + '</h3>' +
        categoryBadge +
        description +
        '<div class="recipe-detail-section portion-section">' +
            '<div class="portion-control">' +
                '<span class="portion-label">Порции:</span>' +
                '<button class="btn-portion" onclick="updateCookTodayPortions(' + recipe.id + ', -1)">−</button>' +
                '<span class="portion-value" id="portion-' + recipe.id + '">1</span>' +
                '<button class="btn-portion" onclick="updateCookTodayPortions(' + recipe.id + ', 1)">+</button>' +
            '</div>' +
        '</div>' +
        '<div class="recipe-detail-section">' +
            '<h4>Ингредиенты:</h4>' +
            '<ul class="recipe-detail-ingredients" id="ingredients-' + recipe.id + '">' +
                buildCookTodayIngredients(recipe, 1) +
            '</ul>' +
        '</div>' +
        instructions +
        '<div class="nutrition-info" id="nutrition-' + recipe.id + '">' +
            buildCookTodayNutrition(recipe, 1) +
        '</div>' +
    '</div>';
}

function buildCookTodayIngredients(recipe, portions) {
    return recipe.ingredients.map(function (ri) {
        var scaledWeight = Math.round(ri.weight_grams * portions);
        return '<li>' + ri.ingredient_name + ' — <strong>' + scaledWeight + 'г</strong></li>';
    }).join('');
}

function buildCookTodayNutrition(recipe, portions) {
    var cal = ((recipe.total_calories || 0) * portions).toFixed(0);
    var prot = ((recipe.total_protein || 0) * portions).toFixed(1);
    var fat = ((recipe.total_fat || 0) * portions).toFixed(1);
    var carbs = ((recipe.total_carbs || 0) * portions).toFixed(1);

    return '<div class="nutrition-card"><h4>Калории</h4><div class="value">' + cal + '</div><small>ккал</small></div>' +
        '<div class="nutrition-card"><h4>Белки</h4><div class="value">' + prot + '</div><small>г</small></div>' +
        '<div class="nutrition-card"><h4>Жиры</h4><div class="value">' + fat + '</div><small>г</small></div>' +
        '<div class="nutrition-card"><h4>Углеводы</h4><div class="value">' + carbs + '</div><small>г</small></div>';
}

function updateCookTodayPortions(recipeId, delta) {
    var recipe = window._cookTodayRecipes[recipeId];
    if (!recipe) return;

    var countEl = document.getElementById('portion-' + recipeId);
    var current = parseInt(countEl.textContent, 10) || 1;
    current = Math.max(1, current + delta);
    countEl.textContent = current;

    document.getElementById('ingredients-' + recipeId).innerHTML = buildCookTodayIngredients(recipe, current);
    document.getElementById('nutrition-' + recipeId).innerHTML = buildCookTodayNutrition(recipe, current);
}

function renderDayTotals(menuData, recipeMap, dayIndex) {
    var totalCal = 0, totalProt = 0, totalFat = 0, totalCarbs = 0;
    for (var m = 0; m < 4; m++) {
        var ids = menuData[dayIndex + '-' + m] || [];
        ids.forEach(function (id) {
            var r = recipeMap[id];
            if (r) {
                totalCal += r.total_calories || 0;
                totalProt += r.total_protein || 0;
                totalFat += r.total_fat || 0;
                totalCarbs += r.total_carbs || 0;
            }
        });
    }
    if (totalCal === 0 && totalProt === 0 && totalFat === 0 && totalCarbs === 0) return '';
    return '<div class="day-totals">' +
        '<h2>Итого за день</h2>' +
        '<div class="nutrition-info">' +
            '<div class="nutrition-card"><h4>Калории</h4><div class="value">' + Math.round(totalCal) + '</div><small>ккал</small></div>' +
            '<div class="nutrition-card"><h4>Белки</h4><div class="value">' + totalProt.toFixed(1) + '</div><small>г</small></div>' +
            '<div class="nutrition-card"><h4>Жиры</h4><div class="value">' + totalFat.toFixed(1) + '</div><small>г</small></div>' +
            '<div class="nutrition-card"><h4>Углеводы</h4><div class="value">' + totalCarbs.toFixed(1) + '</div><small>г</small></div>' +
        '</div>' +
    '</div>';
}
