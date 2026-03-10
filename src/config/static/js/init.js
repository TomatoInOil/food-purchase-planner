/**
 * Application bootstrap: fetch initial data and render all sections.
 */

async function init() {
    try {
        const [recipesData, ingredientsData, menusData, categoriesData] = await Promise.all([
            apiFetch('/api/recipes/'),
            apiFetch('/api/ingredients/'),
            apiFetch('/api/menus/'),
            apiFetch('/api/recipe-categories/')
        ]);
        recipes = recipesData;
        ingredients = ingredientsData;
        menus = menusData;
        recipeCategories = categoriesData;

        if (menus.length === 0) {
            const newMenu = await apiFetch('/api/menus/', {
                method: 'POST',
                body: { name: 'Меню на неделю' }
            });
            menus = [newMenu];
        }
        activeMenuId = _findPrimaryOrFirstId(menus);

        const menuData = await apiFetch(`/api/menus/${activeMenuId}/`);
        weekMenu = menuData;

        renderRecipes();
        populateCategorySelects();
        renderIngredients();
        renderMenuSidebar();
        generateWeekPlanner();
        addIngredientRow();
        setDefaultShoppingDates();
        await loadFriendsTabData();
        if (typeof populateMenuOwnerSelect === 'function') {
            populateMenuOwnerSelect();
        }
        if (typeof updateShoppingOwnerLabel === 'function') {
            updateShoppingOwnerLabel();
        }
    } catch (e) {
        showError(e.message || 'Ошибка загрузки данных');
    }
}

init();
