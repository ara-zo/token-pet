# Token Pet v1 설계

Claude Code 토큰 사용량이 코인이 되는 다마고치. 컨셉 전문은 `docs/SPEC.md`, 화면은 `docs/mockup.html`.
이 문서는 1차 범위를 구현 가능한 수준으로 확정한 설계다. 스펙과 다른 결정은 "결정" 표시로 적었다.

## 1. 범위

1차에 포함:

1. Claude Code 플러그인: Stop·SessionStart 훅, `/pet` 커맨드, 상태표시줄 스크립트
2. `~/.claude/pet/state.json` 스키마, 경제, 틱, 1차·2차 진화 판정 (전부 순수 함수 + pytest)
3. Tauri 데스크톱 앱: 접힌 상태(160×160)와 펼친 위젯(360×460)만. 상점은 `/pet shop`

제외: Windows, 서브에이전트 토큰 집계, 앱 내 상점·옷장, 사냥꾼 "드롭", 다기기 동기화.

## 2. 설치와 실행 모델

- 레포 하나가 마켓플레이스이자 플러그인. 루트 `.claude-plugin/marketplace.json`이 `"source": "./plugin"`을 가리킨다.
- 사용자 설치: `/plugin marketplace add ara-zo/token-pet` → `/plugin install token-pet@token-pet`.
- 상태표시줄은 플러그인이 설정할 수 없다(플러그인 settings는 `agent`, `subagentStatusLine`만 적용됨). `/pet setup`이 사용자 동의 아래 `~/.claude/settings.json`의 `statusLine`을 써 준다. 결정: 플러그인 경로는 업데이트마다 바뀌므로 settings에는 `python3 ~/.claude/pet/statusline.py`(부트스트랩)를 적고, 그 파일이 state.json의 `plugin_root`를 읽어 petlib을 찾는다. `plugin_root`는 훅이 실행될 때마다 갱신된다.
- 런타임 요구: `python3` (3.9+, 표준 라이브러리만). macOS Command Line Tools에 포함.
- Tauri 앱은 GitHub Releases에서 받는 선택 사항. 없어도 플러그인만으로 전부 동작한다.

## 3. 디렉터리 구조

```
token-pet/
  .claude-plugin/marketplace.json
  plugin/
    .claude-plugin/plugin.json
    hooks/hooks.json              Stop → collect.py, SessionStart → tick.py
    commands/pet.md               /pet [status|feed|shop|buy|equip|unequip|name|find|reset|setup]
    statusline.sh                 stdin JSON → python3 -m petlib.cli statusline
    scripts/
      collect.py  tick.py  pet.py   얇은 진입점 (sys.path에 scripts/ 추가 후 petlib 호출)
      petlib/
        __init__.py
        clock.py        now() 주입 지점, 로컬 타임존, 야간/새벽/낮 판정
        schema.py       기본 state, 마이그레이션, daily_log 항목 생성
        store.py        경로, flock 잠금, 읽기, atomic 쓰기, `with store.transaction() as s:`
        economy.py      환율, 레벨 표, 상점 카탈로그, 형태별 배율
        transcript.py   JSONL 증분 읽기 + message.id 중복 제거
        tick.py         경과시간 정산, 일일 롤오버, 형태별 일일 효과
        evolve.py       1차·2차 판정, 복귀 조건, 가출
        actions.py      feed/buy/equip/name/find/reset
        speech.py       말풍선 문구 선택
        render.py       /pet 텍스트 출력, statusline 한 줄
        cli.py          서브커맨드 디스패치, --json 출력
    tests/
  app/
    src/  index.html  app.js  styles.css  sprites.js
    src-tauri/  tauri.conf.json  src/main.rs  Cargo.toml
  docs/  SPEC.md  mockup.html  superpowers/specs/
  README.md
```

## 4. state.json

경로 `~/.claude/pet/state.json`, 잠금파일 `~/.claude/pet/.lock`. 쓰기는 petlib만 한다. 앱은 읽기 전용이고 먹이주기는 `pet.py feed --json`을 서브프로세스로 호출한다.

```json
{
  "version": 1,
  "name": "모찌",
  "created_at": "2026-10-20T09:00:00+09:00",
  "level": 3, "xp": 1240, "coins": 1240, "coin_carry": 0.4,
  "hunger": 38, "mood": 72,
  "form": "base", "form_since": "2026-10-20T00:00:00+09:00",
  "items_owned": ["party_hat"], "equipped": {"head": "party_hat"},
  "last_fed_at": "...", "last_tick_at": "...", "last_turn_at": "...", "last_turn_earned": 12,
  "plugin_root": "/Users/x/.claude/plugins/cache/.../plugin",
  "speech": "오늘 12.4k 토큰 썼지? 나 배고파…",
  "events": [{"at": "...", "type": "earn", "text": "+12"}],
  "sessions": {"<session_id>": {"offset": 48211, "seen_ids": ["msg_..."], "updated_at": "..."}},
  "daily_log": [{
    "date": "2026-10-20", "feeds": 2, "dawn_feeds": 0, "day_feeds": 2, "sessions": 3, "day_sessions": 2,
    "tokens_in": 88000, "tokens_out": 12400, "cache_read": 54000, "night_out": 2400,
    "earned": 312, "spent": 0, "purchases": 0, "refusals": 0,
    "hunger_zero_hours": 0.0, "max_gap_hours": 5.5, "zero_balance": false
  }],
  "since_form": {"days": 0, "tokens_out": 0, "cache_read": 0, "tokens_in_total": 0, "night_out": 0,
                 "dawn_feeds": 0, "day_feeds": 0, "day_sessions": 0, "purchases": 0, "refusals": 0,
                 "zero_balance_days": 0, "streak_50k": 0, "feed_streak": 0},
  "flags": {"debt": 0, "demand_item": null, "demand_since": null, "burnout_until": null,
            "find_days": [], "boss_hijack": false},
  "badges": []
}
```

- `daily_log`는 14일 유지. `since_form`은 현재 형태가 된 뒤의 누적치로, 2차 판정에 쓴다(14일 창으로는 Lv.5~10 구간을 못 본다).
- `seen_ids`는 세션당 최근 200개. `sessions`에서 7일 지난 항목은 롤오버 때 삭제.
- `events`는 최근 20개. 앱과 SessionStart 알림이 읽는다.
- 시간은 전부 ISO 8601 로컬 오프셋 포함. 야간 22:00~04:00, 새벽 04:00~08:00, 낮 08:00~22:00.
- 버전이 올라가면 `schema.migrate()`가 빠진 키를 기본값으로 채운다.

### 쓰기 프로토콜

```
with transaction() as state:      # flock(LOCK_EX) → 읽기 → migrate → tick.apply(state, now)
    ...수정...                      # 블록 종료 시 tmp 파일에 쓰고 os.replace, 잠금 해제
```

statusline은 잠금 없이 읽기만 하고, 틱을 메모리에서만 계산해 표시한다(빨라야 하고 300ms마다 호출될 수 있음).

## 5. 코인 적립 (Stop 훅)

확인된 사실: 한 API 응답이 콘텐츠 블록마다 한 줄씩 JSONL에 기록되고 각 줄이 같은 `message.usage`를 반복한다. Stop 시점에 마지막 메시지가 아직 기록되지 않았을 수 있다.

1. stdin JSON에서 `session_id`, `transcript_path`를 읽는다. `stop_hook_active`는 무시(항상 집계).
2. `sessions[sid].offset`부터 파일을 읽는다. 마지막 줄이 불완전하면 그 줄은 버리고 offset을 그 앞까지만 올린다.
3. `type == "assistant"`, `isSidechain != true`, `message.id`가 `seen_ids`에 없는 줄만 집계한다.
4. 턴 수입:
   - 기본 `output_tokens × 0.02`
   - 캐시 보너스: `cache_read / (input + cache_read + cache_creation) ≥ 0.5` 이면 ×1.05 (메시지 단위)
   - 형태 배율(economy.FORM_EARN): 모범생 1.1, 박사 1.2, 올빼미 야간 2.0, 사냥꾼 야간 3.0, 번아웃 0, 흡혈귀 낮 메시지 0.95
   - `coin_carry`에 더해 정수부만 `coins`, `xp`, `daily_log.earned`로 옮긴다.
5. `daily_log[오늘]`: tokens_in(=input+cache_read+cache_creation), tokens_out, cache_read, night_out(야간 메시지의 output), sessions(새 session_id면 +1, 낮이면 day_sessions +1).
6. `last_turn_earned`, `last_turn_at`, `events += earn`, `speech` 갱신.
7. stdout은 비운다(Claude 컨텍스트에 아무것도 넣지 않는다). 실패해도 exit 0. 로그는 `~/.claude/pet/collect.log`에 마지막 50줄만.

## 6. 틱

모든 `transaction()` 진입 시 `tick.apply(state, now)` 호출.

- `h = (now - last_tick_at) / 1h`. 배고픔 `-3h × hunger_rate`, 기분 `-2h`. 배고픔 0인 구간에서는 기분 `-4h`. 0~100 클램프.
- `hunger_rate`: 모범생·박사 0.7, 그 외 1.0. 사치쟁이·인플루언서는 기분 하한 70.
- 배고픔이 0에 닿는 시각을 선형으로 역산해 `hunger_zero_hours`를 해당 날짜들에 나눠 누적한다.
- `max_gap_hours = max(기존, now - last_fed_at)`.
- 날짜 경계를 넘을 때마다(여러 날이면 반복): 전날 마감 → `since_form` 누적, 일일 효과 적용, 새 항목 생성, 14일 초과 삭제.
- 일일 효과(형태별): 구두쇠 잔액 +1%, 재벌 +3%, 고리대금업자 `debt` 10% 이자 후 잔액에서 차감, 불량배 -10%, 보스 -25%, 사치쟁이·인플루언서 `demand_item` 생성(미보유 아이템 중 랜덤), 전날 요구 미해소면 `refusals +1`, 탕진잼 랜덤 아이템 1개 매각(가격 50%)과 기분 -30, 번아웃 `burnout_until` 지나면 복귀 판정.
- `zero_balance`: 마감 시 coins == 0. `streak_50k`: 전날 tokens_out ≥ 50,000이면 +1 아니면 0. `feed_streak`: 전날 feeds ≥ 1이면 +1 아니면 0.
- 마지막에 `evolve.check(state, now)`.

## 7. 레벨

xp는 누적 획득 코인(지출 무관). `economy.LEVELS`:

| Lv | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 이후 |
|---|---|---|---|---|---|---|---|---|---|---|
| xp | 300 | 800 | 1,400 | 2,000 | 3,200 | 4,600 | 6,200 | 8,000 | 10,000 | +3,000/Lv |

레벨업은 collect 직후 계산한다. Lv.5, Lv.10 도달 이벤트가 `evolve`의 판정 트리거다.

## 8. 진화

### 1차 (form == base 이고 level ≥ 5 가 된 순간, 지난 7일 daily_log)

우선순위 순으로 첫 매치:

| 형태 | 조건 (7일 합계) |
|---|---|
| runaway 가출 | Lv.5 판정 시점엔 해당 없음(아래 "상시 전이") |
| thug 불량배 | hunger_zero_hours ≥ 24 |
| owl 올빼미 | night_out / tokens_out ≥ 0.6 (tokens_out > 0) |
| miser 구두쇠 | coins ≥ 2,000 and purchases == 0 and feeds ≤ 7 |
| spender 사치쟁이 | spent ≥ 0.8 × earned and len(items_owned) ≥ 4 (결정: 카탈로그가 7개뿐이라 스펙의 8을 4로 낮춤) |
| model 모범생 | 기본 |

판정 시 `form_since = now`, `since_form` 초기화, `events += evolve`, 배지 `first_evolution`.

### 상시 전이 (level ≥ 5, 매 롤오버)

- 불량배 진입: 어떤 1차·2차 형태든 7일 hunger_zero_hours ≥ 24 → thug (단 가출·보스 제외).
- 가출 진입: 7일 feeds 합 == 0, 또는 thug 상태로 `feed_streak == 0`이 3일 → runaway. 진입 시 `coins //= 2`, 상점·급식 불가.
- 갱생: thug에서 `feed_streak ≥ 3` → 배지 `rehab`, form = base로 되돌린 뒤 즉시 1차 재판정(level ≥ 10이면 이어서 2차 판정).
- 귀환: runaway에서 `/pet find`를 서로 다른 날 3회(`flags.find_days`) → form = model, 배지 `returned`.

### 2차 (level ≥ 10 이 된 순간, `since_form` 기준)

| 1차 | 상승 조건 → 형태 | 타락 조건 → 형태 | 아니면 |
|---|---|---|---|
| model | cache_read / tokens_in_total ≥ 0.7 → scholar 박사 | streak_50k ≥ 5 → burnout 번아웃 | model 유지 |
| miser | coins ≥ 10,000 and purchases ≥ 1 → tycoon 재벌 | coins ≥ 10,000 and purchases == 0 → loanshark 고리대금업자 | miser 유지 |
| owl | dawn_feeds ≥ 3 → hunter 사냥꾼 | night_out/tokens_out ≥ 0.9 and day_feeds == 0 → vampire 흡혈귀 | owl 유지 |
| spender | items ≥ 6 (결정: 스펙 15 → 6) and refusals ≤ 3 → influencer 인플루언서 | zero_balance_days ≥ 5 and refusals ≥ 5 → broke 탕진잼 | spender 유지 |
| thug | 해당 없음 | 항상 → boss 조직 보스 | |

타락은 상승보다 먼저 검사한다. "유지"면 Lv.11 이후 매 롤오버마다 다시 판정한다.

### 2차 효과와 복귀

| 형태 | 효과 | 복귀 |
|---|---|---|
| scholar | 코인 ×1.2, `/pet`에 절약 팁 한 줄 | — |
| burnout | 코인 ×0 (`burnout_until = +2일`), 이후 하루 tokens_out == 0인 날이 지나면 model로 복귀 후 재판정 | 위 |
| tycoon | 이자 3%, 전품목 해금, 금색 스프라이트 | — |
| loanshark | 코인 부족해도 급식 가능(debt 증가), 매일 debt×10%를 잔액에서 차감 | 구매 1회 → tycoon |
| hunter | 야간 코인 ×3 | — |
| vampire | 낮 메시지 코인 ×0.95, 낮 급식 불가 | 낮 급식 3회 → owl 후 재판정 (낮 급식은 불가하므로 `/pet feed --force`로 2배 가격 급식을 허용) |
| influencer | 구매액 10% 환급 | — |
| broke | 매일 아이템 랜덤 매각, 기분 -30 | 3일 연속 마감 잔액 ≥ 500 → spender |
| boss | 삥 25%, 상태표시줄 문구 점거(`boss_hijack`), 상점 봉쇄 | `/pet reset` "독립 선언": 새 펫 + 배지 `independence` |

## 9. 먹이·상점·행동 (`pet.py`)

- `feed`: 30코인, 배고픔 +40. 거부: coins < 30(단 loanshark는 debt로 허용), runaway, owl·vampire·hunter의 낮 시간("자고 있음"). `--force`는 vampire 낮 급식만 60코인으로 허용. 기록: feeds, dawn_feeds(04~08), day_feeds(08~22), last_fed_at, feed_streak는 롤오버 때.
- `shop`: 카탈로그와 가격(miser ×1.3), 잠금 표시(crown은 Lv.5, tycoon은 전부 해금). thug·boss·runaway는 "상점 봉쇄".
- `buy <id>`: 코인 차감, items_owned 추가, spent·purchases 기록, demand_item 일치 시 해소, influencer 10% 환급.
- `equip <id>` / `unequip <slot>`: 슬롯은 head, face, body, room(쿠션·화분).
- `name <이름>`: 1~8자.
- `find`: runaway일 때만. 오늘 날짜를 find_days에 추가, 3일째면 귀환.
- `reset`: boss일 때 "독립 선언". 그 외엔 `--confirm` 필요. 배지는 유지.
- `setup`: statusLine 설정 JSON을 출력하고, `--write`면 `~/.claude/settings.json`에 병합(기존 statusLine이 있으면 덮지 않고 안내).
- 모든 서브커맨드는 `--json`으로 기계용 출력을 낸다. 앱이 쓴다.

카탈로그(`economy.CATALOG`): party_hat(머리, 0, 기본 보유), fedora 중절모 120, sunglasses 선글라스 90, hoodie 후드티 200, cushion 쿠션 150, plant 화분 80, crown 왕관 500(Lv.5).

## 10. 출력

### `/pet` 커맨드 (`commands/pet.md`)

인라인 bash 실행으로 Claude가 추론 없이 결과를 그대로 보여준다.

```
---
description: 토큰 펫 상태·먹이·상점
argument-hint: [status|feed|shop|buy <id>|equip <id>|name <이름>|find|reset|setup]
allowed-tools: Bash(python3:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pet.py" $ARGUMENTS`

위 출력을 그대로 보여줘. 출력이 "SETUP_PROMPT"로 시작하면 사용자에게 settings.json 수정 동의를 묻고, 동의하면 `--write`를 붙여 다시 실행해.
```

### 상태표시줄 (`statusline.sh`)

stdin JSON(`model.display_name`, `workspace.current_dir`, `context_window.used_percentage`, `cost.total_cost_usd`)과 state를 합쳐 한 줄. ANSI 색 사용. 형태별 글리프는 이모지 표(base 🐣, model 🎓, miser 💰, owl 🦉, spender 🎀, thug 😈, runaway 🏃, scholar 📚, burnout 🔥, tycoon 👑, loanshark 🧾, hunter 🌙, vampire 🧛, influencer 📸, broke 💸, boss 🕶️).

```
~/work/dev-hub │ opus │ 🐣 모찌 Lv.3 🪙1,240 +12 배고픔▓▓░░░ 기분▓▓▓▓░ │ ctx 41% · $2.18
```

boss면 가운데 구간을 "👔 보스: 상납 안 하면 알지?" 로 점거한다. state 파일이 없으면 펫 구간을 생략한다.

### SessionStart 훅 (`tick.py`)

틱을 돌리고, 미전달 이벤트(evolve, runaway, extort, demand)가 있으면 `hookSpecificOutput.additionalContext`로 한 줄 요약을 넣고 `delivered` 처리한다. 이벤트가 없으면 출력하지 않는다. 처음 실행이면 state를 만들고 "모찌가 태어났어요" 이벤트를 넣는다. `plugin_root`를 매번 갱신한다.

### 말풍선 (`speech.py`)

우선순위: 최근 10분 내 이벤트 문구 > 배고픔 < 20 > 기분 < 30 > 형태 전용 문구(요구·협박·잠) > 일반 문구(오늘 토큰·시간대). 결과는 state.speech에 저장하고 `/pet status`, 앱 둘 다 그대로 쓴다.

## 11. Tauri 앱

- Tauri 2, 프론트는 번들러 없는 바닐라 HTML/CSS/JS. mockup.html의 접힌 상태·펼친 위젯 마크업과 SVG를 `src/`로 옮기고 인라인 스타일을 `styles.css`로 뺀다. 형태별 SVG는 `sprites.js`에 문자열 테이블.
- 창 하나: 투명, 프레임 없음, 항상 위, Dock 아이콘 없음(macOS activation policy Accessory), 시작 크기 160×160. 스프라이트 클릭으로 360×460 펼침, 접기 버튼이나 바깥 클릭으로 복귀. 스프라이트 영역은 `data-tauri-drag-region`.
- Rust: 시작 시 state.json 읽어 `state` 이벤트 emit, `notify`로 `~/.claude/pet/` 감시(파일은 rename으로 교체되므로 디렉터리 감시) → 변경 시 다시 읽어 emit. 200ms 디바운스.
- `feed` 커맨드: `state.plugin_root/scripts/pet.py feed --json`을 실행하고 결과를 반환. 실패 메시지는 말풍선으로.
- 꾸미기 버튼: 1차에서는 "터미널에서 /pet shop" 토스트.
- "+N" 말풍선: `last_turn_at`이 바뀌고 5초 이내면 접힌 상태 우상단에 2초 표시.
- 배고픔·기분은 받은 값에 로컬 틱을 적용해 1분마다 다시 그린다(파일이 안 바뀌어도 줄어드는 게 보이도록).
- 배포: `cargo tauri build` → `.dmg`를 Releases에 올린다. 서명·공증은 1차 제외(README에 우클릭 열기 안내).

## 12. 테스트

- `plugin/tests/`, pytest. `clock.now`를 고정 시각으로 주입. 전부 임시 디렉터리의 state 경로를 쓴다(`PET_HOME` 환경변수로 경로 오버라이드).
- `test_transcript.py`: 3줄 중복 응답이 1회만 집계, 불완전한 마지막 줄 무시 후 다음 호출에서 집계, sidechain 제외, offset 전진.
- `test_economy.py`: 환율, 캐시 보너스 경계(0.5), carry, 레벨 표.
- `test_tick.py`: 감소 속도, 0 도달 시각 역산, 여러 날 롤오버, 14일 트림, 일일 효과 각 형태.
- `test_evolve.py`: 1차 6종 + 우선순위, 2차 표 전부, 상시 전이, 갱생·귀환·복귀. 표를 `pytest.mark.parametrize`로.
- `test_actions.py`: feed/buy/equip 거부 사유, 외상, --force, find, reset.
- `test_store.py`: 두 프로세스가 동시에 transaction을 열어도 합계가 보존됨(`multiprocessing`).
- `test_render.py`: statusline 문자열 스냅샷, state 없음 케이스.
- 앱: Rust 쪽은 state 파싱 단위 테스트만. UI는 수동 확인.

## 13. 미정 (실사용 후 조정)

- 환율·감소 속도·레벨 표 수치
- 사냥꾼 드롭, 앱 내 옷장
- 서브에이전트 토큰 집계 여부
- 코드 서명
