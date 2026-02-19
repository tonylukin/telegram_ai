def format_markdown(result: dict) -> str:
    total = result.get("total", {})
    items = result.get("items", [])
    conf = float(result.get("confidence", 0.0))
    assumptions = result.get("assumptions", [])

    lines = ["*Estimated nutrition* 🍽️", ""]
    if items:
        lines.append("*Items:*")
        for it in items:
            lines.append(
                f"- {it.get('name','Unknown')} (~{it.get('estimated_grams','?')}g): "
                f"{it.get('calories','?')} kcal | "
                f"P {it.get('protein_g','?')}g / F {it.get('fat_g','?')}g / C {it.get('carbs_g','?')}g"
            )
        lines.append("")

    lines.append(
        f"*Total:* {total.get('calories','?')} kcal | "
        f"P {total.get('protein_g','?')}g / F {total.get('fat_g','?')}g / C {total.get('carbs_g','?')}g"
    )
    lines.append(f"*Confidence:* {conf:.2f}")

    if assumptions:
        lines.append("")
        lines.append("*Assumptions:*")
        for a in assumptions[:6]:
            lines.append(f"- {a}")

    return "\n".join(lines)
