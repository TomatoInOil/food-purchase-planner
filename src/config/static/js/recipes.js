/**
 * Recipe CRUD, rendering, filtering, ingredient rows, nutrition calculation, modal.
 */

function populateCategorySelects() {
    const filterSelect = document.getElementById('recipeCategoryFilter');
    const formSelect = document.getElementById('recipeCategorySelect');

    [filterSelect, formSelect].forEach(select => {
        if (!select) return;
        const prevValue = select.value;
        const firstOption = select.options[0];
        select.innerHTML = '';
        select.appendChild(firstOption);
        recipeCategories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = String(cat.id);
            opt.textContent = cat.name;
            select.appendChild(opt);
        });
        if (prevValue) select.value = prevValue;
    });
}

function showNewCategoryInput() {
    document.getElementById('newCategoryInput').style.display = 'block';
    document.getElementById('newCategoryName').focus();
}

function hideNewCategoryInput() {
    document.getElementById('newCategoryInput').style.display = 'none';
    document.getElementById('newCategoryName').value = '';
}

async function createCategory() {
    const nameInput = document.getElementById('newCategoryName');
    const name = nameInput.value.trim();
    if (!name) {
        showError('Введите название категории');
        return;
    }
    try {
        const cat = await apiFetch('/api/recipe-categories/', { method: 'POST', body: { name } });
        recipeCategories.push(cat);
        recipeCategories.sort((a, b) => a.name.localeCompare(b.name));
        populateCategorySelects();
        document.getElementById('recipeCategorySelect').value = String(cat.id);
        hideNewCategoryInput();
        showToast('Категория создана');
    } catch (e) {
        showError(e.message || 'Ошибка создания категории');
    }
}

function addIngredientRow() {
    const container = document.getElementById('ingredientsContainer');
    const row = document.createElement('div');
    row.className = 'ingredient-row';
    row.innerHTML = `
        <div class="form-group form-group--inline">
            <select class="ingredient-select" onchange="calculateNutrition()" required>
                <option value="">Выберите ингредиент</option>
                ${ingredients.map(ing => `<option value="${ing.id}">${ing.name}</option>`).join('')}
            </select>
        </div>
        <div class="form-group form-group--inline">
            <input type="number" class="ingredient-weight" placeholder="Вес (г)" min="1" onchange="calculateNutrition()" required>
        </div>
        <div class="form-group form-group--inline">
            <input type="text" class="ingredient-nutrition" readonly placeholder="КБЖУ">
        </div>
        <button type="button" class="btn btn-danger btn-small" onclick="removeIngredientRow(this)">✕</button>
    `;
    container.appendChild(row);
}

function removeIngredientRow(button) {
    button.parentElement.remove();
    calculateNutrition();
}

function refreshRecipeIngredientSelects() {
    const container = document.getElementById('ingredientsContainer');
    if (!container) return;

    const selects = container.querySelectorAll('.ingredient-select');
    selects.forEach(select => {
        const prevValue = select.value;

        while (select.options.length > 1) {
            select.remove(1);
        }

        if (ingredients && ingredients.length > 0) {
            ingredients.forEach(ing => {
                const opt = document.createElement('option');
                opt.value = String(ing.id);
                opt.textContent = ing.name || '';
                select.appendChild(opt);
            });
        }

        const validValues = ['', ...(ingredients || []).map(ing => String(ing.id))];
        if (prevValue && validValues.includes(prevValue)) {
            select.value = prevValue;
        } else {
            select.value = '';
        }
    });

    calculateNutrition();
}

function calculateNutrition() {
    const rows = document.querySelectorAll('.ingredient-row');
    let totalCalories = 0, totalProtein = 0, totalFat = 0, totalCarbs = 0;

    rows.forEach(row => {
        const select = row.querySelector('.ingredient-select');
        const weight = parseFloat(row.querySelector('.ingredient-weight').value) || 0;
        const nutritionField = row.querySelector('.ingredient-nutrition');

        if (select.value && weight > 0) {
            const ingredient = ingredients.find(ing => ing.id == select.value);
            if (ingredient) {
                const multiplier = weight / 100;
                const calories = (ingredient.calories * multiplier).toFixed(1);
                const protein = (ingredient.protein * multiplier).toFixed(1);
                const fat = (ingredient.fat * multiplier).toFixed(1);
                const carbs = (ingredient.carbs * multiplier).toFixed(1);

                nutritionField.value = `${calories}к ${protein}б ${fat}ж ${carbs}у`;

                totalCalories += parseFloat(calories);
                totalProtein += parseFloat(protein);
                totalFat += parseFloat(fat);
                totalCarbs += parseFloat(carbs);
            }
        } else {
            nutritionField.value = '';
        }
    });

    document.getElementById('totalCalories').textContent = totalCalories.toFixed(1);
    document.getElementById('totalProtein').textContent = totalProtein.toFixed(1);
    document.getElementById('totalFat').textContent = totalFat.toFixed(1);
    document.getElementById('totalCarbs').textContent = totalCarbs.toFixed(1);
}

async function saveRecipe(event) {
    event.preventDefault();
    const form = event.target;
    const rows = document.querySelectorAll('.ingredient-row');
    const recipeIngredients = [];
    const isEditing = Boolean(editingRecipeId);

    rows.forEach(row => {
        const ingredientId = row.querySelector('.ingredient-select').value;
        const weight = parseFloat(row.querySelector('.ingredient-weight').value);
        if (ingredientId && weight) {
            recipeIngredients.push({ ingredient_id: parseInt(ingredientId), weight_grams: Math.round(weight) });
        }
    });

    if (recipeIngredients.length === 0) {
        showError('Добавьте хотя бы один ингредиент!');
        return;
    }

    const categorySelect = document.getElementById('recipeCategorySelect');
    const categoryValue = categorySelect ? categorySelect.value : '';

    const body = {
        name: form.recipeName.value.trim(),
        description: form.recipeDescription.value,
        instructions: form.recipeInstructions.value,
        ingredients: recipeIngredients,
        category: categoryValue ? parseInt(categoryValue) : null
    };

    try {
        if (isEditing) {
            await apiFetch(`/api/recipes/${editingRecipeId}/`, { method: 'PUT', body });
        } else {
            await apiFetch('/api/recipes/', { method: 'POST', body });
        }
        showToast(isEditing ? 'Рецепт обновлён' : 'Рецепт создан');
        clearRecipeForm();
        editingRecipeId = null;
        recipes = await apiFetch('/api/recipes/');
        renderRecipes();
        populateCategorySelects();
        switchTab('recipes', document.querySelector('.tab-btn[data-tab="recipes"]'));
    } catch (e) {
        showError(e.message || 'Ошибка сохранения рецепта');
    }
}

function clearRecipeForm() {
    editingRecipeId = null;
    document.getElementById('recipeForm').reset();
    document.querySelector('#create-recipe .card-title').textContent = 'Создать новый рецепт';
    const categorySelect = document.getElementById('recipeCategorySelect');
    if (categorySelect) categorySelect.value = '';
    document.getElementById('ingredientsContainer').innerHTML = '';
    addIngredientRow();
    calculateNutrition();
}

function copyRecipe(recipeId) {
    const recipe = recipes.find(r => r.id === recipeId);
    if (!recipe) return;
    editingRecipeId = null;
    const form = document.getElementById('recipeForm');
    form.recipeName.value = `${recipe.name} (копия)`;
    form.recipeDescription.value = recipe.description || '';
    form.recipeInstructions.value = recipe.instructions || '';
    const categorySelect = document.getElementById('recipeCategorySelect');
    if (categorySelect) categorySelect.value = recipe.category ? String(recipe.category) : '';
    document.querySelector('#create-recipe .card-title').textContent = 'Создать новый рецепт';
    document.getElementById('ingredientsContainer').innerHTML = '';
    recipe.ingredients.forEach(ri => {
        addIngredientRow();
        const rows = document.querySelectorAll('.ingredient-row');
        const last = rows[rows.length - 1];
        last.querySelector('.ingredient-select').value = ri.ingredient_id;
        last.querySelector('.ingredient-weight').value = ri.weight_grams;
        calculateNutrition();
    });
    switchTab('create-recipe', document.querySelector('.tab-btn[data-tab="create-recipe"]'));
}

function loadRecipeForEdit(recipeId) {
    const recipe = recipes.find(r => r.id === recipeId);
    if (!recipe || !recipe.can_edit) return;
    editingRecipeId = recipe.id;
    const form = document.getElementById('recipeForm');
    form.recipeName.value = recipe.name;
    form.recipeDescription.value = recipe.description;
    form.recipeInstructions.value = recipe.instructions;
    const categorySelect = document.getElementById('recipeCategorySelect');
    if (categorySelect) categorySelect.value = recipe.category ? String(recipe.category) : '';
    document.querySelector('#create-recipe .card-title').textContent = 'Редактировать рецепт';
    document.getElementById('ingredientsContainer').innerHTML = '';
    recipe.ingredients.forEach(ri => {
        addIngredientRow();
        const rows = document.querySelectorAll('.ingredient-row');
        const last = rows[rows.length - 1];
        last.querySelector('.ingredient-select').value = ri.ingredient_id;
        last.querySelector('.ingredient-weight').value = ri.weight_grams;
        calculateNutrition();
    });
    switchTab('create-recipe', document.querySelector('.tab-btn[data-tab="create-recipe"]'));
}

function renderRecipes() {
    const container = document.getElementById('recipeList');
    if (recipes.length === 0) {
        container.innerHTML = `
            <div class="empty-state empty-state--full-width">
                <p>Пока нет рецептов. Создайте свой первый рецепт!</p>
            </div>
        `;
        return;
    }

    container.innerHTML = recipes.map(recipe => {
        const cals = (recipe.total_calories || 0).toFixed(0);
        const prot = (recipe.total_protein || 0).toFixed(0);
        const actions = recipe.can_edit
            ? `<button class="btn btn-secondary btn-small" onclick="event.stopPropagation(); loadRecipeForEdit(${recipe.id})">Редактировать</button>
               <button class="btn btn-danger btn-small" onclick="event.stopPropagation(); deleteRecipe(${recipe.id})">Удалить</button>`
            : '';
        const author = recipe.author_username ? `@${recipe.author_username}` : '';
        const categoryBadge = recipe.category_name
            ? `<span class="recipe-card__category">${recipe.category_name}</span>`
            : '';
        return `
        <div class="recipe-card" onclick="showRecipeDetails(${recipe.id})" data-category="${recipe.category || ''}">
            <h3>${recipe.name}</h3>
            ${categoryBadge}
            <p class="recipe-card__description">${recipe.description || 'Без описания'}</p>
            <div class="recipe-meta">
                <span>🔥 ${cals} ккал</span>
                <span>🥩 ${prot}г</span>
            </div>
            <div class="recipe-card__actions">${actions}</div>
            ${author ? `<p class="recipe-card__author">${author}</p>` : ''}
        </div>
    `}).join('');
}

function filterRecipes() {
    const search = document.getElementById('recipeSearch').value.toLowerCase();
    const categoryFilter = document.getElementById('recipeCategoryFilter');
    const selectedCategory = categoryFilter ? categoryFilter.value : '';
    const cards = document.querySelectorAll('.recipe-card');
    cards.forEach(card => {
        const name = card.querySelector('h3').textContent.toLowerCase();
        const cardCategory = card.getAttribute('data-category') || '';
        const matchesSearch = name.includes(search);
        const matchesCategory = !selectedCategory || cardCategory === selectedCategory;
        card.style.display = (matchesSearch && matchesCategory) ? 'block' : 'none';
    });
}

function showRecipeDetails(recipeId) {
    const recipe = recipes.find(r => r.id === recipeId);
    if (!recipe) return;

    const modal = document.getElementById('recipeModal');
    document.getElementById('modalRecipeName').textContent = recipe.name;

    const copyBtn = `<button class="btn btn-secondary" onclick="closeRecipeModal(); copyRecipe(${recipe.id})">Копировать</button>`;
    const editBtn = recipe.can_edit
        ? `<button class="btn btn-primary" onclick="closeRecipeModal(); loadRecipeForEdit(${recipe.id})">Редактировать</button>`
        : '';

    const categoryInfo = recipe.category_name
        ? `<p><strong>Категория:</strong> ${recipe.category_name}</p>`
        : '';

    document.getElementById('modalRecipeContent').innerHTML = `
        <div class="modal-section">
            ${categoryInfo}
            <p><strong>Описание:</strong> ${recipe.description || 'Нет описания'}</p>
        </div>
        <div class="modal-section portion-section">
            <div class="portion-control">
                <span class="portion-label">Порции:</span>
                <button class="btn-portion" onclick="updatePortions(${recipe.id}, -1)">−</button>
                <span id="portionCount" class="portion-value">1</span>
                <button class="btn-portion" onclick="updatePortions(${recipe.id}, 1)">+</button>
            </div>
        </div>
        <div class="modal-section">
            <h3>Ингредиенты:</h3>
            <ul id="modalIngredientsList">
                ${buildIngredientsList(recipe, 1)}
            </ul>
        </div>
        <div class="modal-section">
            <h3>Инструкция:</h3>
            <p>${recipe.instructions || 'Нет инструкции'}</p>
        </div>
        <div class="nutrition-info" id="modalNutritionInfo">
            ${buildNutritionCards(recipe, 1)}
        </div>
        <div class="modal-actions">${copyBtn}${editBtn}</div>
    `;

    modal.classList.add('active');
}

function buildIngredientsList(recipe, portions) {
    return recipe.ingredients.map(ri => {
        const scaledWeight = Math.round(ri.weight_grams * portions);
        return `<li>${ri.ingredient_name} — <strong>${scaledWeight}г</strong></li>`;
    }).join('');
}

function buildNutritionCards(recipe, portions) {
    const cal = ((recipe.total_calories || 0) * portions).toFixed(0);
    const prot = ((recipe.total_protein || 0) * portions).toFixed(1);
    const fat = ((recipe.total_fat || 0) * portions).toFixed(1);
    const carbs = ((recipe.total_carbs || 0) * portions).toFixed(1);

    return `
        <div class="nutrition-card">
            <h4>Калории</h4>
            <div class="value">${cal}</div>
            <small>ккал</small>
        </div>
        <div class="nutrition-card">
            <h4>Белки</h4>
            <div class="value">${prot}</div>
            <small>г</small>
        </div>
        <div class="nutrition-card">
            <h4>Жиры</h4>
            <div class="value">${fat}</div>
            <small>г</small>
        </div>
        <div class="nutrition-card">
            <h4>Углеводы</h4>
            <div class="value">${carbs}</div>
            <small>г</small>
        </div>
    `;
}

function updatePortions(recipeId, delta) {
    const recipe = recipes.find(r => r.id === recipeId);
    if (!recipe) return;

    const countEl = document.getElementById('portionCount');
    let current = parseInt(countEl.textContent, 10) || 1;
    current = Math.max(1, current + delta);
    countEl.textContent = current;

    document.getElementById('modalIngredientsList').innerHTML = buildIngredientsList(recipe, current);
    document.getElementById('modalNutritionInfo').innerHTML = buildNutritionCards(recipe, current);
}

function closeRecipeModal() {
    document.getElementById('recipeModal').classList.remove('active');
}

async function deleteRecipe(recipeId) {
    if (!confirm('Вы уверены, что хотите удалить этот рецепт?')) return;
    try {
        await apiFetch(`/api/recipes/${recipeId}/`, { method: 'DELETE' });
        recipes = recipes.filter(r => r.id !== recipeId);
        renderRecipes();
        closeRecipeModal();
    } catch (e) {
        showError(e.message || 'Ошибка удаления рецепта');
    }
}
