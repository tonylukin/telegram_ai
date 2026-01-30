from __future__ import annotations
from enum import Enum

class Polarity(Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


POSITIVE_REACTIONS = {
    "👍", "❤️", "❤", "🔥", "🥰", "👏", "😁", "🎉", "🤩", "🙏", "👌", "😍", "💯",
    "😄", "😆", "😊", "🙂", "✨", "⭐", "🌟", "💖", "💕", "💞", "💓", "💗",
    "🫶", "🙌", "✅",
    "❤️‍🔥", "⚡",  # common Telegram reaction emojis in some sets
}

NEGATIVE_REACTIONS = {
    "👎", "😢", "😭", "😡", "🤬", "🤮", "💩", "😠", "😞", "😒", "🙄",
    "⛔", "🚫", "❌",
}

NEUTRAL_REACTIONS = {
    "🤔", "🤯", "😱", "😮", "😲", "😐", "😑", "😶",
    "🤡", "🥱", "🥴", "🕊", "🐳",
}

def reaction_polarity(emoji: str) -> Polarity:
    if emoji in POSITIVE_REACTIONS:
        return Polarity.POSITIVE
    if emoji in NEGATIVE_REACTIONS:
        return Polarity.NEGATIVE
    # Unknown/custom reactions should not be forced into negative
    return Polarity.NEUTRAL
