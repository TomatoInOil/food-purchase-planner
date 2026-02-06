/**
 * Ingredient CRUD, rendering and filtering.
 */

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
        showError('Ингредиент успешно добавлен!');
    } catch (e) {
        showError(e.message || 'Ошибка добавления ингредиента');
    }
}

function renderIngredients() {
    const tbody = document.getElementById('ingredientTableBody');
    tbody.innerHTML = ingredients.map(ing => {
        const deleteBtn = ing.is_owner
            ? `<button type="button" class="btn-icon" onclick="deleteIngredient(${ing.id})" title="Удалить">❌</button>`
            : '';
        return `
        <tr>
            <td><strong>${ing.name}</strong></td>
            <td>${ing.calories}</td>
            <td>${ing.protein}</td>
            <td>${ing.fat}</td>
            <td>${ing.carbs}</td>
            <td>${deleteBtn}</td>
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
    } catch (e) {
        showError(e.message || 'Ошибка удаления ингредиента');
    }
}
