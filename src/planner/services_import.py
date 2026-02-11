"""Service for importing ingredients from pasted page content (e.g. 5ka.ru)."""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MAX_CONTENT_SIZE = 100 * 1024


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


def parse_ingredient_from_text(content: str) -> ParsedIngredient:
    """Parse ingredient name and КБЖУ from pasted 5ka.ru page text.

    Expects content copied from product page (Ctrl+A): breadcrumb with "Каталог"
    and nutrition block "Пищевая ценность на 100 г" with values on lines before
    keywords белки, жиры, углеводы, ккал.
    """
    if not content or not content.strip():
        raise IngredientImportError(
            "Вставьте скопированное содержимое страницы продукта."
        )
    if len(content) > MAX_CONTENT_SIZE:
        raise IngredientImportError("Содержимое слишком большое.")

    name = _extract_name_from_breadcrumb(content)
    if not name:
        raise IngredientImportError(
            "Не удалось найти название продукта. "
            "Убедитесь, что скопировали всю страницу с 5ka.ru (Ctrl+A)."
        )

    nutrition = _extract_nutrition_from_text(content)
    if not nutrition:
        raise IngredientImportError(
            "Не удалось найти пищевую ценность (КБЖУ) на 100 г. "
            "Проверьте, что на странице есть блок «Пищевая ценность на 100 г»."
        )

    return ParsedIngredient(
        name=name,
        calories=nutrition["calories"],
        protein=nutrition["protein"],
        fat=nutrition["fat"],
        carbs=nutrition["carbs"],
    )


def _extract_name_from_breadcrumb(content: str) -> str | None:
    """Extract product name from breadcrumb: last element before first repeat or rating."""
    lines = [line.strip() for line in content.splitlines()]
    try:
        idx = lines.index("Каталог")
    except ValueError:
        return None
    seen = set()
    name = None
    rating_pattern = re.compile(r"^\d+[,.]\d+$")
    stop_phrases = ("Пищевая ценность на 100 г",)
    for i in range(idx + 1, len(lines)):
        line = lines[i]
        if not line:
            continue
        if line in seen or rating_pattern.match(line):
            break
        if any(phrase in line for phrase in stop_phrases):
            break
        seen.add(line)
        name = line
    return name


def _extract_nutrition_from_text(content: str) -> dict[str, float] | None:
    """Extract КБЖУ from 'Пищевая ценность на 100 г' block: value on line before keyword."""
    if "Пищевая ценность на 100 г" not in content:
        return None
    lines = content.splitlines()
    keywords = ["белки", "жиры", "углеводы", "ккал"]
    result = {}
    for kw in keywords:
        value = _find_value_before_keyword(lines, kw)
        if value is None:
            return None
        key = (
            "calories"
            if kw == "ккал"
            else {"белки": "protein", "жиры": "fat", "углеводы": "carbs"}[kw]
        )
        result[key] = value
    return result


def _find_value_before_keyword(lines: list[str], keyword: str) -> float | None:
    """Find keyword in lines; return numeric value from the previous non-empty line."""
    for i, line in enumerate(lines):
        if keyword not in line.lower():
            continue
        for j in range(i - 1, -1, -1):
            prev = lines[j].strip()
            if not prev:
                continue
            num = _parse_numeric_value(prev)
            if num is not None:
                return num
        return None
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
