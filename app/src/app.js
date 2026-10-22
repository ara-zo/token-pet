import { SPRITES, ITEMS, OWN_HEADWEAR, hotelMarkup } from "./sprites.js";
import { BACKGROUNDS, BG_VIEWBOX } from "./backgrounds.js";
import { speciesMarkup, speciesInfo, itemOffset, formOwnsSlot, anchor, peeks } from "./species.js";
import { mailLine, eventLine, SPOKEN_EVENTS } from "./lines.js";

const T = window.__TAURI__;
const invoke = T.core.invoke;
const win = T.window.getCurrentWindow();
const LogicalSize = T.dpi.LogicalSize;
const LogicalPosition = T.dpi.LogicalPosition;

const SMALL = { w: 120, h: 156 };   // tall enough for a hat on the tallest species at full size
// The mail bubble and the talk bubble sit just above the pet's head (they may overlap each other).
// What they need above the head, in px; the window grows on top only by what the pet area lacks.
// Positions are always stored for the pet area (SMALL); the extra strip hangs above it.
const BAND = 87;
const MAIL_GAP = 20;                 // mail bubble bottom above the head: its 10px tail + 10px air
let bandOn = false;
const TALK = 54;
let talkOn = false;
let extra = 0;                       // px the collapsed window is currently grown by
let headFromBottom = 110;            // px from the drawn top of the pet to the window bottom
const bandH = () => extra;
const LARGE = { w: 300, h: 390 };
const HUNGER_PER_HOUR = 5, MOOD_PER_HOUR = 2, MOOD_PER_HOUR_STARVING = 4;
const SLOW_HUNGER_FORMS = new Set(["model", "scholar"]);
const FEED_COST = 50;                       // mirrors economy.FEED_COST; shop --json also reports it
const SLOT_KO = { head: "머리", face: "얼굴", body: "몸", room: "방", bg: "배경" };

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
let state = null;
let expanded = false;
let lastTurnAt = null;
let feedCost = FEED_COST;
let shop = null;          // last `pet shop --json` result while the dress panel is open
let dressTab = "wear";
let dex = null;            // last `pet dex --json` result, fetched when the 도감 tab opens    // "wear" (hats, clothes, room items) | "bg" (stage backgrounds)

// ---------------------------------------------------------------- rendering

// ---------------------------------------------------------------- vacation (토키 호텔)
// While the pet is away the widget shows the hotel with the pet asleep in its window; nothing decays.
const VAC = { fee: 20, max: 14, month: 20, options: [1, 3, 7, 14] };
const WEEKDAY_KO = "일월화수목금토";
let returning = false;              // the few hundred ms the pet hops out of the hotel, outfit still off
let lastAway = null;
let coinsBefore = null;             // to fly the early-return refund into the coin pill

function away(s = state) {
  return !!(s && s.vacation && Date.now() < new Date(s.vacation.until).getTime());
}
function vacUntil(s = state) { return new Date(s.vacation.until); }
function vacWhen(d) {
  return `${d.getMonth() + 1}/${d.getDate()}(${WEEKDAY_KO[d.getDay()]}) ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function vacD(s = state) {
  const a = vacUntil(s), b = new Date();
  const days = Math.round((new Date(a.getFullYear(), a.getMonth(), a.getDate()) - new Date(b.getFullYear(), b.getMonth(), b.getDate())) / 864e5);
  return days <= 0 ? "D-DAY" : `D-${days}`;
}
function vacRefund(s = state) {
  return Math.max(0, Math.floor((vacUntil(s).getTime() - Date.now()) / 864e5)) * VAC.fee;
}
function vacUsed(s = state) {
  const d = new Date(), key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  return ((s.settings || {}).vacation_days || {})[key] || 0;
}
// why a stay can't start (the same rules as petlib.vacation), or null
function vacBlock(s, days) {
  if (s.form === "thug" || s.form === "boss") return `${s.form === "thug" ? "불량배" : "조직 보스"}는 못 가요`;
  if (s.form === "runaway") return "가출 중";
  if (vacUsed(s) + days > VAC.month) return "한도 초과";
  if (s.coins < VAC.fee * days) return "코인 부족";
  return null;
}

function spriteMarkup(s) {
  if (away(s)) {
    const info = speciesInfo(s.species || "mochi");
    return { body: hotelMarkup(info ? info.color : undefined), items: "", grouped: true, wrap: "", whole: "",
      form: "vacation", kind: s.species || "mochi" };
  }
  const form = SPRITES[s.form] ? s.form : "base";
  const kind = s.species || "mochi";
  const eq = s.equipped || {};
  const sp = kind !== "mochi" ? speciesMarkup(kind, form) : null;
  let items = "", worn = "";
  for (const slot of ["room", "body", "face", "head"]) {
    const item = eq[slot];
    if (!item || !ITEMS[item] || form === "runaway" || returning) continue;
    if (!sp) {
      if (slot === "head" && OWN_HEADWEAR.has(form)) continue;
      items += ITEMS[item];
      continue;
    }
    // other species: clothes are cut for mochi's body, hats and glasses move to this head and eyes
    if (slot === "body" || formOwnsSlot(form, slot)) continue;
    const [dx, dy] = itemOffset(kind, slot) || [0, 0];
    const drawn = dx || dy ? `<g transform="translate(${dx} ${dy})">${ITEMS[item]}</g>` : ITEMS[item];
    if (slot === "room") items += drawn; else worn += drawn;
  }
  // a hat on the mole ducks into the hole with it (same clip and motion as its body)
  items += worn && sp && peeks(kind) && sp.markup.includes("tp-peek-clip")
    ? `<g clip-path="url(#tp-peek-clip)"><g class="m-peek">${worn}</g></g>` : worn;
  if (sp) return { body: sp.markup, items, grouped: true, wrap: sp.wrap, whole: sp.whole, form, kind };
  return { body: SPRITES[form], items, grouped: false, wrap: "", whole: "", form, kind };
}

// Form motions that need extra pixels (the "모션" board): drawn on both sprites, animated only on
// the stage. The collapsed pet shows species motion only.
function formOverlay(kind, form) {
  const a = anchor(kind), e = a.eye;
  const r = (x, y, w, h, c, cls) => `<rect class="fx-form ${cls}" x="${x}" y="${y}" width="${w}" height="${h}" fill="${c}"/>`;
  if (form === "burnout") {
    return r(a.cx - 8, a.hatY - 8, 4, 4, "#5F5B82", "f-smoke") + r(a.cx - 1, a.hatY - 12, 4, 4, "#5F5B82", "f-smoke d2")
      + r(a.cx + 6, a.hatY - 8, 4, 4, "#5F5B82", "f-smoke d4");
  }
  if (form === "boss") return r(e[0] - 2, e[1] - 1, 2, e[3] + 2, "#F4F1FF", "f-glint");
  if (form === "tycoon" || form === "influencer") {
    return r(4, 20, 3, 3, "#FFE59A", "f-spark") + r(56, 12, 3, 3, "#F4F1FF", "f-spark d2")
      + r(6, 44, 2, 2, "#F5C451", "f-spark d3") + r(57, 40, 3, 3, "#FFE59A", "f-spark d1");
  }
  if (form === "broke") {
    const [ix, iy] = a.item;
    return r(ix + 4, iy + 2, 3, 3, "#F5C451", "f-leak") + r(ix + 4, iy + 2, 3, 3, "#F5C451", "f-leak d2")
      + r(ix + 4, iy + 2, 2, 2, "#FFE59A", "f-leak d4");
  }
  return "";
}

// Eyes are the small filled rects on the eye line (y 34-38) of the body sprite. Grouping them lets
// CSS squash them for blinks and sleep. Items are added afterwards so sunglasses never blink.
function wrapEyes(svg) {
  const eyes = [...svg.querySelectorAll("rect")].filter((r) => {
    const y = +r.getAttribute("y"), h = +r.getAttribute("height"), w = +r.getAttribute("width");
    const fill = r.getAttribute("fill");
    return fill && fill !== "none" && y >= 34 && y <= 38 && h >= 2 && h <= 8 && w >= 2 && w <= 9;
  });
  if (!eyes.length) return;
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "eyes");
  eyes[0].before(g);
  g.append(...eyes);
}

let lastMarkup = null;
function setSprite(m) {
  const key = m.kind + m.form + m.body + m.items;
  if (key === lastMarkup) return;          // re-rendering every 10s must not reset the eyes
  lastMarkup = key;
  for (const id of ["sprite-small", "sprite-large"]) {
    const svg = $(id);
    svg.dataset.form = m.form;
    svg.dataset.species = m.kind;
    // one scale for every species (mochi's original 64-unit size), with headroom for antennas,
    // chimneys and a hat on a tall head
    svg.setAttribute("viewBox", "-4 -20 72 84");
    // everything sits in one group so form motions (sway, droop, nod) move the whole pet
    svg.innerHTML = `<g class="whole ${m.whole}"${m.wrap ? ` style="${m.wrap}"` : ""}>${m.body}</g>`;
    const whole = svg.querySelector(".whole");
    if (!m.grouped) wrapEyes(whole);
    whole.insertAdjacentHTML("beforeend", m.items + formOverlay(m.kind, m.form));
  }
  if (!expanded) { measureHead(); applyExtra(); } else placeSpeech();
}

// Where the head is decides where the bubbles go and how much the window must grow for them.
// Read from the drawing itself, not the screen, so a motion caught mid-way (the mole ducking, a hop)
// doesn't move the bubbles; passing effects (smoke, waves, flashes, form effects) and clip shapes don't count.
function measureHead() {
  const host = $("collapsed"), fx = $("fx-small"), svg = $("sprite-small");
  if (!host.offsetHeight) return;          // hidden (expanded): keep the last measurement
  const top = drawnTop(svg);
  if (top === null) return;
  // layout boxes, not screen rects: the bob and hop animations don't count
  const vb = svg.viewBox.baseVal, scale = svg.height.baseVal.value / vb.height;
  headFromBottom = host.offsetHeight - (fx.offsetTop + (top - vb.y) * scale);
}

const PASSING = /m-smoke|m-wave|e-|f-|fx-form/;
function drawnTop(svg) {
  let best = null;
  for (const el of svg.querySelectorAll("rect")) {
    if (PASSING.test(el.getAttribute("class") || "") || el.closest(".earn, clipPath")) continue;
    let y = parseFloat(el.getAttribute("y")) || 0;
    for (let g = el.parentElement; g && g !== svg; g = g.parentElement) {
      const m = /translate\(\s*[-\d.]+[ ,]+([-\d.]+)/.exec(g.getAttribute("transform") || "");
      if (m) y += parseFloat(m[1]);
    }
    if (best === null || y < best) best = y;
  }
  return best;
}

// The expanded speech bubble stays top-left on the stage; its tail hangs over the pet's head, and a short
// line widens the bubble just enough to reach it.
function placeSpeech() {
  const fx = $("fx-large"), svg = $("sprite-large"), el = $("speech");
  if (!$("stage").offsetHeight) return;
  const vb = svg.viewBox.baseVal, scale = svg.width.baseVal.value / vb.width;
  const head = fx.offsetLeft + (anchor(state ? state.species || "mochi" : "mochi").cx - vb.x) * scale;
  const x = Math.round(head - el.offsetLeft);
  el.style.minWidth = `${x + 14}px`;
  el.style.setProperty("--tail-x", `${x}px`);
}
new ResizeObserver(placeSpeech).observe($("speech"));

// Grow or shrink the strip above the collapsed pet to what the bubbles need, keeping the pet in place.
async function applyExtra() {
  const room = SMALL.h - headFromBottom;
  const need = (px) => Math.max(0, Math.ceil(px - room));
  const want = Math.max(bandOn ? need(BAND) : 0, talkOn ? need(TALK) : 0);
  $("collapsed").style.height = `${SMALL.h + want}px`;
  // "+N" at the head's top-right corner, in front of the mail bubble
  $("earn-bubble").style.bottom = `${Math.round(headFromBottom - 4)}px`;
  $("mail-small").style.bottom = `${Math.round(headFromBottom + MAIL_GAP)}px`;
  $("vac-badge").style.bottom = `${Math.round(headFromBottom - 30)}px`;
  if (want === extra) return;
  const diff = want - extra;
  extra = want;
  if (expanded) return;                    // applied when the widget collapses again
  try {
    const here = await currentPos();
    await win.setSize(new LogicalSize(SMALL.w, SMALL.h + want));
    await win.setPosition(new LogicalPosition(here.x, here.y - diff));
  } catch (e) {}
}

function decayed(s) {
  if (away(s)) return { hunger: s.hunger, mood: s.mood };     // time stands still at the hotel
  // mirror petlib.tick.decay so bars move between file updates
  const last = new Date(s.last_tick_at);
  const h = Math.max(0, (Date.now() - last.getTime()) / 36e5);
  const rate = HUNGER_PER_HOUR * (SLOW_HUNGER_FORMS.has(s.form) ? 0.7 : 1);
  const untilZero = rate > 0 ? s.hunger / rate : Infinity;
  const zeroHours = h > untilZero ? h - untilZero : 0;
  const hunger = Math.max(0, s.hunger - rate * h);
  const mood = Math.max(0, s.mood - MOOD_PER_HOUR * (h - zeroHours) - MOOD_PER_HOUR_STARVING * zeroHours);
  return { hunger, mood };
}

function ago(iso) {
  if (!iso) return "-";
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  if (h < 1) return `${Math.floor(h * 60)}분 전`;
  if (h < 48) return `${Math.floor(h)}시간 전`;
  return `${Math.floor(h / 24)}일 전`;
}

let lastBg = null;
function setBackground(id) {
  const key = BACKGROUNDS[id] ? id : "street";
  if (key === lastBg) return;
  lastBg = key;
  $("stage-bg").innerHTML = BACKGROUNDS[key];
}

function render() {
  if (!state) return;
  const s = state;
  const kind = s.species || "mochi";
  const samePet = lastSpecies === null || kind === lastSpecies;     // a switch is not an evolution
  if (lastForm !== null && s.form !== lastForm && !walkingOut && samePet) {
    if (s.form === "runaway") {
      walkOut();                         // packs up and walks off the screen, then the empty spot shows
    } else {
      formEvent(lastForm, s.form);
    }
  }
  lastForm = s.form;
  const isAway = away(s);
  if (lastAway !== null && lastAway !== isAway) vacationMove(isAway, s.coins - (coinsBefore ?? s.coins));
  lastAway = isAway;
  coinsBefore = s.coins;
  if (!walkingOut) setSprite(spriteMarkup(s));
  setBackground((s.equipped || {}).bg);
  $("sprite-small").setAttribute("aria-label", s.name);
  $("sprite-large").setAttribute("aria-label", s.name);
  $("coins-small").textContent = s.coins.toLocaleString();
  $("coins").textContent = s.coins.toLocaleString();
  $("name").textContent = s.name;
  fitText($("name"), 13, 10);
  $("level").textContent = `LV.${s.level}`;
  $("speech").textContent = s.speech || "…";
  $("speech").classList.remove("error");
  sayNewEvent(s);
  const { hunger, mood } = decayed(s);
  setMood(moodOf(s, hunger, mood));
  trayHunger = Math.round(hunger);
  updateTray();
  const fc = isAway ? null : s.forecast;
  const fcEl = $("forecast");
  fcEl.classList.toggle("hidden", !fc && !isAway);
  if (isAway) {
    const b = document.createElement("b");
    b.textContent = `${vacWhen(vacUntil(s))} 복귀`;
    fcEl.replaceChildren("휴가 중 · ", b, " · 진화 · 가출 멈춤");
    fcEl.title = "";
  } else if (fc) {
    fcEl.innerHTML = "";
    const b = document.createElement("b");
    b.textContent = `🔮 LV.${fc.at_level} ${fc.ko} 기운`;
    fcEl.append(b, ` · ${fc.reason}`);
    fcEl.title = `${fc.ko} 기운 · ${fc.reason}`;
  }
  $("hunger-bar").style.width = `${hunger}%`;
  $("mood-bar").style.width = `${mood}%`;
  $("hunger-val").textContent = isAway ? "고정" : hunger.toFixed(1);
  $("mood-val").textContent = isAway ? "고정" : mood.toFixed(1);
  document.body.classList.toggle("on-vacation", isAway);
  for (const id of ["vac-badge", "vac-badge-large"]) {
    $(id).classList.toggle("hidden", !isAway);
    if (isAway) $(id).textContent = vacD(s);
  }
  $("turn").textContent = isAway ? "공장 쉼 · 코인 안 쌓여요" : `이번 턴 +${s.last_turn_earned || 0} 코인`;
  $("fed").textContent = isAway ? `휴가 ${vacUsed(s)}/${VAC.month}일` : `마지막 식사 ${ago(s.last_fed_at)}`;
  // Feeding is refused below the cost (loansharks borrow instead): grey the button out so a
  // click never looks like a no-op, and keep the cost visible in red.
  const short = !isAway && s.form !== "loanshark" && s.coins < feedCost;
  $("dress").textContent = `${s.name}의 방`;
  $("feed").disabled = !isAway && (s.form === "runaway" || short);
  $("feed").classList.toggle("short", short);
  $("feed-label").textContent = isAway ? "일찍 데려오기" : "밥 주기";
  $("feed-cost").textContent = isAway ? `+${vacRefund(s)}` : short ? `${s.coins}/${feedCost}` : `-${feedCost}`;
  if (shop) renderDress();
  if (stats) renderStats();

  if (s.last_turn_at && s.last_turn_at !== lastTurnAt) {
    const fresh = Date.now() - new Date(s.last_turn_at).getTime() < 5000;
    if (lastTurnAt !== null && fresh && s.last_turn_earned > 0) showEarn(s.last_turn_earned);
    lastTurnAt = s.last_turn_at;
  }
  if (lastLevel !== null && s.level > lastLevel && samePet) {
    fx("hop");
    burst("sparkle", 14);
    toast(`레벨 업! LV.${s.level}`);
  }
  lastLevel = s.level;
  lastSpecies = kind;
  if (mailEnabled() !== mailOn) {           // turned on/off with /pet pr
    mailOn = mailEnabled();
    pollMail();
  }
}

// ---------------------------------------------------------------- animation

const NOCTURNAL = new Set(["owl", "vampire", "hunter"]);
const MOODS = ["mood-calm", "mood-happy", "mood-hungry", "mood-sleep", "mood-gone"];
let petMood = "calm";
let lastLevel = null;

function moodOf(s, hunger, mood) {
  if (s.form === "runaway") return "gone";
  const h = new Date().getHours();
  if (NOCTURNAL.has(s.form) && h >= 8 && h < 22) return "sleep";   // same "day" as petlib.clock.period
  if (hunger < 20) return "hungry";
  if (mood >= 70 && hunger >= 50) return "happy";
  return "calm";
}

function setMood(m) {
  petMood = m;
  for (const id of ["collapsed", "stage"]) {
    const el = $(id);
    el.classList.remove(...MOODS);
    el.classList.add(`mood-${m}`);
  }
}

// One-shot reaction on the sprite wrapper: "hop" | "shake" | "pop". where: "small" | "large" | both.
function fx(name, where) {
  const els = where ? [$(`fx-${where}`)] : [$("fx-small"), $("fx-large")];
  for (const el of els) {
    el.classList.remove("fx-hop", "fx-shake", "fx-pop", "fx-lookup", "fx-wiggle");
    void el.offsetWidth;                    // restart the animation if it is already running
    el.classList.add(`fx-${name}`);
    el.addEventListener("animationend", () => el.classList.remove(`fx-${name}`), { once: true });
  }
}

// Particles: "heart" floats up, "sparkle" bursts out, "z" drifts off a sleeping pet.
function burst(kind, n, where = expanded ? "large" : "small") {
  const layer = $(`particles-${where}`);
  for (let i = 0; i < n; i++) {
    const p = document.createElement("span");
    p.className = `particle ${kind}`;
    if (kind === "heart") p.textContent = "♥";
    if (kind === "z") p.textContent = "z";
    const a = (Math.PI * 2 * i) / n + Math.random() * 0.6;
    const r = 45 + Math.random() * 30;
    p.style.setProperty("--dx", kind === "sparkle" ? `${Math.cos(a) * r}px` : `${(Math.random() - 0.5) * 80}px`);
    p.style.setProperty("--dy", `${Math.sin(a) * r - 25}px`);
    p.style.setProperty("--d", `${kind === "sparkle" ? 0 : i * 0.09}s`);
    p.addEventListener("animationend", () => p.remove());
    layer.append(p);
  }
}

function pulse(el) {
  el.classList.remove("pulse");
  void el.offsetWidth;
  el.classList.add("pulse");
}

function flash(el) {
  el.classList.remove("flash");
  void el.offsetWidth;
  el.classList.add("flash");
}

function scheduleBlink() {
  setTimeout(() => {
    if (petMood !== "sleep" && petMood !== "gone") {
      const svgs = [$("sprite-small"), $("sprite-large")];
      const blink = (after) => {
        svgs.forEach((s) => s.classList.add("blink"));
        setTimeout(() => { svgs.forEach((s) => s.classList.remove("blink")); after && after(); }, 130);
      };
      // now and then a double blink
      blink(Math.random() < 0.2 ? () => setTimeout(() => blink(), 120) : null);
    }
    scheduleBlink();
  }, 2200 + Math.random() * 4200);
}

let earnTimer = null;
// Coins fly into the coin counter on every earn, collapsed or not (more coins for bigger turns).
// Collapsed: they pop out of the "+N" bubble, arc in front of the pet and drop into the coin pill.
// Expanded: they pop up from the pet and arc into the header's coin pill.
// The pet stretches up to watch them, then wiggles once the last one has landed.
// x and y are animated on two nested elements (linear x, gravity y) so the path is a parabola.
const COIN_SVG = '<svg viewBox="0 0 64 64" aria-hidden="true"><rect x="16" y="12" width="32" height="40" fill="#F5C451"/><rect x="12" y="16" width="40" height="32" fill="#F5C451"/><rect x="24" y="20" width="16" height="24" fill="#D9A33A"/><rect x="28" y="24" width="8" height="16" fill="#F5C451"/></svg>';
function coinRain(n) {
  const where = expanded ? "large" : "small";
  const layer = $(`coinfly-${where}`);
  const box = layer.getBoundingClientRect();
  const rel = (r) => ({ x: r.left - box.left + r.width / 2, y: r.top - box.top + r.height / 2 });
  const pill = expanded ? $("coins").parentElement : $("coins-small").parentElement;
  const icon = rel(pill.querySelector("svg").getBoundingClientRect());
  const from = expanded ? rel($("sprite-large").getBoundingClientRect()) : rel($("earn-bubble").getBoundingClientRect());
  const count = Math.min(6, Math.max(1, Math.round(Math.log2(n + 1))));
  const dur = expanded ? 0.75 : 0.85;
  for (let i = 0; i < count; i++) {
    const c = document.createElement("span");
    c.className = "coin-fly";
    c.innerHTML = `<span class="coin-y">${COIN_SVG}</span>`;
    const spread = (i - (count - 1) / 2) * (expanded ? 18 : 20);   // fan out sideways
    // each a different height, but never above the window's top edge (it would get cut off)
    const lift = Math.max((expanded ? -46 : -14) - (i % 3) * (expanded ? 16 : 12), 6 - from.y);
    c.style.setProperty("--x0", `${from.x + spread}px`);
    c.style.setProperty("--x1", `${icon.x}px`);
    c.style.setProperty("--y0", `${from.y}px`);
    c.style.setProperty("--y1", `${icon.y}px`);
    c.style.setProperty("--lift", `${lift}px`);
    c.style.setProperty("--d", `${i * 0.11}s`);
    c.style.setProperty("--dur", `${dur}s`);
    c.addEventListener("animationend", (e) => { if (e.target === c) c.remove(); });
    layer.append(c);
    setTimeout(() => pulse(pill), (i * 0.11 + dur) * 1000 - 40);   // a small bump per coin landing
  }
  fx("lookup", where);
  setTimeout(() => fx("wiggle", where), ((count - 1) * 0.11 + dur) * 1000);   // after the last coin lands
}

function showEarn(n) {
  const el = $("earn-bubble");
  el.textContent = `+${n}`;
  el.classList.remove("hidden");
  earning();
  coinRain(n);
  clearTimeout(earnTimer);
  earnTimer = setTimeout(() => el.classList.add("hidden"), 2000);
}

let toastTimer = null;
function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), 2500);
}

function speakError(msg) {
  const el = $("speech");
  el.textContent = msg;
  el.classList.add("error");
  fx("shake", expanded ? "large" : "small");
  setTimeout(render, 3000);
}

// ---------------------------------------------------------------- window

// Window position. The collapsed position is what the user chose by dragging; it is saved and
// restored on launch. Expanding grows the window up-left from the pet (bottom-right anchored) but is
// kept on screen; collapsing goes back to the exact collapsed spot unless the big window was moved.
const POS_KEY = "token-pet.position";
let collapsedPos = null;          // logical {x, y} of the collapsed window
let movedWhileExpanded = false;   // the user dragged the big window, so collapse where it now is

function savePos(p) {
  try { localStorage.setItem(POS_KEY, JSON.stringify({ x: Math.round(p.x), y: Math.round(p.y), size: SMALL.w, h: SMALL.h })); } catch (e) {}
}
function loadPos() {
  try { return JSON.parse(localStorage.getItem(POS_KEY) || "null"); } catch (e) { return null; }
}

async function currentPos() {
  const pos = await win.outerPosition();
  const sf = await win.scaleFactor();
  return { x: pos.x / sf, y: pos.y / sf };
}

function monitorRect(m, work = false) {
  // work area excludes the menu bar and Dock; macOS pushes windows out of the menu bar anyway
  const sf = m.scaleFactor;
  const a = work && m.workArea ? m.workArea : m;
  return { x: a.position.x / sf, y: a.position.y / sf, w: a.size.width / sf, h: a.size.height / sf };
}

async function clampToMonitor(p, size) {
  try {
    const m = await win.currentMonitor();
    if (!m) return p;
    const r = monitorRect(m, true);
    return {
      x: Math.min(Math.max(p.x, r.x), r.x + r.w - size.w),
      y: Math.min(Math.max(p.y, r.y), r.y + r.h - size.h),
    };
  } catch (e) {
    return p;
  }
}

async function restorePos() {
  const p = loadPos();
  if (!p || typeof p.x !== "number" || typeof p.y !== "number") return;
  // saved by an older build with a different pet size: keep the pet's bottom-right corner where it was
  const oldW = typeof p.size === "number" ? p.size : 160;
  const oldH = typeof p.h === "number" ? p.h : oldW;
  p.x += oldW - SMALL.w;
  p.y += oldH - SMALL.h;
  try {
    // only if the saved spot is still on a connected screen (a monitor may have been unplugged)
    const mons = await T.window.availableMonitors();
    const visible = mons.map(monitorRect).some((r) =>
      p.x + SMALL.w > r.x + 20 && p.x < r.x + r.w - 20 && p.y + SMALL.h > r.y + 20 && p.y < r.y + r.h - 20);
    if (visible) await win.setPosition(new LogicalPosition(p.x, p.y - bandH()));
  } catch (e) {}
}

// Long names shrink until they fit; only past the smallest size do they end in "…" (with a tooltip).
function fitText(el, max, min) {
  if (!el.clientWidth) return;              // hidden: fitted again when shown
  let px = max;
  el.style.fontSize = `${px}px`;
  while (px > min && el.scrollWidth > el.clientWidth) el.style.fontSize = `${--px}px`;
  el.title = el.scrollWidth > el.clientWidth ? el.textContent : "";
}

async function setExpanded(on) {
  if (on === expanded) return;
  expanded = on;
  const above = bandH();
  if (on) hideSay();                        // the expanded view shows the speech itself
  try {
    const here = await currentPos();
    let target, petArea;
    if (on) {
      collapsedPos = { x: here.x, y: here.y + above };            // the pet area, below any band
      movedWhileExpanded = false;
      target = await clampToMonitor(
        { x: here.x + SMALL.w - LARGE.w, y: collapsedPos.y + SMALL.h - LARGE.h }, LARGE);
    } else {
      // Not dragged: go back exactly where the pet was, whatever the OS did to the big window.
      petArea = !movedWhileExpanded && collapsedPos
        ? collapsedPos
        : await clampToMonitor({ x: here.x + LARGE.w - SMALL.w, y: here.y + LARGE.h - SMALL.h }, SMALL);
      target = { x: petArea.x, y: petArea.y - bandH() };
    }
    document.body.className = on ? "expanded" : "collapsed";
    if (on) { fitText($("name"), 13, 10); placeSpeech(); }
    const size = on ? LARGE : { w: SMALL.w, h: SMALL.h + bandH() };
    await win.setSize(new LogicalSize(size.w, size.h));
    await win.setPosition(new LogicalPosition(target.x, target.y));
    if (!on) savePos(petArea);
  } catch (e) {
    document.body.className = on ? "expanded" : "collapsed";
  }
}

// Drag anywhere on the pet. A press that moves more than a few pixels hands the window to the OS
// (startDragging); a press that does not move is a click. Buttons, inputs and the item list stay clickable.
let press = null, dragged = false;
function makeDraggable(el) {
  el.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || e.target.closest("button, input, .dress-list")) return;
    press = { x: e.screenX, y: e.screenY };
    dragged = false;
  });
}
window.addEventListener("mousemove", (e) => {
  if (!press) return;
  if (!(e.buttons & 1)) { press = null; return; }          // mouseup was swallowed by an earlier drag
  if (Math.abs(e.screenX - press.x) > 3 || Math.abs(e.screenY - press.y) > 3) {
    press = null;
    dragged = true;
    if (expanded) movedWhileExpanded = true;
    win.startDragging().catch(() => {});
  }
});
window.addEventListener("mouseup", () => { press = null; });

let saveTimer = null;
win.onMoved(() => {
  // remember where the user left the collapsed pet (programmatic moves while expanded are ignored)
  if (expanded) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    if (expanded) return;
    const p = await currentPos();
    savePos({ x: p.x, y: p.y + bandH() });
  }, 300);
}).catch(() => {});

// ---------------------------------------------------------------- actions

// Run a pet.py command. Refusals and failures surface in both the speech bubble and a toast,
// since a 3-second bubble alone was easy to miss. Returns the payload or null on failure.
async function runPet(args) {
  try {
    const res = await invoke("pet", { args });
    // state refresh arrives via the file watcher; apply the returned state eagerly too
    if (res.state) { state = { ...state, ...res.state }; }
    if (!res.ok) { speakError(res.text); toast(res.text); return null; }
    render();
    return res;
  } catch (e) {
    speakError(String(e)); toast(String(e));
    return null;
  }
}

async function feed() {
  if (away()) return vacationCmd("end");
  const btn = $("feed");
  btn.disabled = true;
  try {
    const res = await runPet(["feed"]);
    if (res) {
      toast(res.text);
      fx("hop", "large");
      burst("heart", 6, "large");
      flash($("hunger-bar"));
    }
  } finally {
    render();      // restores the disabled/short state from coins
  }
}

// ---------------------------------------------------------------- pat

async function patPet() {
  try {
    const res = await invoke("pet", { args: ["pat"] });
    if (res.state) state = { ...state, ...res.state };
    if (res.ok) {
      if (state.form === "thug" || state.form === "boss") {
        fx("shake", "large");            // slaps the hand away (motion board), but the mood still goes up
      } else {
        fx("hop", "large");
        burst("heart", 4, "large");
      }
      flash($("mood-bar"));
      render();
    }
    toast(res.text);                 // a refusal (daily limit) is gentle: no head shake
  } catch (e) {
    toast(String(e));
  }
}

// ---------------------------------------------------------------- event motions

let lastForm = null;
let lastSpecies = null;
let walkingOut = false;

// Coin in: species parts react (crystal grows, lamp, furnace, beak, cheeks).
function earning() {
  for (const id of ["sprite-small", "sprite-large"]) {
    const svg = $(id);
    svg.classList.remove("earning");
    void svg.getBoundingClientRect();
    svg.classList.add("earning");
    setTimeout(() => svg.classList.remove("earning"), 1400);
  }
}

// Evolution: the exchange's notice flies in and unfolds, a flash, then the new look.
// Rehab: the beanie gets thrown off.
function formEvent(from, to) {
  if (from === "thug" && to === "base") {
    burst("beanie", 1);
    toast("비니를 벗어 던졌다!");
    return;
  }
  fx("pop");
  burst("sparkle", 14);
  if (!expanded) return;
  const layer = $("particles-large");
  const note = document.createElement("div");
  note.className = "notice";
  note.innerHTML = "<b>환전소 통지서</b><span>배정 과정 안내</span>";
  const glare = document.createElement("div");
  glare.className = "flashover";
  note.addEventListener("animationend", () => note.remove());
  glare.addEventListener("animationend", () => glare.remove());
  layer.append(note, glare);
}

function walkOut() {
  walkingOut = true;
  for (const id of ["fx-small", "fx-large"]) $(id).classList.add("walk-out");
  setTimeout(() => {
    for (const id of ["fx-small", "fx-large"]) $(id).classList.remove("walk-out");
    walkingOut = false;
    lastMarkup = null;
    render();
  }, 1700);
}

// ---------------------------------------------------------------- menu bar
// The menu bar menu's two info lines follow the pet: name and level, coins, live hunger, unread PRs.

let trayHunger = 0;
let trayText = "";
function updateTray() {
  if (!state) return;
  const unread = mailEnabled() ? mail.items.filter((it) => !isRead(it)).length : 0;
  const title = `${state.name} · Lv.${state.level}`;
  const isAway = away();
  const detail = (isAway
    ? `${state.name} 휴가 중 · ${vacUntil().getMonth() + 1}/${vacUntil().getDate()} 복귀`
    : `코인 ${state.coins.toLocaleString()} · 배고픔 ${trayHunger}`) + (unread ? ` · 안 읽은 PR ${unread}` : "");
  const vacation = {
    away: isAway,
    back: isAway ? `일찍 데려오기 (${vacD()})` : "일찍 데려오기",
    options: VAC.options.map((d) => {
      const why = vacBlock(state, d);
      return { days: d, enabled: !why, label: `${d}일 · ${why || `${VAC.fee * d}코인`}` };
    }),
  };
  const key = title + detail + JSON.stringify(vacation);
  if (key === trayText) return;
  trayText = key;
  invoke("tray_status", { title, detail, vacation }).catch(() => {});
}

// "/pet vacation <days|end>" from the menu bar or the button; the answer's first line as a toast
async function vacationCmd(arg) {
  const res = await runPet(["vacation", String(arg)]);
  if (res) toast(res.text.split("\n")[0]);
}
T.event.listen("tray-vacation", (ev) => vacationCmd(ev.payload));

// Leaving: the pet hops and the hotel pops in. Coming back: the hotel shrinks away and the pet hops out,
// outfit off until the hop is over (design board: items come back after the motion).
function vacationMove(nowAway, refund) {
  if (nowAway) {
    fx("pop"); fx("pop", "large");
    return;
  }
  returning = true;
  fx("hop"); fx("hop", "large");
  burst("sparkle", 10);
  if (refund > 0) setTimeout(() => showEarn(refund), 300);
  setTimeout(() => { returning = false; lastMarkup = null; render(); }, 900);
}

// "업데이트 확인…" in the menu bar: the pet tells how it went
T.event.listen("tray-say", (ev) => {
  if (expanded) speakNote(ev.payload); else say(ev.payload, 8000);
});

// ---------------------------------------------------------------- PR mailbox
// PRs matching the GitHub search conditions the player typed into the mailbox ("가져오는 곳"), through
// gh (Rust `pr_inbox`), every 5 minutes, only after `/pet pr on`. A newly found PR makes the pet speak
// and hop; PRs already there when the mailbox (or a condition) was added only show in the bubble.

// Search conditions live only in this widget, like read marks. It starts empty: the player adds them.
const MAIL_SOURCES_KEY = "token-pet.pr.sources";
// { ids: {id: 1}, queries: [...] }: PRs already announced, and the conditions they were checked with
const MAIL_SEEN_KEY = "token-pet.pr.seen";
const REVIEW_QUERY = /\breview-requested:@me\b/;
const MAIL_LABEL = { review: "내 리뷰", open: "열린 PR" };
let mail = { items: [], counts: {}, errors: {}, error: null };
// "read" lives only in this widget: a PR I already looked at stops ringing, but stays listed
// (dimmed) until it no longer matches any condition (merged, closed, review done).
const MAIL_READ_KEY = "token-pet.pr.read";
let mailRead = new Set((() => { try { return JSON.parse(localStorage.getItem(MAIL_READ_KEY) || "[]"); } catch (e) { return []; } })());
function saveRead() { try { localStorage.setItem(MAIL_READ_KEY, JSON.stringify([...mailRead])); } catch (e) {} }
const isRead = (it) => mailRead.has(String(it.id));
let mailSources = (() => {
  try {
    const v = JSON.parse(localStorage.getItem(MAIL_SOURCES_KEY) || "null");
    if (Array.isArray(v)) return v.filter((q) => typeof q === "string");
  } catch (e) {}
  return [];
})();
function saveSources() { try { localStorage.setItem(MAIL_SOURCES_KEY, JSON.stringify(mailSources)); } catch (e) {} }
let mailOpen = false;
let mailOn = false;
let mailTab = "list";
let polling = null, pollAgain = false;

function mailEnabled() { return !!(state && state.settings && state.settings.pr_inbox); }

// "org:*** is:open" -> "is:pr org:*** is:open": without it GitHub mixes issues in
function normalizeQuery(raw) {
  const q = raw.trim().replace(/\s+/g, " ");
  if (!q) return "";
  return /(^|\s)(is|type):pr(\s|$)/.test(q) ? q : `is:pr ${q}`;
}

// one check at a time; a request during a check (a condition added or removed) runs once more after it
function pollMail() {
  if (polling) { pollAgain = true; return polling; }
  polling = doPollMail().finally(() => {
    polling = null;
    if (pollAgain) { pollAgain = false; pollMail(); }
  });
  return polling;
}

async function doPollMail() {
  if (!mailEnabled()) {
    // forget what was announced, so turning it on again starts quiet instead of ringing for everything
    try { localStorage.removeItem(MAIL_SEEN_KEY); } catch (e) {}
    mail = { items: [], counts: {}, errors: {}, error: null };
    renderMail();
    return;
  }
  const queries = [...mailSources];
  if (!queries.length) {
    mail = { items: [], counts: {}, errors: {}, error: null };
    renderMail();
    return;
  }
  let res;
  try {
    res = await invoke("pr_inbox", { queries });
  } catch (e) {
    mail = { ...mail, error: String(e) };
    renderMail();
    return;
  }
  // merge the conditions; a PR found by several shows once, as "내 리뷰" if any of them asked for my review
  const byId = new Map(), counts = {}, errors = {}, okQueries = [];
  for (const r of res.results || []) {
    if (!mailSources.includes(r.query)) continue;            // removed while this check was running
    counts[r.query] = r.items.length;
    if (r.error) { errors[r.query] = r.error; continue; }
    okQueries.push(r.query);
    const review = REVIEW_QUERY.test(r.query);
    for (const it of r.items) {
      const prev = byId.get(it.id);
      if (prev) { if (review) prev.category = "review"; continue; }
      byId.set(it.id, { ...it, category: review ? "review" : "open", query: r.query });
    }
  }
  // a condition that failed this time keeps its PRs from the last check instead of dropping them
  for (const it of mail.items) if (errors[it.query] && !byId.has(it.id)) byId.set(it.id, it);
  const items = [...byId.values()].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));

  let seen = null;
  try { seen = JSON.parse(localStorage.getItem(MAIL_SEEN_KEY) || "null"); } catch (e) {}
  if (!seen || !seen.ids) seen = null;                       // first run: nothing is "new"
  // only PRs from conditions that were already checked count as new, so adding a condition stays quiet
  const known = new Set(seen ? seen.queries : []);
  const fresh = seen ? items.filter((it) => !(it.id in seen.ids) && known.has(it.query)) : [];
  const ids = {};
  for (const it of items) ids[it.id] = 1;
  try { localStorage.setItem(MAIL_SEEN_KEY, JSON.stringify({ ids, queries: [...new Set([...okQueries, ...(seen ? seen.queries : [])])].filter((q) => mailSources.includes(q)) })); } catch (e) {}
  // forget read marks of PRs that left the list, so a PR that comes back rings again
  const live = new Set(items.map((it) => String(it.id)));
  for (const id of [...mailRead]) if (!live.has(id)) mailRead.delete(id);
  saveRead();
  mail = { items, counts, errors, error: null };
  renderMail();
  if (fresh.length) announceMail(fresh);
}

// No macOS notification: the pet says it and hops, and the bubble rings.
function announceMail(fresh) {
  speakNote(mailLine(state ? state.form : "base", "fresh", fresh.length));
  const badge = $("mail-small");
  badge.classList.remove("fresh");
  void badge.offsetWidth;
  badge.classList.add("fresh");
  fx("hop");
}

// The collapsed pet talks now and then: right away when something happens (a thug takes its cut,
// an evolution, a level-up), otherwise its current line every few minutes. The bubble sits above
// the pet's head, in a strip the window grows for it. The expanded view already shows the same speech.
let lastEventAt = null;
let sayTimer = null;
async function say(text, ms = 5000) {
  if (!text || expanded || walkingOut) return;
  clearTimeout(sayTimer);
  await setTalk(true);
  if (expanded) return;
  const el = $("say-small");
  $("say-text").textContent = text;
  el.classList.remove("hidden");
  // the tail sits just above whatever is drawn highest (a hat, ears), not the top of the sprite box
  measureHead();
  el.style.bottom = `${Math.round(headFromBottom + 9)}px`;
  el.style.animation = "none";
  void el.offsetWidth;
  el.style.animation = "";
  sayTimer = setTimeout(hideSay, ms);
}

function hideSay() {
  clearTimeout(sayTimer);
  $("say-small").classList.add("hidden");
  setTalk(false);
}

// Grow or drop the talk strip above the collapsed pet, keeping the pet where it is on screen.
async function setTalk(on) {
  if (on === talkOn) return;
  talkOn = on;
  $("collapsed").classList.toggle("with-talk", on);
  await applyExtra();
}

function sayNewEvent(s) {
  const evs = s.events || [];
  const newest = evs.length ? evs[evs.length - 1].at : "";
  if (lastEventAt !== null && newest !== lastEventAt) {
    const since = lastEventAt ? new Date(lastEventAt).getTime() : 0;
    const ev = evs.filter((e) => SPOKEN_EVENTS.has(e.type) && new Date(e.at).getTime() > since).pop();
    if (ev && Date.now() - new Date(ev.at).getTime() < 2 * 60 * 1000) say(eventLine(ev, s.form), 6000);
  }
  lastEventAt = newest;                    // nothing from before launch is said
}

function chatter() {
  if (state && !document.hidden) say(state.speech);
  setTimeout(chatter, (4 + Math.random() * 3) * 60 * 1000);
}

function speakNote(msg) {
  const el = $("speech");
  el.textContent = msg;
  el.classList.remove("error");
  setTimeout(render, 6000);
}

// Grow or drop the sentence band above the collapsed pet, keeping the pet where it is on screen.
async function setBand(on) {
  if (on === bandOn) return;
  bandOn = on;
  $("collapsed").classList.toggle("with-band", on);
  await applyExtra();
}

function renderMail() {
  const on = mailEnabled();
  const unread = mail.items.filter((it) => !isRead(it));      // only unread ones ring
  const n = unread.length;
  const reviews = unread.filter((it) => it.category === "review").length;
  $("mail-btn").classList.toggle("hidden", !on);
  $("mail-small").classList.toggle("hidden", !on || n === 0);
  $("mail-small").classList.toggle("review", reviews > 0);    // pink while a review request waits
  $("collapsed").classList.toggle("review", reviews > 0);
  $("mail-letter").classList.toggle("hidden", !on || n === 0);
  const shown = n > 99 ? "99+" : n;
  const full = mailLine(state ? state.form : "base", reviews > 0 ? "review" : "wait", shown);
  $("mail-count-small").textContent = full;
  $("mail-small").setAttribute("aria-label", `PR 우편함 열기, ${full}`);
  setBand(on && n > 0);
  updateTray();
  $("mail-count").textContent = n > 99 ? "99+" : String(n);
  $("mail-count").classList.toggle("hidden", n === 0);
  if (!mailOpen) return;

  const listTab = mailTab === "list";
  $("mail-tab-list").setAttribute("aria-selected", String(listTab));
  $("mail-tab-src").setAttribute("aria-selected", String(!listTab));
  $("mail-tab-list").textContent = `PR ${mail.items.length}`;
  $("mail-tab-src").textContent = `가져오는 곳 ${mailSources.length}`;
  $("mail-readall").classList.toggle("hidden", !listTab);
  $("mail-readall").disabled = n === 0;
  $("mail-list").classList.toggle("hidden", !listTab);
  $("mail-src").classList.toggle("hidden", listTab);
  const failed = Object.keys(mail.errors).length;
  const note = $("mail-note");
  note.textContent = mail.error || (listTab && failed ? `조건 ${failed}개를 검색하지 못했어요. 가져오는 곳 탭을 봐 주세요` : "");
  note.classList.toggle("hidden", !note.textContent);
  if (listTab) renderMailList(); else renderSources();
}

function renderMailList() {
  if (!mail.items.length) {
    const li = document.createElement("li");
    li.className = "mail-empty";
    li.textContent = mail.error ? "" : mailSources.length ? "조건에 맞는 PR이 없어요" : "가져오는 곳 탭에서 검색 조건을 추가해 주세요";
    $("mail-list").replaceChildren(li);
    return;
  }
  $("mail-list").replaceChildren(...mail.items.map((it) => {
    const li = document.createElement("li");
    li.className = "item mail-item" + (isRead(it) ? " read" : "");
    li.tabIndex = 0;
    li.setAttribute("role", "link");
    const chip = document.createElement("span");
    chip.className = `mail-chip ${it.category}`;
    chip.textContent = isRead(it) ? "읽음" : MAIL_LABEL[it.category];
    const meta = document.createElement("div");
    meta.className = "item-meta";
    const title = document.createElement("span");
    title.className = "item-name";
    title.textContent = it.title;
    const sub = document.createElement("span");
    sub.className = "item-sub";
    sub.textContent = `${it.repo}${it.number ? ` #${it.number}` : ""}${it.draft ? " · 초안" : ""}`;
    meta.append(title, sub);
    li.append(chip, meta);
    const go = () => openMail(it);
    li.addEventListener("click", go);
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
    return li;
  }));
}

function renderSources() {
  if (!mailSources.length) {
    const li = document.createElement("li");
    li.className = "mail-empty";
    li.textContent = "예: is:pr org:*** is:open";
    $("mail-src-list").replaceChildren(li);
    return;
  }
  $("mail-src-list").replaceChildren(...mailSources.map((q) => {
    const li = document.createElement("li");
    li.className = "item src-item";
    const meta = document.createElement("div");
    meta.className = "item-meta";
    const name = document.createElement("span");
    name.className = "src-query";
    name.textContent = q;
    name.title = q;
    const sub = document.createElement("span");
    const err = mail.errors[q];
    sub.className = "item-sub" + (err ? " short" : "");
    sub.textContent = err || (q in mail.counts ? `PR ${mail.counts[q]}개${mail.counts[q] >= 50 ? " · 50개까지만 보여요" : ""}` : "확인 중…");
    meta.append(name, sub);
    const del = document.createElement("button");
    del.type = "button";
    del.className = "icon-btn src-del";
    del.textContent = "×";
    del.setAttribute("aria-label", `${q} 빼기`);
    del.addEventListener("click", () => removeSource(q));
    li.append(meta, del);
    return li;
  }));
}

function addSource(e) {
  e.preventDefault();
  const input = $("mail-src-input");
  const q = normalizeQuery(input.value);
  if (!q) return;
  if (mailSources.includes(q)) { toast("이미 있는 조건이에요"); return; }
  mailSources.push(q);
  saveSources();
  input.value = "";
  renderMail();
  pollMail();
}

function removeSource(q) {
  mailSources = mailSources.filter((x) => x !== q);
  saveSources();
  // drop its PRs right away; ones another condition also finds come back on the next check
  mail = { ...mail, items: mail.items.filter((it) => it.query !== q) };
  delete mail.errors[q];
  renderMail();
  pollMail();
}

// open the PR in the browser and mark it read; it leaves the list once it no longer matches (next check)
function openMail(it) {
  invoke("open_url", { url: it.url }).catch((e) => toast(String(e)));
  mailRead.add(String(it.id));
  saveRead();
  renderMail();
}

function readAllMail() {
  for (const it of mail.items) mailRead.add(String(it.id));
  saveRead();
  renderMail();
  toast("PR을 모두 읽음으로 표시했어요");
}

function showMailTab(tab) {
  mailTab = tab;
  renderMail();
  if (tab === "src") $("mail-src-input").focus();
}

function openMailbox() {
  closeDress();
  closeStats();
  mailOpen = true;
  if (!mailSources.length) mailTab = "src";           // nothing to fetch yet: start where conditions are added
  $("expanded").classList.add("panel-open");
  $("mail-panel").classList.remove("hidden");
  renderMail();
  pollMail();
}

function closeMailbox() {
  mailOpen = false;
  $("mail-panel").classList.add("hidden");
  $("expanded").classList.remove("panel-open");
}

// ---------------------------------------------------------------- stats

let stats = null;   // last `pet stats --json` result while the panel is open
const W_CHART = 268;
const WEEKDAY = ["일", "월", "화", "수", "목", "금", "토"];

async function openStats() {
  closeDress();
  closeMailbox();
  const res = await runPet(["stats"]);
  if (!res) return;
  stats = res.result;
  $("expanded").classList.add("panel-open");
  $("stats-panel").classList.remove("hidden");
  renderStats();
}

function closeStats() {
  stats = null;
  $("stats-panel").classList.add("hidden");
  $("chart-tip").classList.add("hidden");
  $("expanded").classList.remove("panel-open");
}

function svgEl(tag, attrs) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

// Single series (coins earned per day): no legend, the panel title names it. Bars <= 24px,
// 4px rounded top, square at the baseline; today's value is labelled, the rest on hover.
function renderStats() {
  if (!stats) return;
  const days = stats.days, t = stats.total, today = days[days.length - 1];
  const hasIn = today.tokens_in != null;   // older plugins send output only
  fillRows($("stats-today"), [
    ["오늘 획득", `+${today.earned.toLocaleString()}`, "coin"],
    [hasIn ? "출력 · 입력" : "출력 토큰",
      kTokens(today.tokens_out) + (hasIn ? ` · ${kTokens(today.tokens_in)}` : "")],
    ["밥 · 쓰다듬기", `${today.feeds} · ${today.pats}`],
  ]);
  $("stats-total").textContent =
    `7일 합계 +${t.earned.toLocaleString()}코인 · 사용 ${t.spent.toLocaleString()} · 밥 ${t.feeds}번`;

  const svg = $("stats-chart");
  svg.replaceChildren();
  const W = W_CHART, top = 14, base = 64, slot = W / days.length, bw = 18;
  const max = Math.max(1, ...days.map((d) => d.earned));
  svg.append(svgEl("line", { class: "base", x1: 0, x2: W, y1: base + 0.5, y2: base + 0.5 }));
  days.forEach((d, i) => {
    const cx = slot * i + slot / 2;
    const g = svgEl("g", { class: "slot" });
    const h = d.earned > 0 ? Math.max(3, ((base - top) * d.earned) / max) : 2;
    const x = cx - bw / 2, y = base - h, r = Math.min(4, h);
    const path = d.earned > 0
      ? `M${x},${base} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${base} Z`
      : `M${x},${base} V${base - 2} H${x + bw} V${base} Z`;
    g.append(svgEl("path", { class: d.earned > 0 ? "bar" : "bar empty", d: path }));
    const isToday = i === days.length - 1;
    const wd = WEEKDAY[new Date(`${d.date}T00:00:00`).getDay()];
    const label = svgEl("text", { class: isToday ? "day today" : "day", x: cx, y: base + 15 });
    label.textContent = isToday ? "오늘" : wd;
    g.append(label);
    if (isToday && d.earned > 0) {
      const v = svgEl("text", { class: "val", x: cx, y: y - 4 });
      v.textContent = d.earned.toLocaleString();
      g.append(v);
    }
    const hit = svgEl("rect", { class: "hit", x: slot * i, y: 0, width: slot, height: 84 });
    hit.addEventListener("mouseenter", () => showTip(d, cx, wd, isToday));
    hit.addEventListener("mouseleave", () => $("chart-tip").classList.add("hidden"));
    g.append(hit);
    svg.append(g);
  });
}

// 1234 -> "1.2k", 88000 -> "88k", 2500000 -> "2.5M"
function kTokens(n) {
  if (n < 1000) return n.toLocaleString();
  if (n >= 1e6) return `${+(n / 1e6).toFixed(1)}M`;
  const k = n / 1000;
  return `${k >= 100 ? Math.round(k) : +k.toFixed(1)}k`;
}

// <dl> of label/value rows
function fillRows(dl, rows) {
  dl.replaceChildren();
  for (const [label, value, cls] of rows) {
    const row = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value;
    if (cls) dd.className = cls;
    row.append(dt, dd);
    dl.append(row);
  }
}

function showTip(d, cx, wd, isToday) {
  const tip = $("chart-tip");
  const [, m, day] = d.date.split("-");
  tip.textContent = `${+m}/${+day} ${isToday ? "오늘" : wd} · +${d.earned.toLocaleString()}코인 · 출력 ${d.tokens_out.toLocaleString()} · 밥 ${d.feeds}`;
  tip.style.left = `${Math.min(Math.max(cx, 110), W_CHART - 110)}px`;   // keep the bubble inside the panel
  tip.classList.remove("hidden");
}

// ---------------------------------------------------------------- room
// "{name}의 방" takes the whole expanded window: 밥 · 상점 · 옷장 · 배경 · 도감. Items are cards in a
// grid; picking one fills the single action button at the bottom (구매 / 착용 / 벗기).

let roomSel = {};                     // tab -> selected item id

async function openDress() {
  closeStats();
  closeMailbox();
  const res = await runPet(["shop"]);
  if (!res) return;
  shop = res.result;
  feedCost = shop.feed_cost || FEED_COST;
  dressTab = "wear";
  roomSel = {};
  $("expanded").classList.add("room-open");
  $("dress-panel").classList.remove("hidden");
  renderDress();
}

function closeDress() {
  shop = null;
  $("dress-panel").classList.add("hidden");
  $("expanded").classList.remove("room-open");
}

// which catalog items each tab shows
function roomItems() {
  const wear = shop.catalog.filter((it) => it.slot !== "bg");
  if (dressTab === "wear") return wear.filter((it) => !it.owned);
  if (dressTab === "closet") return wear.filter((it) => it.owned);
  if (dressTab === "bg") return shop.catalog.filter((it) => it.slot === "bg");
  return [];
}

function cardSub(it) {
  if (it.owned) return it.equipped ? [it.slot === "bg" ? "사용 중" : "착용 중", "on"] : ["보유", "on"];
  if (!it.unlocked) return [it.grant ? "특별" : `LV.${it.min_level}`, "lock"];
  return [String(it.price), ""];
}

function itemCard(it, selected) {
  const li = document.createElement("li");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "card" + (selected ? " selected" : "") + (!it.owned && !it.unlocked ? " locked" : "");
  btn.setAttribute("aria-pressed", String(selected));
  const isBg = it.slot === "bg";
  const icon = document.createElementNS(SVG_NS, "svg");
  icon.setAttribute("viewBox", isBg ? BG_VIEWBOX : "0 0 64 64");
  icon.setAttribute("preserveAspectRatio", "xMidYMid slice");
  icon.setAttribute("class", isBg ? "card-icon bg" : "card-icon");
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = (isBg ? BACKGROUNDS[it.id] : ITEMS[it.id]) || "";
  const name = document.createElement("span");
  name.className = "card-name";
  name.textContent = it.name;
  const [text, tone] = cardSub(it);
  const sub = document.createElement("span");
  sub.className = "card-sub" + (tone ? ` ${tone}` : "");
  sub.textContent = text;
  btn.title = `${it.name} · ${SLOT_KO[it.slot] || it.slot}` + (!it.owned && !it.unlocked && it.grant ? ` · ${it.grant}` : "");
  btn.append(icon, name, sub);
  btn.addEventListener("click", () => { roomSel[dressTab] = it.id; renderDress(); });
  li.append(btn);
  return li;
}

// the bottom button for the picked item: [label, args or null, ghost?]
function roomAction(it) {
  if (!it) return ["골라 주세요", null, false];
  if (it.owned) {
    if (away()) return ["복귀하면 할 수 있어요", null, true];
    if (it.slot === "bg") return it.equipped ? ["사용 중", null, true] : ["이 배경 쓰기", ["equip", it.id], false];
    return it.equipped ? [`${it.name} 벗기`, ["unequip", it.slot], true] : [`${it.name} 입히기`, ["equip", it.id], false];
  }
  if (!it.unlocked) return [it.grant || `Lv.${it.min_level}에 열려요`, null, true];
  if (shop.blocked) return ["상점이 봉쇄됐어요", null, true];
  if (state.coins < it.price) return [`${(it.price - state.coins).toLocaleString()}코인 부족`, null, true];
  return [`${it.name} 구매 -${it.price}`, ["buy", it.id], false];
}

function setRoomAction(label, onClick, ghost) {
  const btn = $("room-action");
  btn.classList.remove("hidden");
  btn.textContent = label;
  btn.classList.toggle("ghost", !!ghost);
  btn.classList.toggle("primary", !ghost);
  btn.disabled = !onClick;
  btn.onclick = onClick;
}

function renderDress() {
  if (!shop || !state) return;
  $("room-title").textContent = `${state.name}의 방`;
  fitText($("room-title"), 15, 11);
  $("coins-dress").textContent = state.coins.toLocaleString();
  for (const tab of document.querySelectorAll(".tabs .tab")) {
    tab.setAttribute("aria-selected", String(tab.dataset.tab === dressTab));
  }
  const note = $("dress-note");
  note.classList.remove("hint");
  note.classList.toggle("hidden", !(shop.blocked && dressTab === "wear"));
  note.textContent = "상점이 봉쇄됐어요. 지금은 살 수 없어요";
  const list = $("dress-list");
  const food = dressTab === "food";
  list.classList.toggle("hidden", food);
  $("room-food").classList.toggle("hidden", !food);
  if (food) { renderFood(); return; }
  if (dressTab === "dex") {
    list.classList.remove("grid", "wide");
    $("room-action").classList.add("hidden");
    renderDex();
    return;
  }
  list.classList.add("grid");
  list.classList.toggle("wide", dressTab === "bg");
  const items = roomItems();
  let sel = items.find((it) => it.id === roomSel[dressTab]);
  if (!sel) sel = items.find((it) => it.equipped) || items.find((it) => it.unlocked || it.owned) || items[0];
  if (sel) roomSel[dressTab] = sel.id;
  if (!items.length) {
    const li = document.createElement("li");
    li.className = "room-empty";
    li.textContent = dressTab === "closet" ? "아직 산 게 없어요. 상점에서 골라 보세요" : "더 살 게 없어요. 옷장에서 입혀 보세요";
    list.replaceChildren(li);
  } else {
    list.replaceChildren(...items.map((it) => itemCard(it, it === sel)));
  }
  const [label, args, ghost] = roomAction(sel);
  setRoomAction(label, args ? () => dressAction(args) : null, ghost);
}

function renderFood() {
  // the same live value as the main bars (they tick down between file updates)
  $("room-hunger-bar").style.width = $("hunger-bar").style.width;
  $("room-hunger-val").textContent = $("hunger-val").textContent;
  $("room-fed").textContent = $("fed").textContent;
  const short = state.coins < feedCost;
  const gone = state.form === "runaway" || away();
  const label = away() ? "복귀하면 할 수 있어요" : gone ? "펫이 집을 나갔어요" : short ? `${(feedCost - state.coins).toLocaleString()}코인 부족` : `밥 주기 -${feedCost}`;
  setRoomAction(label, gone || short ? null : async () => { await feed(); renderDress(); }, gone || short);
}

async function openDexTab() {
  const res = await runPet(["dex"]);
  if (res) dex = res.result;
  renderDress();
}

// 도감: every species with its base look. Owned pets can be brought back, registered ones adopted,
// locked ones are silhouettes with the condition and progress.
function renderDex() {
  const note = $("dress-note");
  note.textContent = "쉬는 펫은 상태가 멈춘 채 기다려요. 코인은 다 같이 써요";
  note.title = "";
  note.classList.remove("hidden");
  note.classList.add("hint");
  if (!dex) { $("dress-list").replaceChildren(); return; }
  $("dress-list").replaceChildren(...dex.species.map((sp) => {
    const li = document.createElement("li");
    li.className = "item dex" + (sp.current ? " equipped" : "") + (sp.unlocked ? "" : " locked");
    const icon = document.createElementNS(SVG_NS, "svg");
    icon.setAttribute("viewBox", "-4 -6 72 72");
    icon.setAttribute("class", "item-icon" + (sp.unlocked ? "" : " silhouette"));
    icon.setAttribute("aria-hidden", "true");
    icon.innerHTML = sp.id === "mochi" ? SPRITES.base : speciesMarkup(sp.id, "base").markup;
    const meta = document.createElement("div");
    meta.className = "item-meta";
    const name = document.createElement("span");
    name.className = "item-name";
    name.textContent = sp.name;
    const sub = document.createElement("span");
    sub.className = "item-sub";
    if (sp.current) sub.textContent = `${sp.part} · 지금 돌보는 중`;
    else if (sp.resting) sub.textContent = `쉬는 중 · ${sp.resting.name} Lv.${sp.resting.level}`;
    else if (sp.unlocked) sub.textContent = `입양 가능 · ${sp.adopt_cost ? `${sp.adopt_cost.toLocaleString()}코인` : "무료"}`;
    else {
      sub.textContent = `“${sp.hint}”`;           // a rumor, not the rule: unlocking stays a surprise
      sub.classList.add("rumor");
    }
    if (sp.unlocked && !sp.current) li.title = `만난 계기: ${sp.condition}`;
    meta.append(name, sub);
    let end;
    if (sp.current) {
      end = document.createElement("span");
      end.className = "dex-tag";
      end.textContent = "돌보는 중";
    } else if (sp.owned) {
      end = document.createElement("button");
      end.type = "button";
      end.className = "btn small mood";
      end.textContent = "데려오기";
      end.addEventListener("click", () => rosterAction(["switch", sp.id]));
    } else if (sp.unlocked) {
      const short = state.coins < sp.adopt_cost;
      end = document.createElement("button");
      end.type = "button";
      end.className = "btn small primary";
      end.textContent = "입양";
      end.disabled = short;
      if (short) sub.textContent += ` (${(sp.adopt_cost - state.coins).toLocaleString()} 부족)`;
      sub.classList.toggle("short", short);
      end.addEventListener("click", () => rosterAction(["adopt", sp.id]));
    } else {
      end = document.createElement("span");
      end.className = `dex-sign s${sp.sign}`;
      end.textContent = "●".repeat(sp.sign + 1) + "○".repeat(2 - sp.sign);
      end.title = sp.sign_text;
      end.setAttribute("aria-label", sp.sign_text);
    }
    li.append(icon, meta, end);
    return li;
  }));
}

// adopt / switch: the result carries the fresh dex, the state carries the pet now on stage
async function rosterAction(args) {
  for (const b of $("dress-list").querySelectorAll("button")) b.disabled = true;
  const res = await runPet(args);
  if (res) {
    dex = res.result;
    toast(res.text);
    fx("pop");
    burst(args[0] === "adopt" ? "heart" : "sparkle", 8);
    const fresh = await runPet(["shop"]);           // owned/equipped flags follow the new pet
    if (fresh) shop = fresh.result;
  }
  renderDress();
}

async function dressAction(args) {
  for (const b of $("dress-list").querySelectorAll("button")) b.disabled = true;
  $("room-action").disabled = true;
  const res = await runPet(args);
  if (res) {
    toast(res.text.split("\n")[0]);
    fx("pop", "large");
    burst("sparkle", 12, "large");
    // re-read the shop so owned/equipped/unlocked flags come from the single source of truth
    const fresh = await runPet(["shop"]);
    if (fresh) shop = fresh.result;
  }
  renderDress();
}

async function load() {
  try {
    state = await invoke("read_state");
    render();
  } catch (e) {
    $("speech").textContent = String(e);
    $("sprite-small").innerHTML = SPRITES.base;
  }
}

// ---------------------------------------------------------------- wiring

makeDraggable($("collapsed"));
makeDraggable($("expanded"));
$("collapsed").addEventListener("click", () => {
  if (dragged) { dragged = false; return; }       // the press was a drag, not a click
  setExpanded(true);
});

$("collapse").addEventListener("click", () => { closeDress(); closeStats(); closeMailbox(); setExpanded(false); });
$("feed").addEventListener("click", feed);
$("dress").addEventListener("click", openDress);
$("dress-close").addEventListener("click", closeDress);
for (const tab of document.querySelectorAll(".tabs .tab")) {
  tab.addEventListener("click", () => {
    dressTab = tab.dataset.tab;
    $("dress-list").scrollTop = 0;
    if (dressTab === "dex") openDexTab(); else renderDress();
  });
}
$("stats-btn").addEventListener("click", () => (stats ? closeStats() : openStats()));
$("stats-close").addEventListener("click", closeStats);
$("fx-large").addEventListener("click", () => {
  if (dragged) { dragged = false; return; }       // the press was a drag
  patPet();
});
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (shop) closeDress(); else if (stats) closeStats(); else if (mailOpen) closeMailbox(); else setExpanded(false);
});
window.addEventListener("blur", () => { if (expanded) { closeDress(); closeStats(); closeMailbox(); setExpanded(false); } });

T.event.listen("state", (ev) => { state = ev.payload; render(); });
$("mail-btn").addEventListener("click", () => (mailOpen ? closeMailbox() : openMailbox()));
$("mail-close").addEventListener("click", closeMailbox);
$("mail-readall").addEventListener("click", readAllMail);
$("mail-tab-list").addEventListener("click", () => showMailTab("list"));
$("mail-tab-src").addEventListener("click", () => showMailTab("src"));
$("mail-src-form").addEventListener("submit", addSource);
$("mail-small").addEventListener("click", (e) => {
  e.stopPropagation();                      // don't also count as a click on the pet
  if (dragged) { dragged = false; return; }
  setExpanded(true).then(openMailbox);
});
setInterval(pollMail, 5 * 60 * 1000);
// while mail waits, every 10 s the bubble rings and the pet hops (collapsed only)
setInterval(() => {
  if (!bandOn || expanded) return;
  const b = $("mail-small");
  b.classList.remove("ring", "fresh");
  void b.offsetWidth;
  b.classList.add("ring");
  fx("hop", "small");
}, 10 * 1000);
setInterval(render, 10 * 1000);
scheduleBlink();
setTimeout(chatter, 2 * 60 * 1000);
setInterval(() => { if (petMood === "sleep") burst("z", 1); }, 1800);   // bars visibly tick down between file updates
restorePos();
load();
