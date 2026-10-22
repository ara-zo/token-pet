// Widget-only lines, voiced per form like the plugin's speech_lines.py (missing forms fall back to base).
// The pet's everyday speech still comes from pet.py via state.speech; these cover what only the widget sees.

// PR mailbox. wait: the band while unread PRs sit there, review: the same when a review request
// is among them, fresh: the moment new ones arrive. {n} can be "99+", and the band is two short
// lines wide, so keep each line within about 16 characters.
const MAIL = {
  base: { wait: "안 읽은 PR {n}개 있어!", review: "리뷰 부탁 {n}개 왔어!", fresh: "새 PR {n}개 왔어!" },
  model: { wait: "PR {n}개 검토 대기 중", review: "리뷰 {n}건. 마감 지키자", fresh: "새 PR {n}건 접수 완료" },
  miser: { wait: "PR {n}개. 읽는 건 공짜", review: "리뷰 {n}개… 돈은 안 돼", fresh: "PR {n}개 왔어. 공짜지?" },
  owl: { wait: "PR {n}개… 밤에 읽자", review: "리뷰 {n}개. 밤샘각이야", fresh: "부엉! PR {n}개 왔어" },
  spender: { wait: "PR {n}개! 다 뜯어 봐", review: "리뷰 {n}개! 택배 같아", fresh: "택배 왔다! PR {n}개" },
  thug: { wait: "PR {n}개. 빨리 까라", review: "리뷰 {n}개. 안 하면 알지", fresh: "야. PR {n}개 왔다" },
  runaway: { wait: "(우편함에 PR {n}개…)", review: "(리뷰 요청 {n}개…)", fresh: "(빈 집에 PR {n}개)" },
  scholar: { wait: "PR {n}편 정독 대기", review: "리뷰 {n}건. 심사 들어가자", fresh: "새 PR {n}편 도착" },
  burnout: { wait: "PR {n}개… 나중에…", review: "리뷰 {n}개… 못 해…", fresh: "…PR {n}개 또 왔어" },
  tycoon: { wait: "PR {n}건 결재 대기", review: "리뷰 {n}건. 비서 없어?", fresh: "결재 서류 {n}건 도착" },
  loanshark: { wait: "PR {n}건 장부에 적음", review: "리뷰 {n}건. 이자 붙는다", fresh: "PR {n}건 입금 확인" },
  hunter: { wait: "PR {n}마리 포착", review: "리뷰 {n}마리. 사냥 가자", fresh: "사냥감 {n}마리 출현" },
  vampire: { wait: "PR {n}개… 해 지면 봐", review: "리뷰 {n}개… 피곤해", fresh: "어둠 속에 PR {n}개" },
  influencer: { wait: "DM {n}개 쌓였어!", review: "리뷰 {n}개! 피드백 각", fresh: "새 알림 {n}개!" },
  broke: { wait: "PR {n}개. 이건 공짜!", review: "리뷰 {n}개… 돈 되나?", fresh: "PR {n}개! 돈은 아니네" },
  boss: { wait: "PR {n}건. 처리해라", review: "리뷰 {n}건. 기다리게 마", fresh: "애들아, PR {n}건이다" },
};

export function mailLine(form, kind, n) {
  const own = (MAIL[form] || {})[kind] || MAIL.base[kind];
  return own.replace("{n}", n);
}

// Events the collapsed pet says out loud (the plugin's EVENT_TYPES_TO_SPEAK, plus level-ups). Most keep the
// plugin's text; the ones where the pet takes something from you are said in its own voice.
export const SPOKEN_EVENTS = new Set(["evolve", "runaway", "extort", "demand", "sold", "rehab", "born", "debt", "softcap", "levelup",
  "vacation_leave", "vacation_back", "vacation_early"]);
const VOICED = {
  extort: { thug: "{n}코인 걷어 간다. 토 달지 마.", boss: "{n}코인. 오늘 상납금이다." },
  debt: { loanshark: "이자 {n}코인 떼 간다. 장부 봐." },
};

export function eventLine(ev, form) {
  const own = (VOICED[ev.type] || {})[form];
  const n = (String(ev.text).match(/(\d+)코인/) || [])[1];
  return own && n ? own.replace("{n}", n) : ev.text;
}
