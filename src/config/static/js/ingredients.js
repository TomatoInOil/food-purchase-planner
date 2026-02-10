/**
 * Ingredient CRUD, rendering, filtering, and import from external URLs.
 *
 * Import flow: the browser fetches the product page directly (bypassing
 * anti-bot protection as a real client). If CORS blocks the request,
 * a fallback textarea is shown for manual HTML paste.
 */

async function importIngredientFromUrl(event) {
    event.preventDefault();
    const form = event.target;
    const url = form.importUrl.value.trim();
    if (!url) return;

    const btn = document.getElementById('importBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Загрузка...';

    try {
        const html = await _fetchPageHtml(url);
        if (html) {
            await _submitImport(url, html, form);
        } else {
            _showHtmlFallback(url);
        }
    } catch (e) {
        showError(e.message || 'Ошибка импорта ингредиента');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function importIngredientFromHtml(event) {
    event.preventDefault();
    const url = document.getElementById('importFallbackUrl').value;
    const html = document.getElementById('importHtmlInput').value.trim();
    if (!html) {
        showError('Вставьте содержимое страницы');
        return;
    }

    const btn = document.getElementById('importHtmlBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Загрузка...';

    try {
        await _submitImport(url, html, document.getElementById('importIngredientForm'));
        _hideHtmlFallback();
    } catch (e) {
        showError(e.message || 'Ошибка импорта ингредиента');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

async function _fetchPageHtml(url) {
    try {
        const resp = await fetch(url, {
            mode: 'cors',
            credentials: 'omit',
        });
        if (resp.ok) {
            return await resp.text();
        }
    } catch (_ignored) { /* CORS or network error — use fallback */ }
    return null;
}

async function _submitImport(url, html, form) {
    await apiFetch('/api/ingredients/import-url/', {
        method: 'POST',
        body: { url, html }
    });
    ingredients = await apiFetch('/api/ingredients/');
    form.reset();
    renderIngredients();
    showToast('Ингредиент успешно импортирован!');
}

function _showHtmlFallback(url) {
    document.getElementById('importFallbackUrl').value = url;
    document.getElementById('importHtmlFallback').style.display = 'block';
    document.getElementById('importHtmlInput').value = '';
    document.getElementById('importHtmlInput').focus();
}

function _hideHtmlFallback() {
    document.getElementById('importHtmlFallback').style.display = 'none';
    document.getElementById('importHtmlInput').value = '';
}

function openImportUrl() {
    const url = document.getElementById('importFallbackUrl').value;
    if (url) window.open(url, '_blank');
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
