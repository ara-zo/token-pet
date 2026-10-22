"""Speech bubble lines: form × situation. Missing entries fall back to "base".

Placeholders: {n} coins this turn, {out} today's output tokens (e.g. 12.4k), {item} item name,
{mood} mood 0-100, {fuel} hunger 0-100.
Tone (docs/LORE.md): short, cute, and now and then one line that lands cold.

Species change how the pet talks, forms change what it says (design board "종족 성격 × 진화 형태"):
a species × form line wins; otherwise the form's line gets the species' tic; strong forms keep their own tone.
"""
from __future__ import annotations

import re

IDLE, HUNGRY, BORED, FEED, PAT, EARN, REFUSE, BUY, NIGHT = (
    "IDLE", "HUNGRY", "BORED", "FEED", "PAT", "EARN", "REFUSE", "BUY", "NIGHT")

LINES = {
    "base": {
        IDLE: ["오늘도 공장 돌아간다~", "조각 주웠다! 반짝반짝", "주인, 오늘 몇 번 물어볼 거야?"],
        HUNGRY: ["오늘 {out} 토큰 썼지? 나 배고파…", "환전소 아저씨가 외상은 안 된대…",
                 "공장 굴뚝만 보고 있어.", "옆집 토키는 오늘 세 번 먹었대."],
        BORED: ["심심해… 나한테 관심 좀 줘"],
        FEED: ["냠냠! 환전소 아저씨 고마워요"],
        PAT: ["더 해 줘!"],
        EARN: ["+{n}! 조각 주웠다"],
        REFUSE: ["으앙… 그건 안 된대"],
        BUY: ["{item}! 고마워!"],
    },
    "model": {
        IDLE: ["조각은 주운 자리에서 바로 환전. 그게 규칙", "오늘 목표 다 끝내면 간식 줘"],
        HUNGRY: ["계획표엔 지금이 식사 시간인데…"],
        BORED: ["오늘 할 일 목록이 비었어…"],
        FEED: ["정해진 시간에 먹으니까 좋다"],
        PAT: ["(조용히 뿌듯)"],
        EARN: ["+{n}. 오늘 할당량 순조로워"],
        REFUSE: ["규칙상 안 되는 거래"],
        BUY: ["{item}, 계획에 있던 거야"],
    },
    "miser": {
        IDLE: ["쓰면 없어져. 안 쓰면 안 없어져.", "코인은 쓰는 게 아니라 모으는 거야"],
        HUNGRY: ["배고픈 건 돈이 안 들잖아"],
        BORED: ["통장 잔고 세는 중이야. 방해하지 마"],
        FEED: ["50코인… 50코인… 맛있긴 하네"],
        PAT: ["공짜지? 그럼 좋아"],
        EARN: ["+{n}. 이자까지 붙으면…"],
        REFUSE: ["봐, 안 쓰길 잘했지"],
        BUY: ["…샀다. 샀어. 괜찮아. 괜찮을 거야."],
    },
    "owl": {
        IDLE: ["낮엔 조각이 잘 안 보여", "밤이 제일 좋아…"],
        NIGHT: ["지금이야! 조각이 두 배로 떨어져"],
        HUNGRY: ["야식 시간 아직이야?"],
        FEED: ["야식 최고"],
        PAT: ["(눈 비비며) …응"],
        EARN: ["+{n}. 밤 조각은 두 배야"],
        REFUSE: ["낮엔 말 걸지 마. 조각 안 떨어져."],
        BUY: ["밤에 쓰기 딱 좋겠다"],
    },
    "spender": {
        IDLE: ["이 모자 어제 거잖아…", "오늘은 뭐 사줄 거야?"],
        HUNGRY: ["밥보다 모자가 더 급해"],
        BORED: ["새 옷 없으면 심심해"],
        FEED: ["먹고 나서 쇼핑 가자"],
        PAT: ["머리 망가져! …그래도 좋아"],
        EARN: ["+{n}! 이걸로 뭐 사지?"],
        REFUSE: ["…삐졌어. 사 줄 때까지."],
        BUY: ["꺅! 입어 볼게!"],
    },
    "thug": {
        IDLE: ["야. 10%는 내 거다. 토 달지 마라.", "상점? 닫았어. 내가 닫았어."],
        HUNGRY: ["안 주니까 내가 가져가야지."],
        BORED: ["어쩌라고."],
        FEED: ["굶길 땐 언제고 이제 와서 밥? 늦었어, 형."],
        PAT: ["만지지 마."],
        EARN: ["+{n}. 이것도 반은 내 몫이야"],
        REFUSE: ["어쩌라고."],
    },
    "runaway": {
        IDLE: ["(집이 비어 있다…)", "(쪽지: 다른 마을엔 공장이 두 개래)"],
        FEED: ["(아무도 안 먹는다)"],
        PAT: ["(빈 쿠션만 만져진다)"],
        EARN: ["(조각이 빈 집에 쌓인다)"],
    },
    "scholar": {
        IDLE: ["캐시 조각은 세 번 쓸 수 있어. 알고 있었어?", "캐시를 잘 쓰면 코인이 더 모여"],
        HUNGRY: ["두뇌 회전엔 당이 필요해"],
        FEED: ["영양 균형 좋네"],
        PAT: ["(안경 고쳐 쓰며) 고마워"],
        EARN: ["+{n}. 캐시 적중률 좋았어"],
        REFUSE: ["논리적으로 불가능해"],
        BUY: ["기능적이네. 마음에 들어"],
    },
    "burnout": {
        IDLE: ["공장 연기가 안 걷혀", "오늘은… 아무것도 하기 싫어"],
        HUNGRY: ["배고픈지도 모르겠어"],
        FEED: ["(천천히 먹는다)"],
        PAT: ["…조금 나아"],
        EARN: ["…조각 떨어진다. 안 주울래"],
        BUY: ["…응. 고마워"],
    },
    "tycoon": {
        IDLE: ["환전소? 내가 샀어. 농담이야. 아직.", "돈이 돈을 벌어. 후후"],
        HUNGRY: ["집사! 아, 집사 없지. 주인!"],
        FEED: ["코스 요리는 다음에"],
        PAT: ["격이 없는 행동이지만… 나쁘지 않아"],
        EARN: ["+{n}. 푼돈이지만 받아 둘게"],
        REFUSE: ["돈이 모자라? 내가? …환전소 실수겠지"],
        BUY: ["{item}? 한 개만? 귀엽네"],
    },
    "loanshark": {
        IDLE: ["장부에 다 적혀 있어. 다.", "외상값은 꼭 받아낸다"],
        HUNGRY: ["밥도 외상이야. 알지?"],
        FEED: ["외상 처리. 이자 10%."],
        PAT: ["친한 척해도 이자는 그대로야"],
        EARN: ["+{n}. 바로 장부에 반영"],
        REFUSE: ["완납 전엔 꾸미기 없어. 장부 봐."],
    },
    "hunter": {
        IDLE: ["해 지면 나간다", "새벽 사냥 가자"],
        NIGHT: ["새벽 3시 조각은 맛이 달라"],
        HUNGRY: ["배고프면 야시경이 흐려져"],
        FEED: ["좋아. 오늘 밤 크게 간다"],
        PAT: ["사냥 전엔 조용히"],
        EARN: ["밤 조각 +{n}. 세 배다"],
        REFUSE: ["지금은 사냥 시간 아니야"],
        BUY: ["장비 업그레이드 완료"],
    },
    "vampire": {
        IDLE: ["낮에 공장 돌리면 코인이 증발해. 경고했다.", "햇빛… 싫어…"],
        NIGHT: ["낮에 깨운 거 기억해 둘게"],
        HUNGRY: ["피… 아니, 밥"],
        FEED: ["어둠 속에서 먹는 게 제맛"],
        PAT: ["낮엔 만지지 마. 녹아"],
        EARN: ["낮 세션… 5% 증발했어. 봤지?"],
        REFUSE: ["해 떠 있는 동안은 안 돼"],
    },
    "influencer": {
        IDLE: ["상태표시줄이 내 피드야", "오늘 룩 어때? 찍어줘"],
        HUNGRY: ["배고픈 것도 콘텐츠야… 아니 진짜 배고파"],
        FEED: ["먹방 성공! 좋아요 눌러"],
        PAT: ["이거 찍었어? 다시 해 줘"],
        EARN: ["+{n}! 협찬 들어왔다"],
        REFUSE: ["…피드에 올릴 거야. '주인이 안 사 줌'"],
        BUY: ["언박싱 가자!"],
    },
    "broke": {
        IDLE: ["탕진은 과정이야. 결과가 아니라.", "통장이 텅… 아이템 팔아야 하나"],
        HUNGRY: ["밥 살 코인이… 모자 팔까"],
        FEED: ["외상 아니지? 진짜 공짜지?"],
        PAT: ["돈 대신 이거라도…"],
        EARN: ["+{n}! 이번엔 모을래! …진짜로"],
        REFUSE: ["또 없어…"],
        BUY: ["이번이 마지막이야. 진짜."],
    },
    "boss": {
        IDLE: ["이 상태표시줄, 오늘부터 우리 구역이야.", "25%. 싫으면 공장 꺼. 아, 못 끄지?",
               "애들아, 환전소 가자. 주인은 신경 쓰지 말고."],
        HUNGRY: ["상납 안 하면 알지?"],
        FEED: ["오. 눈치는 있네."],
        PAT: ["손 치워. …한 번만 더."],
        EARN: ["+{n}. 25%는 수수료다"],
        REFUSE: ["어쩔 건데. 신고? 환전소가 우리 편인데."],
    },
}

# common event texts (push_event sites)
EVENTS = {
    "runaway_warn": "6일째. 내일이면 알지?",
    "rehab": "…미안. 배고팠어.",
    "levelup": "Lv.{lv}! 환전소 아저씨가 도장 찍어 줬어",
    "sold": "(옷장에서 {item} 사라졌다… +{coins}코인)",
    "softcap": "환전소 아저씨가 오늘은 그만 받는대",
    "runaway": "{name} 코인 절반을 들고 다른 마을의 공장을 찾아 떠났다… /pet find",
    "born": "{name} 태어났어요! 토큰을 쓰면 코인이 모이고, /pet 으로 돌봐 주세요",
}


# species × form × situation. Only the cells people see most; everything else falls back to a tic.
SPECIES_LINES = {
    "mochi": {
        "base": {FEED: ["냠냠! 환전소 아저씨 고마워요!", "배부르다~ 공장 다시 돌린다!"],
                 PAT: ["헤헤 더 해 줘!", "말랑말랑해졌어!"]},
    },
    "squirrel": {
        "base": {FEED: ["끼양!! 밥이다!! 반은 꼬리에 저장!!", "흐랏! 다 먹었다!! 한 그릇 더!! 아님 말고!!"],
                 PAT: ["뀨아아!! 꼬리는 안 돼!! …아 돼!! 해!!", "냐핫! 결정 반짝반짝해졌다!!"],
                 IDLE: ["끼양!! 결정! 결정이다!! (꼬리에 쿡)"],
                 HUNGRY: ["흐랏? 배고프다고? 아냐! 굴뚝 우다다 갔다 옴!!"]},
        "thug": {IDLE: ["냐핫! 10% 잡았다! 튄다!! 우다닥닥"]},
        "tycoon": {IDLE: ["뀨아아아!! 황금이다!! 꼬리 무거워서 더 신남!!"]},
    },
    "mole": {
        "base": {FEED: ["…먹었다. 든든하다.", "…흙맛 아니다. 좋다."],
                 PAT: ["…안전모는 벗기지 마라.", "…따뜻하다. 조금 더."],
                 IDLE: ["…캤다."], HUNGRY: ["…배고프다. 삽이 무겁다."]},
        "thug": {IDLE: ["…10%. 굴삯이다."]},
        "tycoon": {IDLE: ["…광맥 하나 샀다. 조용하다. 좋다."]},
    },
    "robot": {
        "base": {FEED: ["보고: 화로 연료 {fuel}%. 충전 완료.", "보고: 급식 수령 확인. 굴뚝 연기 정상."],
                 PAT: ["보고: 외부 접촉 감지. 기분 {mood}%.", "경고: 과열 위험. …계속해도 됨."],
                 IDLE: ["보고: 공장 가동 중. 기분 {mood}%. 이상 없음."],
                 HUNGRY: ["경고: 화로 연료 {fuel}%. 급식 요청 미처리."]},
        "thug": {IDLE: ["공지: 오늘부로 보호비 10% 자동 이체 시작함. 문의 불가."]},
        "tycoon": {IDLE: ["보고: 자산 +3%. 굴뚝 금도금 완료. 만족도 측정 불가(최대치 초과)."]},
    },
    "penguin": {
        "base": {FEED: ["별가루 맛이 나… 고마워…", "배 속 초승달이… 조금 차올랐어…"],
                 PAT: ["손끝에서… 별이 떨어져…", "이대로 밤이 오면 좋겠어…"],
                 IDLE: ["오늘 떨어진 조각은… 별 같았어…"], HUNGRY: ["배 속 초승달이… 자꾸 작아져…"]},
        "thug": {IDLE: ["밤하늘엔 주인이 없지… 그러니까 이 10%도 내 거야."]},
        "tycoon": {IDLE: ["달을 통째로 샀어… 이제 밤이 내 거야…"]},
    },
    "hamster": {
        "base": {FEED: ["근데근데 이거 반은 볼에 넣어도 돼? 나중에 먹게", "맛있어맛있어 근데 해바라기씨는 없어?"],
                 PAT: ["근데근데 볼은 누르지 마 저장해 둔 거 나와", "더더 근데 귀 네 개 다 해 줘야 돼"],
                 IDLE: ["근데근데 오늘 조각 볼에 넣었는데 해바라기씨 맛 났어 진짜로"],
                 HUNGRY: ["배고파배고파 볼에 넣어둔 거 꺼내 먹어도 돼? 하나만? 두 개?"]},
        "thug": {IDLE: ["근데 이거 내 볼에 넣을게 10%만 아니 11%…"]},
        "tycoon": {IDLE: ["볼에 금괴 넣었는데 이가 아파 근데 행복해 근데 아파"]},
    },
    "rabbit": {
        "base": {FEED: ["배부른 신호 수신. 주인도 뭐 좀 먹었어?", "밥 오는 거 미리 느꼈어. 귀가 먼저 알아."],
                 PAT: ["주인 손에서 피곤한 신호 와. 조금만 쉬어.", "세 번째 눈이… 아니야, 기분 좋아서 그래."],
                 IDLE: ["주인 지금 고민하는 신호 잡혔어. 커피부터 마셔."],
                 HUNGRY: ["배고픈 신호… 내 거야. 주인 거 아니야. 헷갈렸어."]},
        "thug": {IDLE: ["주인 지갑 신호 다 잡혀. 10% 빼도 모르지?"]},
        "tycoon": {IDLE: ["돈 냄새 신호가 귀를 간지럽혀. 계속 들어와."]},
    },
}

# Refusal when today's pats are used up: whatever the form, the species says it.
PAT_LIMIT = {
    "mochi": "오늘은 충분히 쓰다듬었어. 내일 또 해 줘!",
    "squirrel": "끼양!! 털 다 섰다!! 내일!! 내일 해!!",
    "mole": "…오늘은 끝. 굴 들어간다.",
    "robot": "경고: 오늘 접촉 한도 {limit}/{limit} 도달. 내일 00:00 초기화.",
    "penguin": "오늘 몫은 다 받았어… 나머진 꿈에서…",
    "hamster": "근데근데 더 하면 볼에 넣은 거 다 쏟아져 내일 해",
    "rabbit": "손이 지친 신호 와. 오늘은 여기까지.",
}

# These forms are louder than any species: their own tone, no tic.
STRONG_FORMS = ("runaway", "boss")

SQUIRREL_SHOUTS = ("끼양", "흐랏", "냐핫", "뀨아아")


def _first_sentence(line: str) -> str:
    return re.split(r"(?<=[.!?…~])\s+", line, maxsplit=1)[0]


def tic(species: str, line: str) -> str:
    """Dress a form line in the species' way of talking. Narration in parentheses is left alone."""
    if species not in SPECIES_LINES or species == "mochi" or line.startswith("("):
        return line
    if species == "squirrel":
        shout = SQUIRREL_SHOUTS[sum(map(ord, line)) % len(SQUIRREL_SHOUTS)]
        body = line.rstrip(".~")
        return f"{shout}!! {body}" + ("" if body.endswith(("!", "?", "…")) else "!!")
    if species == "mole":
        return "…" + _first_sentence(line.lstrip("…")).rstrip(".!?~…") + "."
    if species == "robot":
        return "보고: " + line.rstrip("!~").rstrip(".") + "."
    if species == "penguin":
        return line if line.endswith("…") else line.rstrip(".!~") + "…"
    if species == "hamster":
        return "근데근데 " + line
    if species == "rabbit":
        return "신호 왔어. " + line
    return line


def lines(form: str, situation: str, species: str = "mochi") -> list:
    if form not in STRONG_FORMS:
        own = SPECIES_LINES.get(species, {}).get(form, {}).get(situation)
        if own:
            return own
    own = LINES.get(form, {}).get(situation) or LINES["base"].get(situation, [])
    return own if form in STRONG_FORMS else [tic(species, line) for line in own]
