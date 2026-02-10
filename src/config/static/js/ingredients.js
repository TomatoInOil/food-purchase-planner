/**
 * Ingredient CRUD, rendering, filtering, and import from external URLs.
 *
 * Import flow: the browser fetches the product page HTML directly
 * (bypassing anti-bot protection) and sends it to the backend for parsing.
 */

async function importIngredientFromUrl(event) {
    event.preventDefault();
    const form = event.target;
    const url = form.importUrl.value.trim();
    if (!url) return;

    const btn = document.getElementById('importBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Загрузка страницы...';

    try {
        const html = await fetchProductPageHtml(url);

        btn.textContent = '⏳ Импорт...';
        await apiFetch('/api/ingredients/import-url/', {
            method: 'POST',
            body: { url, html }
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

async function fetchProductPageHtml(url) {
    try {
        const response = await fetch(url, {
            mode: 'cors',
            credentials: 'omit',
        });
        if (!response.ok) {
            throw new Error('Сайт вернул ошибку: ' + response.status);
        }
        return await response.text();
    } catch (e) {
        if (e instanceof TypeError) {
            throw new Error(
                'Не удалось загрузить страницу. Сайт заблокировал запрос (CORS). '
                + 'Попробуйте другую ссылку или добавьте ингредиент вручную.'
            );
        }
        throw e;
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
        showToast('Ингредиент удалён');
    } catch (e) {
        showError(e.message || 'Ошибка удаления ингредиента');
    }
}
