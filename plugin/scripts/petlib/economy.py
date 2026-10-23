"""Numbers and tables. Tune here, nowhere else."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

COIN_PER_OUTPUT_TOKEN = 0.002         # 1k output tokens = 2 coins
DAILY_SOFTCAP_OUT = 300_000           # exchange daily limit: output past this a day earns the low rate
COIN_PER_OUTPUT_TOKEN_OVER_CAP = 0.0003
CACHE_BONUS_THRESHOLD = 0.5
CACHE_BONUS = 1.05

FEED_COST = 50
FORCE_FEED_COST = 100
FEED_HUNGER = 40

PAT_MOOD = 8                          # mood per pat
PAT_DAILY_LIMIT = 5

HUNGER_PER_HOUR = 5.0
MOOD_PER_HOUR = 2.0
MOOD_PER_HOUR_STARVING = 4.0

LEVELS = [0, 1500, 4000, 7000, 10000, 15000, 20000, 26000, 33000, 40000]   # xp needed for level index+1
LEVEL_STEP_AFTER_10 = 15000
FIRST_EVOLUTION_LEVEL = 5
SECOND_EVOLUTION_LEVEL = 10

DAILY_INTEREST = {"miser": 0.01, "tycoon": 0.03}
DAILY_EXTORTION = {"thug": 0.10, "boss": 0.25}
LOANSHARK_INTEREST = 0.10
INFLUENCER_REFUND = 0.10
MISER_PRICE_MULT = 1.3
BROKE_SELL_RATIO = 0.5
BROKE_MOOD_HIT = 30
BURNOUT_DAYS = 2


@dataclass(frozen=True)
class Item:
    name: str
    slot: str          # head | face | body | room | bg | hotel
    price: int
    min_level: Optional[int] = None
    grant: Optional[str] = None    # not for sale: handed over by an event, this says which
    forms: Optional[tuple] = None  # for sale only while the pet has one of these forms


CATALOG = {
    "party_hat": Item("파티 모자", "head", 0),
    "fedora": Item("중절모", "head", 600),
    "sunglasses": Item("선글라스", "face", 450),
    "hoodie": Item("후드티", "body", 1000),
    "cushion": Item("쿠션", "room", 750),
    "plant": Item("화분", "room", 400),
    "crown": Item("왕관", "head", 2500, FIRST_EVOLUTION_LEVEL),
    # backgrounds: the expanded widget's stage
    "street": Item("환전소 거리", "bg", 0),
    "night_factory": Item("밤의 공장", "bg", 800),
    "vault": Item("환전소 금고 안", "bg", 1500),
    "alley": Item("환전소 뒷골목", "bg", 0, grant="불량배 계열만 해금"),
    "two_factories": Item("공장이 두 개인 마을", "bg", 0, grant="가출 후 찾아오면 해금"),
    "mansion": Item("황금 저택", "bg", 0, grant="재벌만 해금"),
    # hotels: what the widget shows while the pet is on vacation (looks only, the stay is the same)
    "toki_hotel": Item("토키 호텔", "hotel", 0),
    "mushroom_inn": Item("버섯 여관", "hotel", 600),
    "beach_resort": Item("바닷가 리조트", "hotel", 800),
    "snow_lodge": Item("눈 산장", "hotel", 1000),
    "space_hotel": Item("우주 호텔", "hotel", 1500),
    "golden_hotel": Item("황금 호텔", "hotel", 2500, forms=("tycoon",)),
}
SLOTS = ("head", "face", "body", "room", "bg", "hotel")


@dataclass(frozen=True)
class Gift:
    """One-off present bought in the room's 선물 tab and given right away."""
    name: str
    kind: str          # treat: mood up at once | toy: mood up and slower mood decay for `hours`
    price: int
    mood: int
    hours: float = 0


GIFTS = {
    "candy": Gift("사탕", "treat", 40, 15),
    "pudding": Gift("푸딩", "treat", 80, 30),
    "cake": Gift("케이크", "treat", 150, 60),
    "yarn": Gift("털실", "toy", 60, 10, 3),
    "ball": Gift("공", "toy", 120, 20, 6),
    "doll": Gift("인형", "toy", 200, 25, 24),
}
TREAT_DAILY_LIMIT = 3                  # more and the pet gets a tummy ache
TOY_DECAY = 0.5                        # mood falls at half speed while a toy is being played with
GIFT_MOOD_MULT = {"spender": 1.5, "influencer": 1.5}
NO_TREAT_FORMS = ("thug", "boss")      # too cool for sweets; toys still work
STARTER_ITEMS = {"party_hat": "head", "street": "bg", "toki_hotel": "hotel"}
FORM_ONLY_KO = {"tycoon": "재벌만"}
GRANT_ON_FORM = {"thug": "alley", "boss": "alley", "tycoon": "mansion"}
GRANT_ON_RETURN = "two_factories"

# background bonuses, only while equipped and only for the matching form family
BG_MOOD_BONUS = {"night_factory": (("owl", "hunter", "vampire"), 5)}      # mood +5 each new day
BG_INTEREST_BONUS = {"vault": (("miser", "tycoon"), 0.005)}              # daily interest +0.5%p


@dataclass(frozen=True)
class Form:
    ko: str
    glyph: str
    tier: int          # 0 base, 1 first, 2 second


FORMS = {
    "base": Form("아기", "🐣", 0),
    "model": Form("모범생", "🎓", 1),
    "miser": Form("구두쇠", "💰", 1),
    "owl": Form("올빼미", "🦉", 1),
    "spender": Form("사치쟁이", "🎀", 1),
    "thug": Form("불량배", "😈", 1),
    "runaway": Form("가출", "🏃", 1),
    "scholar": Form("박사", "📚", 2),
    "burnout": Form("번아웃", "🔥", 2),
    "tycoon": Form("재벌", "👑", 2),
    "loanshark": Form("고리대금업자", "🧾", 2),
    "hunter": Form("야행성 사냥꾼", "🌙", 2),
    "vampire": Form("흡혈귀", "🧛", 2),
    "influencer": Form("인플루언서", "📸", 2),
    "broke": Form("탕진잼", "💸", 2),
    "boss": Form("조직 보스", "🕶️", 2),
}
FIRST_TIER = ("model", "miser", "owl", "spender", "thug", "runaway")
NOCTURNAL = ("owl", "vampire", "hunter")
SHOP_BLOCKED = ("thug", "boss", "runaway")


def level_for_xp(xp: int) -> int:
    level = 1
    for i, need in enumerate(LEVELS):
        if xp >= need:
            level = i + 1
    if xp >= LEVELS[-1]:
        level = len(LEVELS) + (xp - LEVELS[-1]) // LEVEL_STEP_AFTER_10
    return level


def xp_for_level(level: int) -> int:
    if level <= len(LEVELS):
        return LEVELS[max(level, 1) - 1]
    return LEVELS[-1] + (level - len(LEVELS)) * LEVEL_STEP_AFTER_10


def earn_multiplier(form: str, period: str) -> float:
    if form == "burnout":
        return 0.0
    if form == "model":
        return 1.1
    if form == "scholar":
        return 1.2
    if form == "owl" and period == "night":
        return 2.0
    if form == "hunter" and period == "night":
        return 3.0
    if form == "vampire" and period == "day":
        return 0.95
    return 1.0


def hunger_rate(form: str) -> float:
    return 0.7 if form in ("model", "scholar") else 1.0


def mood_floor(form: str) -> int:
    return 70 if form in ("spender", "influencer") else 0


def for_sale(item_id: str) -> bool:
    item = CATALOG[item_id]
    return item.price > 0 and item.grant is None


def bought_count(state: dict) -> int:
    """Item count for spender/influencer: free backgrounds (starter, granted) don't count, as before they existed."""
    return sum(1 for k in state["items_owned"]
               if not (k in CATALOG and CATALOG[k].slot in ("bg", "hotel") and not for_sale(k)))


def bg_bonus(table: dict, state: dict):
    rule = table.get(state["equipped"].get("bg"))
    return rule[1] if rule and state["form"] in rule[0] else 0


def price(item_id: str, form: str) -> int:
    p = CATALOG[item_id].price
    if form == "miser":
        p = int(round(p * MISER_PRICE_MULT))
    return p


def is_unlocked(item_id: str, state: dict) -> bool:
    item = CATALOG[item_id]
    if item.forms:
        return state.get("form") in item.forms
    if state.get("form") == "tycoon":
        return True
    return item.min_level is None or state.get("level", 1) >= item.min_level


def shop_blocked(form: str) -> bool:
    return form in SHOP_BLOCKED


def feed_blocked(form: str, period: str) -> Optional[str]:
    if form == "runaway":
        return "가출 중이라 먹일 수 없어. /pet find 로 찾아봐"
    if form in NOCTURNAL and period == "day":
        return "낮이라 자고 있어… 밤에 다시 와"
    return None


def cache_ratio(input_tokens: int, cache_read: int, cache_creation: int) -> float:
    total = input_tokens + cache_read + cache_creation
    return cache_read / total if total else 0.0


def output_coins(output_tokens: int, day_out_before: int = 0) -> float:
    """Base coins for output, the part past today's soft cap at the low rate."""
    under = max(0, min(output_tokens, DAILY_SOFTCAP_OUT - day_out_before))
    return under * COIN_PER_OUTPUT_TOKEN + (output_tokens - under) * COIN_PER_OUTPUT_TOKEN_OVER_CAP


def turn_coins(output_tokens: int, input_tokens: int, cache_read: int,
               cache_creation: int, form: str, period: str, day_out_before: int = 0) -> float:
    coins = output_coins(output_tokens, day_out_before)
    if cache_ratio(input_tokens, cache_read, cache_creation) >= CACHE_BONUS_THRESHOLD:
        coins *= CACHE_BONUS
    return coins * earn_multiplier(form, period)
