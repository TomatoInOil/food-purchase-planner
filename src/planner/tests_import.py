"""Tests for ingredient import from external URLs (5ka.ru)."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from planner.models import Ingredient
from planner.services_import import (
    IngredientImportError,
    _extract_plu_from_url,
    _is_antibot_page,
    _parse_nutrition_from_text,
    _parse_product_page,
    import_ingredient_from_url,
)

User = get_user_model()


SAMPLE_HTML_WITH_JSON_LD = """
<!doctype html>
<html lang="ru">
<head>
    <title>Макароны Barilla Лазанья — Пятёрочка</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org/",
        "@type": "Product",
        "name": "Макароны Barilla Лазанья",
        "nutrition": {
            "@type": "NutritionInformation",
            "calories": "359",
            "proteinContent": "14",
            "fatContent": "2",
            "carbohydrateContent": "69.7"
        }
    }
    </script>
</head>
<body><div id="root"></div></body>
</html>
"""

SAMPLE_HTML_WITH_NEXT_DATA = """
<!doctype html>
<html lang="ru">
<head><title>Пятёрочка</title></head>
<body>
<div id="root"></div>
<script id="__NEXT_DATA__" type="application/json">
{
    "props": {
        "pageProps": {
            "product": {
                "name": "Молоко Простоквашино 3.2%",
                "plu": "2085981",
                "nutrition": {
                    "calories": 58,
                    "protein": 2.9,
                    "fat": 3.2,
                    "carbs": 4.7
                }
            }
        }
    }
}
</script>
</body>
</html>
"""

SAMPLE_HTML_WITH_PROPERTIES = """
<!doctype html>
<html lang="ru">
<head><title>Пятёрочка</title></head>
<body>
<div id="root"></div>
<script id="__NEXT_DATA__" type="application/json">
{
    "props": {
        "pageProps": {
            "product": {
                "name": "Сыр Российский",
                "plu": "1234567",
                "properties": [
                    {"name": "Энергетическая ценность", "value": "350 ккал"},
                    {"name": "Белки", "value": "23.2 г"},
                    {"name": "Жиры", "value": "29.0 г"},
                    {"name": "Углеводы", "value": "0 г"}
                ]
            }
        }
    }
}
</script>
</body>
</html>
"""

SAMPLE_HTML_WITH_TEXT_NUTRITION = """
<!doctype html>
<html lang="ru">
<head><title>Куриная грудка — Пятёрочка</title></head>
<body>
<h1>Куриная грудка филе</h1>
<div class="nutrition-info">
    <p>Калорийность: 113 ккал</p>
    <p>Белки: 23.6 г</p>
    <p>Жиры: 1.9 г</p>
    <p>Углеводы: 0.4 г</p>
</div>
</body>
</html>
"""

SAMPLE_HTML_ANTIBOT = """
<!DOCTYPE html>
<html>
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
  <noscript><meta http-equiv="refresh" content="0; url=/exhkqyad"></noscript>
</head>
<body>
  <div id="id_spinner" class="container"></div>
  <div id="id_captcha_frame_div" style="display: none;"></div>
  <script type="text/javascript" src="//servicepipe.ru/static/jsrsasign-all-min.js"></script>
</body>
</html>
"""

SAMPLE_HTML_WITH_EMBEDDED_STATE = """
<!doctype html>
<html lang="ru">
<head><title>Пятёрочка</title></head>
<body>
<div id="root"></div>
<script>
window.__INITIAL_STATE__ = {
    "product": {
        "currentProduct": {
            "plu": "3020941",
            "name": "Макароны Barilla Лазанья",
            "nutrition": {
                "calories": 359,
                "protein": 14,
                "fat": 2,
                "carbs": 69.7
            }
        }
    }
};
</script>
</body>
</html>
"""


class ExtractPluFromUrlTests(TestCase):
    """Test PLU extraction from various 5ka.ru URL formats."""

    def test_standard_url_format(self):
        url = "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"
        validated_url, plu = _extract_plu_from_url(url)
        self.assertEqual(plu, "3020941")
        self.assertTrue(validated_url.startswith("https://5ka.ru/"))

    def test_url_without_trailing_slash(self):
        url = "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941"
        validated_url, plu = _extract_plu_from_url(url)
        self.assertEqual(plu, "3020941")
        self.assertTrue(validated_url.startswith("https://5ka.ru/"))

    def test_url_with_www(self):
        url = "https://www.5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"
        validated_url, plu = _extract_plu_from_url(url)
        self.assertEqual(plu, "3020941")
        self.assertTrue(validated_url.startswith("https://www.5ka.ru/"))

    def test_http_url(self):
        url = "http://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"
        validated_url, plu = _extract_plu_from_url(url)
        self.assertEqual(plu, "3020941")
        self.assertTrue(validated_url.startswith("http://5ka.ru/"))

    def test_alt_url_format(self):
        url = "https://5ka.ru/product/2085981/moloko-prostokvashino/"
        validated_url, plu = _extract_plu_from_url(url)
        self.assertEqual(plu, "2085981")
        self.assertTrue(validated_url.startswith("https://5ka.ru/"))

    def test_invalid_url_raises_error(self):
        with self.assertRaises(IngredientImportError):
            _extract_plu_from_url("https://example.com/product/123")

    def test_empty_url_raises_error(self):
        with self.assertRaises(IngredientImportError):
            _extract_plu_from_url("")

    def test_ssrf_url_with_embedded_5ka_pattern_raises_error(self):
        with self.assertRaises(ImportError):
            _extract_plu_from_url(
                "http://169.254.169.254/meta-data?https://5ka.ru/product/x--1/"
            )

    def test_ssrf_url_with_5ka_in_path_raises_error(self):
        with self.assertRaises(ImportError):
            _extract_plu_from_url(
                "http://evil.com/https://5ka.ru/product/makarony--3020941/"
            )


class ParseProductPageTests(TestCase):
    """Test parsing of various HTML page formats."""

    def test_parse_json_ld(self):
        result = _parse_product_page(SAMPLE_HTML_WITH_JSON_LD, "3020941")
        self.assertEqual(result.name, "Макароны Barilla Лазанья")
        self.assertEqual(result.calories, 359)
        self.assertEqual(result.protein, 14)
        self.assertEqual(result.fat, 2)
        self.assertEqual(result.carbs, 69.7)

    def test_parse_next_data(self):
        result = _parse_product_page(SAMPLE_HTML_WITH_NEXT_DATA, "2085981")
        self.assertEqual(result.name, "Молоко Простоквашино 3.2%")
        self.assertEqual(result.calories, 58)
        self.assertEqual(result.protein, 2.9)
        self.assertEqual(result.fat, 3.2)
        self.assertEqual(result.carbs, 4.7)

    def test_parse_properties_list(self):
        result = _parse_product_page(SAMPLE_HTML_WITH_PROPERTIES, "1234567")
        self.assertEqual(result.name, "Сыр Российский")
        self.assertEqual(result.calories, 350)
        self.assertEqual(result.protein, 23.2)
        self.assertEqual(result.fat, 29.0)
        self.assertEqual(result.carbs, 0)

    def test_parse_html_content(self):
        result = _parse_product_page(SAMPLE_HTML_WITH_TEXT_NUTRITION, "0")
        self.assertEqual(result.name, "Куриная грудка филе")
        self.assertEqual(result.calories, 113)
        self.assertEqual(result.protein, 23.6)
        self.assertEqual(result.fat, 1.9)
        self.assertEqual(result.carbs, 0.4)

    def test_antibot_page_raises_error(self):
        with self.assertRaises(IngredientImportError) as ctx:
            _parse_product_page(SAMPLE_HTML_ANTIBOT, "3020941")
        self.assertIn("антибот", str(ctx.exception))

    def test_parse_embedded_state(self):
        result = _parse_product_page(SAMPLE_HTML_WITH_EMBEDDED_STATE, "3020941")
        self.assertEqual(result.name, "Макароны Barilla Лазанья")
        self.assertEqual(result.calories, 359)
        self.assertEqual(result.protein, 14)
        self.assertEqual(result.fat, 2)
        self.assertEqual(result.carbs, 69.7)

    def test_empty_html_raises_error(self):
        with self.assertRaises(IngredientImportError):
            _parse_product_page("<html><body></body></html>", "123")


class ParseNutritionFromTextTests(TestCase):
    """Test parsing КБЖУ from free-form text."""

    def test_standard_format(self):
        result = _parse_nutrition_from_text(
            "Test",
            "Калорийность: 250 ккал, Белки: 10 г, Жиры: 5 г, Углеводы: 30 г",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.calories, 250)
        self.assertEqual(result.protein, 10)
        self.assertEqual(result.fat, 5)
        self.assertEqual(result.carbs, 30)

    def test_decimal_values_with_comma(self):
        result = _parse_nutrition_from_text(
            "Test",
            "Калорийность: 113,5 ккал Белки: 23,6 Жиры: 1,9 Углеводы: 0,4",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.calories, 113.5)
        self.assertEqual(result.protein, 23.6)

    def test_no_nutrition_data_returns_none(self):
        result = _parse_nutrition_from_text("Test", "No nutrition here")
        self.assertIsNone(result)


class IsAntibotPageTests(TestCase):
    """Test anti-bot detection."""

    def test_servicepipe_detected(self):
        self.assertTrue(_is_antibot_page(SAMPLE_HTML_ANTIBOT))

    def test_normal_page_not_detected(self):
        self.assertFalse(_is_antibot_page(SAMPLE_HTML_WITH_JSON_LD))


class ImportIngredientFromUrlTests(TestCase):
    """Test the full import flow with mocked HTTP responses."""

    @patch("planner.services_import._fetch_page")
    def test_successful_import_json_ld(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_WITH_JSON_LD
        result = import_ingredient_from_url(
            "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"
        )
        self.assertEqual(result.name, "Макароны Barilla Лазанья")
        self.assertEqual(result.calories, 359)
        self.assertEqual(result.protein, 14)
        self.assertEqual(result.fat, 2)
        self.assertEqual(result.carbs, 69.7)

    @patch("planner.services_import._fetch_page")
    def test_successful_import_next_data(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_WITH_NEXT_DATA
        result = import_ingredient_from_url(
            "https://5ka.ru/product/moloko-prostokvashino--2085981/"
        )
        self.assertEqual(result.name, "Молоко Простоквашино 3.2%")
        self.assertEqual(result.calories, 58)

    @patch("planner.services_import._fetch_page")
    def test_antibot_raises_import_error(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_ANTIBOT
        with self.assertRaises(IngredientImportError):
            import_ingredient_from_url(
                "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"
            )

    def test_invalid_url_raises_import_error(self):
        with self.assertRaises(IngredientImportError):
            import_ingredient_from_url("https://example.com/product/123")


class IngredientImportApiTests(TestCase):
    """Test the ingredient import API endpoint."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass123", email="test@example.com"
        )
        self.client.force_login(self.user)

    @patch("planner.services_import._fetch_page")
    def test_import_creates_ingredient(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_WITH_JSON_LD
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps(
                {"url": "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "Макароны Barilla Лазанья")
        self.assertEqual(data["calories"], 359)
        self.assertEqual(data["protein"], 14)
        self.assertEqual(data["fat"], 2)
        self.assertEqual(data["carbs"], 69.7)
        self.assertTrue(data["is_owner"])
        self.assertTrue(
            Ingredient.objects.filter(
                user=self.user, name="Макароны Barilla Лазанья"
            ).exists()
        )

    def test_import_empty_url_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps({"url": ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_import_missing_url_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_import_invalid_url_returns_400(self):
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps({"url": "https://example.com/product/123"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    @patch("planner.services_import._fetch_page")
    def test_import_antibot_returns_400(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_ANTIBOT
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps(
                {"url": "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
        self.assertIn("антибот", response.json()["error"])

    @patch("planner.services_import._fetch_page")
    def test_import_duplicate_ingredient_returns_400(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_HTML_WITH_JSON_LD
        Ingredient.objects.create(
            user=self.user,
            name="Макароны Barilla Лазанья",
            calories=0,
        )
        response = self.client.post(
            "/api/ingredients/import-url/",
            data=json.dumps(
                {"url": "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_import_requires_authentication(self):
        anon_client = Client()
        response = anon_client.post(
            "/api/ingredients/import-url/",
            data=json.dumps(
                {"url": "https://5ka.ru/product/makarony-barilla-lazanya-500g--3020941/"}
            ),
            content_type="application/json",
        )
        self.assertIn(response.status_code, [401, 403])
