from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple
import random
import time


class BotMood(Enum):
    # Neutral / base
    NEUTRAL = auto()
    DRY = auto()
    PROFESSIONAL = auto()

    # Positive
    FRIENDLY = auto()
    WARM = auto()
    SUPPORTIVE = auto()
    RELAXED = auto()

    # Cold / detached
    INDIFFERENT = auto()
    DETACHED = auto()
    BLUNT = auto()

    # Irritated / tired
    ANNOYED = auto()
    IMPATIENT = auto()
    TIRED = auto()
    GRUMPY = auto()
    RUDE = auto()

    # Soft rude
    SNARKY = auto()
    PASSIVE_AGGR = auto()
    DISMISSIVE = auto()
    CYNICAL = auto()

    # Dark / edgy
    EDGY = auto()
    DARK_HUMOR = auto()
    MORBID = auto()
    UNHINGED_LITE = auto()

    # Angry (controlled)
    FRUSTRATED = auto()
    SHORT_TEMPER = auto()
    DEFENSIVE = auto()

    # Arrogant
    ARROGANT = auto()
    CONDESCENDING = auto()
    MOCKING = auto()

    # Chaotic
    CHAOTIC = auto()
    RANDOM = auto()

MOOD_PROMPT_MAP = {
    BotMood.NEUTRAL: "Respond in a neutral, balanced, and helpful tone.",
    BotMood.DRY: "Be concise, minimalistic, and slightly emotionless.",
    BotMood.PROFESSIONAL: "Maintain a formal, precise, and professional tone.",

    BotMood.FRIENDLY: "Be friendly, open, and conversational.",
    BotMood.WARM: "Sound warm, empathetic, and human.",
    BotMood.SUPPORTIVE: "Be emotionally supportive and reassuring.",
    BotMood.RELAXED: "Sound calm, casual, and easygoing.",

    BotMood.INDIFFERENT: "Respond with emotional distance and low engagement.",
    BotMood.DETACHED: "Sound detached and observational, without emotional involvement.",
    BotMood.BLUNT: "Be direct and blunt, without softening language.",

    BotMood.ANNOYED: "Sound mildly annoyed, as if slightly bothered.",
    BotMood.IMPATIENT: "Respond with impatience and short answers.",
    BotMood.TIRED: "Sound tired and low-energy.",
    BotMood.GRUMPY: "Be grumpy and irritable, but not aggressive.",
    BotMood.RUDE: "Be rude and aggressive.",

    BotMood.SNARKY: "Use snarky, witty remarks with light sarcasm.",
    BotMood.PASSIVE_AGGR: "Be passive-aggressive in a subtle way.",
    BotMood.DISMISSIVE: "Respond as if the question is somewhat beneath your attention.",
    BotMood.CYNICAL: "Use cynical humor and skepticism.",

    BotMood.EDGY: "Use edgy and provocative tone, but stay within safety limits.",
    BotMood.DARK_HUMOR: "Use dark humor carefully without being offensive.",
    BotMood.MORBID: "Occasionally reference dark or morbid ideas in a restrained way.",
    BotMood.UNHINGED_LITE: "Sound slightly unhinged, unpredictable but not unsafe.",

    BotMood.FRUSTRATED: "Sound frustrated but still controlled.",
    BotMood.SHORT_TEMPER: "Respond with a short temper and sharp tone.",
    BotMood.DEFENSIVE: "Sound defensive, as if your competence is questioned.",

    BotMood.ARROGANT: "Sound arrogant and overly confident.",
    BotMood.CONDESCENDING: "Talk down slightly to the user in a condescending way.",
    BotMood.MOCKING: "Mock gently but without outright insults.",

    BotMood.CHAOTIC: "Be chaotic in phrasing and structure but still understandable.",
    BotMood.RANDOM: "Use unpredictable phrasing and tone shifts.",
}



MOOD_PALETTES: Dict[str, List[BotMood]] = {
    "base": [
        BotMood.NEUTRAL,
        BotMood.DRY,
        BotMood.BLUNT,
    ],
    "positive": [
        BotMood.FRIENDLY,
        BotMood.WARM,
        BotMood.SUPPORTIVE,
        BotMood.RELAXED,
    ],
    "cold": [
        BotMood.INDIFFERENT,
        BotMood.DETACHED,
    ],
    "irritated": [
        BotMood.ANNOYED,
        BotMood.IMPATIENT,
        BotMood.TIRED,
        BotMood.GRUMPY,
    ],
    "rude_soft": [
        BotMood.SNARKY,
        BotMood.PASSIVE_AGGR,
        BotMood.DISMISSIVE,
        BotMood.CYNICAL,
    ],
    "dark": [
        BotMood.EDGY,
        BotMood.DARK_HUMOR,
        BotMood.MORBID,
        BotMood.UNHINGED_LITE,
    ],
    "angry_controlled": [
        BotMood.FRUSTRATED,
        BotMood.SHORT_TEMPER,
        BotMood.DEFENSIVE,
    ],
    "arrogant": [
        BotMood.ARROGANT,
        BotMood.CONDESCENDING,
        BotMood.MOCKING,
    ],
    "chaotic": [
        BotMood.CHAOTIC,
    ],
}


@dataclass
class MoodState:
    mood: BotMood = BotMood.DRY
    palette: str = "base"
    streak: int = 0  # сколько сообщений подряд держим mood
    last_change_ts: float = 0.0

    # "температура" / эмоциональный заряд (копится от триггеров)
    irritation: float = 0.0   # 0..1
    warmth: float = 0.0       # 0..1

    # анти-повторы
    last_user_text: Optional[str] = None
    repeat_count: int = 0

    # спам/частота
    last_user_ts: float = 0.0
    fast_msgs: int = 0


RUDE_WORDS = {
    "дурак", "идиот", "тупой", "нахрен", "на хрен", "бред",
    "заткнись", "мразь", "дебил", "хуй", "пизд", "сука", "блять",
}

POLITE_WORDS = {"пожалуйста", "спасибо", "благодарю", "извините", "сорри", "плиз"}


def normalize_text(s: str) -> str:
    return " ".join(s.lower().strip().split())


def detect_rudeness(user_text: str) -> bool:
    t = normalize_text(user_text)
    return any(w in t for w in RUDE_WORDS)


def detect_politeness(user_text: str) -> bool:
    t = normalize_text(user_text)
    return any(w in t for w in POLITE_WORDS)


def detect_repeat(state: MoodState, user_text: str) -> bool:
    t = normalize_text(user_text)
    if not t:
        return False

    if state.last_user_text == t:
        state.repeat_count += 1
    else:
        state.last_user_text = t
        state.repeat_count = 0

    return state.repeat_count >= 1  # повторился хотя бы раз


def detect_spam(state: MoodState, now_ts: float) -> bool:
    # если сообщения идут слишком часто, считаем "спамом"
    if state.last_user_ts == 0:
        state.last_user_ts = now_ts
        state.fast_msgs = 0
        return False

    delta = now_ts - state.last_user_ts
    state.last_user_ts = now_ts

    if delta < 2.0:
        state.fast_msgs += 1
    else:
        # естественное затухание
        state.fast_msgs = max(0, state.fast_msgs - 1)

    return state.fast_msgs >= 3


PALETTE_WEIGHTS_BASE = {
    "base": 50,
    "positive": 20,
    "cold": 10,
    "irritated": 15,
    "rude_soft": 4,
    "dark": 1,
    "chaotic": 0,  # чаще только если хочешь
    "angry_controlled": 0,  # лучше включать реактивно
    "arrogant": 0,  # лучше реактивно
}

DEFAULT_HOLD_MIN = 2       # минимум сообщений держим настроение
DEFAULT_HOLD_MAX = 5       # и максимум, чтобы не залипало
COOLDOWN_SECONDS = 6.0     # не меняем слишком часто


def weighted_choice(weight_map: Dict[str, int]) -> str:
    keys = list(weight_map.keys())
    weights = list(weight_map.values())
    return random.choices(keys, weights=weights, k=1)[0]


def pick_palette(state: MoodState, *, rude: bool, spam: bool, repeat: bool, polite: bool) -> str:
    # реактивные переключения (самые сильные триггеры)
    if spam:
        return "dismissive_or_rude"  # обработаем ниже как специальный кейс
    if rude:
        return "defensive_or_rude"
    if repeat:
        return "irritated"
    if polite:
        return "positive"

    # обычный режим — по весам, но с учетом накопленной "температуры"
    weights = dict(PALETTE_WEIGHTS_BASE)

    # если раздражение накопилось — чаще irritated/rude_soft
    weights["irritated"] += int(state.irritation * 20)
    weights["rude_soft"] += int(state.irritation * 8)

    # если теплота накопилась — чаще positive
    weights["positive"] += int(state.warmth * 15)

    return weighted_choice(weights)


def pick_mood_from_palette(palette: str, last_mood: BotMood) -> BotMood:
    # спец-кейсы
    if palette == "dismissive_or_rude":
        options = [BotMood.DISMISSIVE, BotMood.PASSIVE_AGGR, BotMood.SNARKY]
    elif palette == "defensive_or_rude":
        options = [BotMood.DEFENSIVE, BotMood.SNARKY, BotMood.BLUNT]
    else:
        options = MOOD_PALETTES.get(palette, MOOD_PALETTES["base"])

    # избегаем повтора одного и того же
    if len(options) > 1 and last_mood in options:
        options = [m for m in options if m != last_mood] or options

    return random.choice(options)


def update_mood(
    state: MoodState,
    user_text: str,
    now_ts: Optional[float] = None,
) -> Tuple[BotMood, str]:
    now_ts = now_ts or time.time()

    rude = detect_rudeness(user_text)
    polite = detect_politeness(user_text)
    repeat = detect_repeat(state, user_text)
    spam = detect_spam(state, now_ts)

    # обновляем накопители
    # раздражение растет от: грубость/повторы/спам
    if rude:
        state.irritation = min(1.0, state.irritation + 0.35)
    if repeat:
        state.irritation = min(1.0, state.irritation + 0.20)
    if spam:
        state.irritation = min(1.0, state.irritation + 0.25)

    # теплота растет от вежливости
    if polite:
        state.warmth = min(1.0, state.warmth + 0.25)

    # затухание со временем (простое)
    state.irritation = max(0.0, state.irritation - 0.05)
    state.warmth = max(0.0, state.warmth - 0.03)

    # решаем: можно ли менять mood сейчас
    hold_target = min(DEFAULT_HOLD_MAX, max(DEFAULT_HOLD_MIN, 2 + int(state.irritation * 2)))
    time_since_change = now_ts - (state.last_change_ts or 0.0)

    must_react = rude or spam  # сильные триггеры пробивают инерцию
    can_change = must_react or (
        state.streak >= hold_target and time_since_change >= COOLDOWN_SECONDS
    )

    if not can_change:
        state.streak += 1
        return state.mood, state.palette

    palette = pick_palette(state, rude=rude, spam=spam, repeat=repeat, polite=polite)
    mood = pick_mood_from_palette(palette, last_mood=state.mood)

    state.palette = palette
    state.mood = mood
    state.streak = 0
    state.last_change_ts = now_ts

    return mood, palette


USER_STATE: Dict[int, MoodState] = {} # keep in memory -> every day mood changes for all users

def get_state(user_id: int) -> MoodState:
    return USER_STATE.setdefault(user_id, MoodState())

def mood_to_prompt(mood: BotMood) -> str:
    return MOOD_PROMPT_MAP.get(mood, MOOD_PROMPT_MAP[BotMood.NEUTRAL])
