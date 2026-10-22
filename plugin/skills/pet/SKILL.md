---
name: pet
description: 토큰 펫 돌보기 — 상태, 밥, 쓰다듬기, 기록, 상점, 꾸미기, 도감, 휴가. /pet [status|feed|pat|stats|shop|buy <id>|equip <id>|unequip <slot>|name <이름>|dex|vacation [<일수>|end]|find|reset|setup|widget [on|off|install]|pr [on|off]|update]
argument-hint: "[status | feed | pat | stats | shop | buy <id> | equip <id> | unequip <slot> | name <이름> | dex | vacation [<일수>|end] | find | reset [--confirm] [종족] | setup | widget [on|off|install] | pr [on|off] | update]"
allowed-tools: Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pet.py" *)
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pet.py" $ARGUMENTS`

위 명령 출력을 그대로 보여줘. 해석하거나 요약하지 마.

- 출력이 `SETUP_PROMPT`로 시작하면: 사용자에게 settings.json에 statusLine을 추가해도 되는지 물어보고, 동의하면 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pet.py" setup --write` 를 실행해 결과를 보여줘.
- 출력이 `SETUP_EXISTS`로 시작하면: 기존 설정이 있다는 뜻이니 안내문만 보여주고 아무것도 바꾸지 마.
- 그 외에는 추가 명령을 실행하지 마.
