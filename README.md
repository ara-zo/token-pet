# Token Pet 🐣

Claude Code에서 쓴 **출력 토큰이 코인**이 되는 다마고치. 코인으로 먹이를 주고 꾸미고, 어떻게 키웠느냐에 따라 **진화가 갈린다**. 서버도 계정도 없다. 전부 `~/.claude/pet/state.json` 하나에 저장된다.

```
~/work/dev-hub │ opus │ 🐣 모찌 Lv.3 🪙1,240 +12 배고픔▓▓░░░ 기분▓▓▓▓░ │ ctx 41% · $2.18
```

## 설치

Claude Code 안에서:

```
/plugin marketplace add ara-zo/token-pet
/plugin install token-pet@token-pet
```

새 세션을 시작하면 펫이 태어난다. 상태표시줄에 띄우려면 한 번 더:

```
/pet setup
```

요구사항: macOS, `python3` (Command Line Tools에 포함). Windows는 아직 지원하지 않는다.

## 사용법

| 명령 | 설명 |
|---|---|
| `/pet` | 상태 (레벨·코인·배고픔·기분·말풍선) |
| `/pet feed` | 먹이주기. 50코인 → 배고픔 +40 |
| `/pet shop` | 상점 목록과 가격 |
| `/pet buy <id>` | 구매 (`fedora`, `sunglasses`, `hoodie`, `cushion`, `plant`, `crown`) |
| `/pet equip <id>` / `unequip <slot>` | 착용·해제 (슬롯: head, face, body, room) |
| `/pet name <이름>` | 이름 바꾸기 (1~8자) |
| `/pet find` | 가출했을 때 찾기. 서로 다른 날 3번 |
| `/pet reset --confirm` | 새로 시작 (배지는 유지) |
| `/pet setup` | 상태표시줄 설정 |

## 규칙

- **코인**: 출력 1k 토큰 = 5코인. 캐시 적중률 50% 이상이면 +5%. 입력 토큰은 0.
- **배고픔** 시간당 -10, **기분** 시간당 -2 (배고픔 0이면 기분 -4). 세션을 안 켜도 시간은 간다.
- **레벨**: xp = 누적 획득 코인. Lv.5 = 10,000 / Lv.10 = 50,000.
- **1차 진화 (Lv.5)**, 지난 7일 생활 기록으로 판정. 우선순위 순:

| 형태 | 조건 | 효과 |
|---|---|---|
| 😈 불량배 | 배고픔 0 누적 48h+ | 매일 잔액 10% 삥, 상점 봉쇄. 3일 연속 급식하면 갱생 |
| 🦉 올빼미 | 출력 토큰 60%+가 22~04시 | 밤 코인 2배, 낮엔 잠(급식 불가) |
| 💰 구두쇠 | 코인 2,000+, 구매 0, 급식 최소 | 매일 이자 1%, 상점가 +30% |
| 🎀 사치쟁이 | 획득의 80%+ 꾸미기 | 기분 항상 높음, 매일 "신상 사줘" |
| 🎓 모범생 | 기본 | 코인 +10%, 배고픔 느리게 |

- **7일 방치**하거나 불량배로 3일 더 두면 코인 절반을 들고 **가출**한다. `/pet find`.
- **2차 진화 (Lv.10)**: 박사·번아웃, 재벌·고리대금업자, 야행성 사냥꾼·흡혈귀, 인플루언서·탕진잼, 조직 보스. 타락 형태는 전부 복귀 조건이 있다. 자세한 조건은 [`docs/SPEC.md`](docs/SPEC.md)와 [설계 문서](docs/superpowers/specs/2026-10-20-token-pet-v1-design.md).

## 데스크톱 위젯 (선택)

`app/`의 Tauri 앱은 화면 구석에 펫을 띄운다. 접힌 상태 120×120, 클릭하면 펼쳐져 먹이를 주고 상점에서 꾸밀 수 있다. 플러그인이 쓰는 `state.json`을 감시해서 읽기만 하고, 먹이주기·구매·착용은 플러그인 스크립트를 호출한다. 빌드는 `app/README.md` 참고. 없어도 플러그인만으로 전부 동작한다.

## 구조

```
.claude-plugin/marketplace.json   레포 자체가 마켓플레이스
plugin/
  hooks/hooks.json                Stop → collect.py (코인 적립), SessionStart → tick.py (시간 정산·알림)
  skills/pet/SKILL.md             /pet (정식 이름은 /token-pet:pet)
  scripts/petlib/                 모든 로직. 순수 함수 + pytest (plugin/tests)
app/                              Tauri 2 위젯
docs/                             컨셉 스펙, 목업, 설계·플랜
```

- 상태 파일 쓰기는 `petlib`만 한다. `flock` 잠금 + 임시파일 rename이라 세션 여러 개가 동시에 돌아도 안전하다.
- 트랜스크립트는 바이트 오프셋 + `message.id` 중복 제거로 증분 집계한다 (한 응답이 여러 줄로 저장되고, Stop 시점에 마지막 줄이 아직 없을 수 있어서).
- 서브에이전트 토큰은 1차에서 세지 않는다.

테스트: `cd plugin && python3 -m pytest -q`

## 아직 안 정한 것

- 환율·감소 속도·레벨 구간은 실사용 후 조정
- 상점 아이템이 7개뿐이라 사치쟁이(4개+)·인플루언서(6개+) 기준을 스펙(8/15)보다 낮춰 뒀다. 아이템이 늘면 올린다
- 사냥꾼 "드롭", 앱 내 옷장, Windows, 코드 서명
