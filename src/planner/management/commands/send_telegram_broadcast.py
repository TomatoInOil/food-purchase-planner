"""Management command to send a broadcast message to all linked Telegram users."""

import asyncio
import datetime
from html import escape

from django.conf import settings
from django.core.management.base import BaseCommand
from telegram.constants import ParseMode
from telegram.ext import AIORateLimiter, ApplicationBuilder

from planner.models import MenuSlot, Recipe, UserTelegramProfile
from planner.services import get_active_menu

MEAL_EMOJI = {
    0: "\U0001f305",  # Sunrise - Завтрак
    1: "\u2600\ufe0f",  # Sun - Обед
    2: "\U0001f375",  # Tea - Перекус
    3: "\U0001f319",  # Crescent moon - Ужин
}

MEAL_NAME = {
    0: "Завтрак",
    1: "Обед",
    2: "Перекус",
    3: "Ужин",
}


class Command(BaseCommand):
    help = "Send broadcast message to all linked Telegram users"

    def handle(self, *args, **options):
        profiles = list(UserTelegramProfile.objects.select_related("user").all())
        messages = self._prepare_messages(profiles)
        asyncio.run(self._broadcast(messages))

    def _prepare_messages(
        self, profiles: list[UserTelegramProfile]
    ) -> list[tuple[int, str]]:
        today_weekday = datetime.date.today().weekday()
        messages = []

        for profile in profiles:
            menu = get_active_menu(profile.user)
            if not menu:
                continue

            slots = MenuSlot.objects.filter(
                menu=menu, day_of_week=today_weekday
            ).select_related("recipe")

            meals_by_type: dict[int, list[tuple[Recipe, int]]] = {}
            for slot in slots:
                if slot.recipe:
                    meals_by_type.setdefault(slot.meal_type, []).append(
                        (slot.recipe, slot.servings)
                    )

            if not meals_by_type:
                continue

            text = self._format_message(meals_by_type)
            messages.append((profile.chat_id, text))

        return messages

    def _format_recipe(self, recipe: Recipe, servings: int) -> str:
        lines = [f"<b>{escape(recipe.name)}</b>"]
        if servings > 1:
            lines[0] += f" × {servings}"

        if recipe.description:
            lines.append(escape(recipe.description))

        recipe_ingredients = recipe.recipe_ingredients.select_related(
            "ingredient"
        ).all()
        if recipe_ingredients:
            lines.append("")
            lines.append("<i>Ингредиенты:</i>")
            for ri in recipe_ingredients:
                amount = ri.weight_grams * servings
                lines.append(f"• {escape(ri.ingredient.name)}: {amount}г")

        if recipe.instructions:
            lines.append("")
            lines.append("<i>Приготовление:</i>")
            lines.append(escape(recipe.instructions))

        return "\n".join(lines)

    def _format_message(
        self, meals_by_type: dict[int, list[tuple[Recipe, int]]]
    ) -> str:
        lines = ["\U0001f373 <b>Готовить сегодня</b>"]
        for meal_type in sorted(meals_by_type.keys()):
            emoji = MEAL_EMOJI[meal_type]
            name = MEAL_NAME[meal_type]
            lines.append("")
            lines.append(f"{emoji} <b>{name}</b>")
            for recipe, servings in meals_by_type[meal_type]:
                lines.append("")
                lines.append(self._format_recipe(recipe, servings))
        return "\n".join(lines)

    async def _broadcast(self, messages: list[tuple[int, str]]) -> None:
        application = (
            ApplicationBuilder()
            .token(settings.TELEGRAM_BOT_TOKEN)
            .rate_limiter(AIORateLimiter())
            .build()
        )
        sent = 0
        failed = 0
        async with application:
            for chat_id, text in messages:
                try:
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        parse_mode=ParseMode.HTML,
                    )
                    sent += 1
                except Exception as e:
                    self.stdout.write(f"Failed to send to {chat_id}: {e}")
                    failed += 1
        self.stdout.write(f"Broadcast complete: {sent} sent, {failed} failed.")
