"""Speech bubble lines: form × situation. Missing entries fall back to "base".

Placeholders: {n} coins this turn, {out} today's output tokens (e.g. 12.4k), {item} item name.
Tone (docs/LORE.md): short, cute, and now and then one line that lands cold.
"""
from __future__ import annotations

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


def lines(form: str, situation: str) -> list:
    own = LINES.get(form, {}).get(situation)
    return own if own else LINES["base"].get(situation, [])
