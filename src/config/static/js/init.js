/**
 * Application bootstrap: fetch initial data and render all sections.
 */

async function init() {
    try {
        const [recipesData, ingredientsData, menuData] = await Promise.all([
            apiFetch('/api/recipes/'),
            apiFetch('/api/ingredients/'),
            apiFetch('/api/menu/')
        ]);
        recipes = recipesData;
        ingredients = ingredientsData;
        weekMenu = menuData;
        renderRecipes();
        renderIngredients();
        generateWeekPlanner();
        addIngredientRow();
        setDefaultShoppingDates();
        await loadFriendsTabData();
    } catch (e) {
        showError(e.message || 'Ошибка загрузки данных');
    }
}

init();
