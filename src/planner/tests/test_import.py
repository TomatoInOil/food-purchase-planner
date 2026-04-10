"""Tests for ingredient import from pasted page content (5ka.ru)."""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import Ingredient
from planner.services_import import (
    MAX_CONTENT_SIZE,
    IngredientImportError,
    parse_ingredient_from_text,
)

User = get_user_model()


SAMPLE_PAGE_CONTENT = """
Каталог
Овощи, фрукты, орехи
Овощи, зелень, грибы
Капуста Китайская
Капуста Китайская

Пищевая ценность на 100 г
1.5
белки

0.2
жиры

2.2
углеводы

13.0
ккал
"""

SAMPLE_PAGE_CONTENT_NUMBERED_BREADCRUMB = """
Новости
X5 Клуб
Кешбэк баллами
Подарочные сертификаты
Оценка товаров
Клуб тайных покупателей
Еще
Доставка от 0 ₽
от 55 мин
290
29,0 ₽
1
1. Главная
2. Сыр Galbani Моцарелла мягкий 45% БЗМЖ 125г
4,92

(3 551 оценка)
Сыр Galbani Моцарелла мягкий 45% БЗМЖ 125г
125 г
19999₽
13699₽
Пищевая ценность на 100 г
16.5
белки
17.0
жиры
3.0
углеводы
231.0
ккал
Описание
"""

SAMPLE_PAGE_CONTENT_COMMA_DECIMAL = """
Каталог
Молочные продукты
Молоко
Молоко Простоквашино 3.2%

Пищевая ценность на 100 г
2,9
белки

3,2
жиры

4,7
углеводы

58,0
ккал
"""


class ParseIngredientFromTextTests(TestCase):
    """Test parse_ingredient_from_text for pasted 5ka.ru page content."""

    def test_successful_parse_full_content(self):
        result = parse_ingredient_from_text(SAMPLE_PAGE_CONTENT)
        self.assertEqual(result.name, "Капуста Китайская")
        self.assertEqual(result.protein, 1.5)
        self.assertEqual(result.fat, 0.2)
        self.assertEqual(result.carbs, 2.2)
        self.assertEqual(result.calories, 13.0)

    def test_successful_parse_numbered_breadcrumb(self):
        result = parse_ingredient_from_text(SAMPLE_PAGE_CONTENT_NUMBERED_BREADCRUMB)
        self.assertEqual(result.name, "Сыр Galbani Моцарелла мягкий 45% БЗМЖ 125г")
        self.assertEqual(result.protein, 16.5)
        self.assertEqual(result.fat, 17.0)
        self.assertEqual(result.carbs, 3.0)
        self.assertEqual(result.calories, 231.0)

    def test_parse_decimal_comma(self):
        result = parse_ingredient_from_text(SAMPLE_PAGE_CONTENT_COMMA_DECIMAL)
        self.assertEqual(result.name, "Молоко Простоквашино 3.2%")
        self.assertEqual(result.protein, 2.9)
        self.assertEqual(result.fat, 3.2)
        self.assertEqual(result.carbs, 4.7)
        self.assertEqual(result.calories, 58.0)

    def test_empty_content_raises_error(self):
        with self.assertRaises(IngredientImportError) as ctx:
            parse_ingredient_from_text("")
        self.assertIn("Вставьте", str(ctx.exception))

    def test_whitespace_only_raises_error(self):
        with self.assertRaises(IngredientImportError):
            parse_ingredient_from_text("   \n\t  ")

    def test_missing_name_raises_error(self):
        content = """
Пищевая ценность на 100 г
1
белки
0
жиры
0
углеводы
10
ккал
"""
        with self.assertRaises(IngredientImportError) as ctx:
            parse_ingredient_from_text(content)
        self.assertIn("название", str(ctx.exception))

    def test_missing_nutrition_raises_error(self):
        content = """
Каталог
Продукты
Тестовый продукт

Нет блока КБЖУ здесь.
"""
        with self.assertRaises(IngredientImportError) as ctx:
            parse_ingredient_from_text(content)
        self.assertIn("пищевую ценность", str(ctx.exception).lower())

    def test_content_too_large_raises_error(self):
        content = "Каталог\nX\n\nПищевая ценность на 100 г\n1\nбелки\n0\nжиры\n0\nуглеводы\n0\nккал"
        large = content + "x" * (MAX_CONTENT_SIZE - len(content) + 1)
        with self.assertRaises(IngredientImportError) as ctx:
            parse_ingredient_from_text(large)
        self.assertIn("больш", str(ctx.exception))


class IngredientImportPageContentApiTests(TestCase):
    """Test POST /api/ingredients/import-page-content/."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com"
        )
        self.client.force_login(self.user)

    def test_import_creates_ingredient(self):
        response = self.client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({"content": SAMPLE_PAGE_CONTENT}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Капуста Китайская")
        self.assertEqual(data["calories"], 13.0)
        self.assertEqual(data["protein"], 1.5)
        self.assertEqual(data["fat"], 0.2)
        self.assertEqual(data["carbs"], 2.2)
        self.assertTrue(data["is_owner"])
        self.assertTrue(
            Ingredient.objects.filter(user=self.user, name="Капуста Китайская").exists()
        )

    def test_empty_content_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({"content": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_missing_content_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_too_large_content_returns_400(self):
        content = "Каталог\nX\n\nПищевая ценность на 100 г\n1\nбелки\n0\nжиры\n0\nуглеводы\n0\nккал"
        large = content + "x" * (MAX_CONTENT_SIZE - len(content) + 1)
        response = self.client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({"content": large}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_invalid_format_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({"content": "Random text without Каталог or nutrition"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_requires_authentication(self):
        anon_client = Client()
        response = anon_client.post(
            "/api/ingredients/import-page-content/",
            data=json.dumps({"content": SAMPLE_PAGE_CONTENT}),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [401, 403])
