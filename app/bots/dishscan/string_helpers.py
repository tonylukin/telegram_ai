from decimal import Decimal

from date_helpers import format_consumed_time_for_user, DEFAULT_USER_TIMEZONE


def format_num(value) -> str:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        return format(value.normalize(), "f").rstrip("0").rstrip(".")

    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)

    return str(value)


def to_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    if isinstance(value, (int, float, str)):
        return Decimal(str(value))
    raise ValueError(f"Expected numeric value, got {type(value).__name__}: {value}")

def extract_meal_title(result: dict | None) -> str:
    if not isinstance(result, dict):
        return "Приём пищи"

    items = result.get("items")
    if isinstance(items, list) and items:
        names = []
        for item in items[:3]:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
        if names:
            if len(items) > 3:
                return ", ".join(names) + "…"
            return ", ".join(names)

    if result.get("name"):
        return str(result["name"])

    return "Приём пищи"


def build_history_text(items: list[dict], local_date: str) -> str:
    if not items:
        return f"📝 За дату *{local_date}* история приёмов пищи пуста."

    lines = [f"📝 *История за {local_date}*\n"]

    for idx, item in enumerate(items, start=1):
        result = item.get("result")
        title = extract_meal_title(result)
        calories = format_num(item.get("calories", 0))
        protein = format_num(item.get("protein_g", 0))
        fat = format_num(item.get("fat_g", 0))
        carbs = format_num(item.get("carbs_g", 0))
        consumed_at = str(item.get("consumed_at", ""))
        timezone_name = str(item.get("timezone", DEFAULT_USER_TIMEZONE))

        time_part = format_consumed_time_for_user(consumed_at, timezone_name)

        lines.append(
            f"{idx}. *{title}*\n"
            f"   🕒 {time_part}\n"
            f"   🔥 {calories} kcal | Б {protein} g | Ж {fat} g | У {carbs} g"
        )

    return "\n\n".join(lines)

def build_today_text(day_item: dict | None, local_date: str) -> str:
    if not day_item:
        return (
            f"📊 За сегодня ({local_date}) пока ничего не записано.\n"
            f"Отправьте фото еды, и я начну вести историю."
        )

    total_calories = day_item.get("total_calories", 0)
    total_protein = day_item.get("total_protein_g", 0)
    total_fat = day_item.get("total_fat_g", 0)
    total_carbs = day_item.get("total_carbs_g", 0)
    meals_count = day_item.get("meals_count", 0)

    return (
        f"📊 *Итого за сегодня* ({local_date})\n\n"
        f"Приёмов пищи: *{format_num(meals_count)}*\n"
        f"Калории: *{format_num(total_calories)} kcal*\n"
        f"Белки: *{format_num(total_protein)} g*\n"
        f"Жиры: *{format_num(total_fat)} g*\n"
        f"Углеводы: *{format_num(total_carbs)} g*"
    )
