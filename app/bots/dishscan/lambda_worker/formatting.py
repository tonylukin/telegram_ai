def format_markdown(result: dict) -> str:
    total = result.get("total", {})
    items = result.get("items", [])
    conf = float(result.get("confidence", 0.0))
    assumptions = result.get("assumptions", [])

    lines = ["*Оценка питания* 🍽️", ""]
    if items:
        lines.append("*Блюда:*")
        for it in items:
            lines.append(
                f"- {it.get('name', 'Неизвестно')} (~{it.get('estimated_grams', '?')}г): "
                f"{it.get('calories', '?')} ккал | "
                f"Б {it.get('protein_g', '?')}г / Ж {it.get('fat_g', '?')}г / У {it.get('carbs_g', '?')}г"
            )
        lines.append("")

    lines.append(
        f"*Итого:* {total.get('calories', '?')} ккал | "
        f"Б {total.get('protein_g', '?')}г / Ж {total.get('fat_g', '?')}г / У {total.get('carbs_g', '?')}г"
    )
    lines.append(f"*Уверенность:* {conf:.2f}")

    if assumptions:
        lines.append("")
        lines.append("*Предположения:*")
        for a in assumptions[:6]:
            lines.append(f"- {a}")

    return "\n".join(lines)
