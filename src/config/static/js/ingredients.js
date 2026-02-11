/**
 * Ingredient CRUD, rendering, filtering, and import from pasted page content (5ka.ru).
 */

async function importIngredientFromPageContent(event) {
    event.preventDefault();
    const form = event.target;
    const content = form.pageContent.value.trim();
    if (!content) return;

    const btn = document.getElementById('importBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Импорт...';

    try {
        await apiFetch('/api/ingredients/import-page-content/', {
            method: 'POST',
            body: { content }
        });
        ingredients = await apiFetch('/api/ingredients/');
        form.reset();
        renderIngredients();
        showToast('Ингредиент успешно импортирован!');
    } catch (e) {
        showError(e.message || 'Ошибка импорта ингредиента');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function saveIngredient(event) {
    event.preventDefault();
    const form = event.target;
    const body = {
        name: form.ingredientName.value.trim(),
        calories: parseFloat(form.calories.value),
        protein: parseFloat(form.protein.value),
        fat: parseFloat(form.fat.value),
        carbs: parseFloat(form.carbs.value)
    };
    try {
        await apiFetch('/api/ingredients/', { method: 'POST', body });
        ingredients = await apiFetch('/api/ingredients/');
        form.reset();
        renderIngredients();
        showToast('Ингредиент успешно добавлен!');
    } catch (e) {
        showError(e.message || 'Ошибка добавления ингредиента');
    }
}

function renderIngredients() {
    const tbody = document.getElementById('ingredientTableBody');
    tbody.innerHTML = ingredients.map(ing => {
        const editBtn = ing.is_owner
            ? `<button type="button" class="btn-icon" onclick="openEditIngredientModal(${ing.id})" title="Редактировать">✏️</button>`
            : '';
        const deleteBtn = ing.is_owner
            ? `<button type="button" class="btn-icon" onclick="deleteIngredient(${ing.id})" title="Удалить">❌</button>`
            : '';
        const actions = editBtn || deleteBtn ? `${editBtn}${deleteBtn}` : '';
        return `
        <tr>
            <td><strong>${ing.name}</strong></td>
            <td>${ing.calories}</td>
            <td>${ing.protein}</td>
            <td>${ing.fat}</td>
            <td>${ing.carbs}</td>
            <td>${actions}</td>
        </tr>
    `}).join('');
}

function filterIngredients() {
    const search = document.getElementById('ingredientSearch').value.toLowerCase();
    const rows = document.querySelectorAll('#ingredientTableBody tr');
    rows.forEach(row => {
        const name = row.querySelector('td').textContent.toLowerCase();
        row.style.display = name.includes(search) ? '' : 'none';
    });
}

async function deleteIngredient(ingredientId) {
    if (!confirm('Вы уверены, что хотите удалить этот ингредиент?')) return;
    try {
        await apiFetch(`/api/ingredients/${ingredientId}/`, { method: 'DELETE' });
        ingredients = await apiFetch('/api/ingredients/');
        renderIngredients();
        showToast('Ингредиент удалён');
    } catch (e) {
        showError(e.message || 'Ошибка удаления ингредиента');
    }
}

function openEditIngredientModal(ingredientId) {
    const ingredient = ingredients.find(ing => ing.id === ingredientId);
    if (!ingredient) return;

    editingIngredientId = ingredientId;
    document.getElementById('editIngredientName').value = ingredient.name;
    document.getElementById('editIngredientCalories').value = ingredient.calories;
    document.getElementById('editIngredientProtein').value = ingredient.protein;
    document.getElementById('editIngredientFat').value = ingredient.fat;
    document.getElementById('editIngredientCarbs').value = ingredient.carbs;
    document.getElementById('editIngredientModal').classList.add('active');
}

function closeEditIngredientModal() {
    document.getElementById('editIngredientModal').classList.remove('active');
    editingIngredientId = null;
    document.getElementById('editIngredientForm').reset();
}

async function saveEditedIngredient(event) {
    event.preventDefault();
    if (!editingIngredientId) return;

    const form = event.target;
    const body = {
        name: form.ingredientName.value.trim(),
        calories: parseFloat(form.calories.value),
        protein: parseFloat(form.protein.value),
        fat: parseFloat(form.fat.value),
        carbs: parseFloat(form.carbs.value)
    };

    try {
        await apiFetch(`/api/ingredients/${editingIngredientId}/`, {
            method: 'PATCH',
            body
        });
        ingredients = await apiFetch('/api/ingredients/');
        renderIngredients();
        closeEditIngredientModal();
        showToast('Ингредиент обновлён');
    } catch (e) {
        showError(e.message || 'Ошибка обновления ингредиента');
    }
}
