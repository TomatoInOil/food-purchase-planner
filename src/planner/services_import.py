"""Service for importing ingredients from external store URLs (e.g. 5ka.ru)."""

import logging
import os
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

PYATEROCHKA_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?5ka\.ru/product/(?P<slug>[a-z0-9-]+?)--(?P<plu>\d+)/?",
    re.IGNORECASE,
)

PYATEROCHKA_URL_PATTERN_ALT = re.compile(
    r"https?://(?:www\.)?5ka\.ru/product/(?P<plu>\d+)/(?P<slug>[a-z0-9-]+?)/?",
    re.IGNORECASE,
)

SELENIUM_PAGE_LOAD_TIMEOUT = 15
SELENIUM_BODY_WAIT_TIMEOUT = 15


class IngredientImportError(Exception):
    """Raised when ingredient import fails."""


@dataclass
class ParsedIngredient:
    """Parsed ingredient data from an external source."""

    name: str
    calories: float
    protein: float
    fat: float
    carbs: float


def import_ingredient_from_url(url: str) -> ParsedIngredient:
    """Import ingredient data from a supported store URL.

    Currently supports 5ka.ru product pages.
    """
    validated_url, plu = _extract_plu_from_url(url)
    return _fetch_and_parse_product(validated_url, plu)


def _extract_plu_from_url(url: str) -> tuple[str, str]:
    """Extract PLU (product ID) and validated URL from a 5ka.ru product URL.

    Uses match() to anchor the pattern to the start of the string,
    preventing SSRF via URLs that embed a valid 5ka.ru substring
    after an attacker-controlled host.

    Returns a tuple of (validated_url, plu).
    """
    match = PYATEROCHKA_URL_PATTERN.match(url)
    if match:
        return match.group(0), match.group("plu")

    match = PYATEROCHKA_URL_PATTERN_ALT.match(url)
    if match:
        return match.group(0), match.group("plu")

    raise IngredientImportError(
        "Неподдерживаемый формат ссылки. "
        "Поддерживаются ссылки вида: https://5ka.ru/product/название--123456/"
    )


def _fetch_and_parse_product(url: str, plu: str) -> ParsedIngredient:
    """Fetch product page and extract ingredient data."""
    try:
        html = _fetch_page(url)
    except IngredientImportError:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        raise IngredientImportError(
            "Не удалось загрузить страницу. Проверьте ссылку и попробуйте снова."
        ) from exc

    return _parse_product_page(html, plu)


def _fetch_page(url: str) -> str:
    """Fetch page content using a local headless Chrome via Selenium.

    Launches a headless Chromium process to render the page,
    bypassing anti-bot protection that blocks plain HTTP requests.
    """
    driver = _create_webdriver()
    try:
        driver.set_page_load_timeout(SELENIUM_PAGE_LOAD_TIMEOUT)
        driver.get(url)
        WebDriverWait(driver, SELENIUM_BODY_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        return driver.page_source
    finally:
        driver.quit()


def _create_webdriver() -> webdriver.Chrome:
    """Create a local headless Chrome WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=ru-RU")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    chrome_bin = os.environ.get("CHROME_BIN")
    if chrome_bin:
        options.binary_location = chrome_bin

    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    service = (
        ChromeService(executable_path=chromedriver_path)
        if chromedriver_path
        else ChromeService()
    )

    return webdriver.Chrome(service=service, options=options)


def _parse_product_page(html: str, plu: str) -> ParsedIngredient:
    """Parse product page HTML and extract ingredient data.

    Tries multiple strategies:
    1. JSON-LD structured data
    2. Next.js __NEXT_DATA__ embedded JSON
    3. HTML meta tags and DOM parsing
    4. Embedded JavaScript state/data
    """
    soup = BeautifulSoup(html, "html.parser")

    result = _try_parse_json_ld(soup)
    if result:
        return result

    result = _try_parse_next_data(soup)
    if result:
        return result

    result = _try_parse_meta_tags(soup)
    if result:
        return result

    result = _try_parse_html_content(soup)
    if result:
        return result

    result = _try_parse_embedded_json(html, plu)
    if result:
        return result

    if _is_antibot_page(html):
        raise IngredientImportError(
            "Сайт 5ka.ru заблокировал запрос (антибот-защита). "
            "Попробуйте позже или проверьте настройки сервера."
        )

    raise IngredientImportError(
        "Не удалось извлечь данные о продукте со страницы. "
        "Возможно, формат страницы изменился."
    )


def _try_parse_json_ld(soup: BeautifulSoup) -> ParsedIngredient | None:
    """Try to extract product data from JSON-LD structured data."""
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "Product":
                return _extract_from_json_ld_product(item)
    return None


def _extract_from_json_ld_product(data: dict) -> ParsedIngredient | None:
    """Extract ingredient data from a JSON-LD Product object."""
    name = data.get("name", "").strip()
    if not name:
        return None

    nutrition = data.get("nutrition", {})
    if not nutrition:
        return None

    try:
        return ParsedIngredient(
            name=name,
            calories=float(nutrition.get("calories", 0)),
            protein=float(nutrition.get("proteinContent", 0)),
            fat=float(nutrition.get("fatContent", 0)),
            carbs=float(nutrition.get("carbohydrateContent", 0)),
        )
    except (ValueError, TypeError):
        return None


def _try_parse_next_data(soup: BeautifulSoup) -> ParsedIngredient | None:
    """Try to extract product data from Next.js __NEXT_DATA__ script."""
    import json

    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return None

    page_props = data.get("props", {}).get("pageProps", {})
    product = page_props.get("product") or page_props.get("data", {}).get("product")
    if not product:
        return None

    return _extract_from_product_dict(product)


def _extract_from_product_dict(product: dict) -> ParsedIngredient | None:
    """Extract ingredient data from a product dictionary (common API format)."""
    name = (
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or ""
    ).strip()
    if not name:
        return None

    nutrition = (
        product.get("nutrition")
        or product.get("nutritionFacts")
        or product.get("nutritionalValue")
        or {}
    )
    if isinstance(nutrition, dict):
        calories = _extract_float(nutrition, ["calories", "energy", "kcal", "energyKcal"])
        protein = _extract_float(nutrition, ["protein", "proteins", "proteinContent"])
        fat = _extract_float(nutrition, ["fat", "fats", "fatContent"])
        carbs = _extract_float(
            nutrition, ["carbs", "carbohydrates", "carbohydrateContent"]
        )
        if any(v > 0 for v in [calories, protein, fat, carbs]):
            return ParsedIngredient(
                name=name,
                calories=calories,
                protein=protein,
                fat=fat,
                carbs=carbs,
            )

    properties = product.get("properties") or product.get("characteristics") or []
    if isinstance(properties, list):
        return _extract_from_properties_list(name, properties)

    return None


def _extract_float(data: dict, keys: list[str]) -> float:
    """Extract a float value from dict trying multiple keys."""
    for key in keys:
        value = data.get(key)
        if value is not None:
            try:
                return float(str(value).replace(",", "."))
            except (ValueError, TypeError):
                continue
    return 0.0


def _extract_from_properties_list(
    name: str, properties: list[dict],
) -> ParsedIngredient | None:
    """Extract nutritional data from a list of product properties/characteristics."""
    nutrition_map = {}

    calorie_keys = {"калорийность", "энергетическая ценность", "ккал", "калории", "energy"}
    protein_keys = {"белки", "белок", "protein"}
    fat_keys = {"жиры", "жир", "fat"}
    carbs_keys = {"углеводы", "carbs", "carbohydrates"}

    for prop in properties:
        prop_name = (prop.get("name") or prop.get("key") or "").strip().lower()
        prop_value = prop.get("value") or prop.get("text") or ""

        value = _parse_numeric_value(str(prop_value))
        if value is None:
            continue

        if any(k in prop_name for k in calorie_keys):
            nutrition_map["calories"] = value
        elif any(k in prop_name for k in protein_keys):
            nutrition_map["protein"] = value
        elif any(k in prop_name for k in fat_keys):
            nutrition_map["fat"] = value
        elif any(k in prop_name for k in carbs_keys):
            nutrition_map["carbs"] = value

    if nutrition_map:
        return ParsedIngredient(
            name=name,
            calories=nutrition_map.get("calories", 0),
            protein=nutrition_map.get("protein", 0),
            fat=nutrition_map.get("fat", 0),
            carbs=nutrition_map.get("carbs", 0),
        )
    return None


def _try_parse_meta_tags(soup: BeautifulSoup) -> ParsedIngredient | None:
    """Try to extract product data from meta tags (og:title, etc.)."""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if not og_title:
        return None

    name = str(og_title.get("content") or "").strip()
    if not name:
        return None

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    if og_desc:
        desc = str(og_desc.get("content") or "")
        result = _parse_nutrition_from_text(name, desc)
        if result:
            return result

    return None


def _try_parse_html_content(soup: BeautifulSoup) -> ParsedIngredient | None:
    """Try to extract product data from rendered HTML content."""
    name = _extract_product_name(soup)
    if not name:
        return None

    nutrition_text = ""
    class_patterns = [
        re.compile(r"nutrit|nutrition|пищев|кбжу", re.I),
        re.compile(r"product.*detail|detail.*product", re.I),
    ]
    for pattern in class_patterns:
        section = soup.find(attrs={"class": pattern})
        if section:
            nutrition_text = section.get_text(separator=" ")
            break

    if not nutrition_text:
        nutrition_text = soup.get_text(separator=" ")

    return _parse_nutrition_from_text(name, nutrition_text)


def _extract_product_name(soup: BeautifulSoup) -> str | None:
    """Extract product name from HTML heading or title."""
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text and len(text) > 2:
            return text

    title = soup.find("title")
    if title:
        text = title.get_text(strip=True)
        text = re.sub(r"\s*[|–—-]\s*(Пятёрочка|5ka\.ru).*$", "", text, flags=re.I)
        if text and len(text) > 2:
            return text.strip()

    return None


def _parse_nutrition_from_text(name: str, text: str) -> ParsedIngredient | None:
    """Parse КБЖУ values from free-form text."""
    text = text.replace(",", ".")

    calories = _find_nutrition_value(
        text,
        [
            r"(?:калорийность|энергетическая\s+ценность|ккал)[:\s]*(\d+\.?\d*)",
            r"(\d+\.?\d*)\s*(?:ккал|kcal)",
        ],
    )
    protein = _find_nutrition_value(
        text, [r"(?:белки|белок)[:\s]*(\d+\.?\d*)", r"(\d+\.?\d*)\s*(?:г|g)\s*белк"]
    )
    fat = _find_nutrition_value(
        text, [r"(?:жиры|жир)[:\s]*(\d+\.?\d*)", r"(\d+\.?\d*)\s*(?:г|g)\s*жир"]
    )
    carbs = _find_nutrition_value(
        text,
        [r"(?:углеводы)[:\s]*(\d+\.?\d*)", r"(\d+\.?\d*)\s*(?:г|g)\s*углевод"],
    )

    if any(v is not None for v in [calories, protein, fat, carbs]):
        return ParsedIngredient(
            name=name,
            calories=calories or 0,
            protein=protein or 0,
            fat=fat or 0,
            carbs=carbs or 0,
        )
    return None


def _find_nutrition_value(text: str, patterns: list[str]) -> float | None:
    """Find a nutrition value in text using regex patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def _try_parse_embedded_json(html: str, plu: str) -> ParsedIngredient | None:
    """Try to find product JSON embedded in script tags or JS variables."""
    import json

    patterns = [
        re.compile(r'window\.__(?:INITIAL_STATE|PRELOADED_STATE|STORE__)__\s*=\s*({.+?})\s*;', re.DOTALL),
        re.compile(r'window\.__data\s*=\s*({.+?})\s*;', re.DOTALL),
        re.compile(r'"plu"\s*:\s*' + re.escape(plu) + r'[^}]*}[^}]*}', re.DOTALL),
    ]

    for pattern in patterns:
        match = pattern.search(html)
        if not match:
            continue

        try:
            text = match.group(1) if match.lastindex else match.group(0)
            data = json.loads(text)

            if isinstance(data, dict):
                product = _find_product_in_nested_dict(data, plu)
                if product:
                    return _extract_from_product_dict(product)
        except (json.JSONDecodeError, TypeError):
            continue

    return None


def _find_product_in_nested_dict(data: dict, plu: str) -> dict | None:
    """Recursively search for product data in a nested dictionary."""
    if str(data.get("plu")) == plu or str(data.get("id")) == plu:
        if data.get("name") or data.get("title"):
            return data

    for value in data.values():
        if isinstance(value, dict):
            result = _find_product_in_nested_dict(value, plu)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = _find_product_in_nested_dict(item, plu)
                    if result:
                        return result
    return None


def _parse_numeric_value(text: str) -> float | None:
    """Parse a numeric value from text, handling commas as decimal separators."""
    text = text.strip().replace(",", ".")
    match = re.search(r"(\d+\.?\d*)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _is_antibot_page(html: str) -> bool:
    """Check if the page is a ServicePipe or similar anti-bot challenge."""
    indicators = ["servicepipe.ru", "id_captcha_frame_div", "sp_rotated_captcha"]
    html_lower = html.lower()
    return any(indicator in html_lower for indicator in indicators)
