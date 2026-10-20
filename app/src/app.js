import { SPRITES, ITEMS, OWN_HEADWEAR } from "./sprites.js";

const T = window.__TAURI__;
const invoke = T.core.invoke;
const win = T.window.getCurrentWindow();
const LogicalSize = T.dpi.LogicalSize;
const LogicalPosition = T.dpi.LogicalPosition;

const SMALL = { w: 160, h: 160 };
const LARGE = { w: 360, h: 460 };
const HUNGER_PER_HOUR = 10, MOOD_PER_HOUR = 2, MOOD_PER_HOUR_STARVING = 4;
const SLOW_HUNGER_FORMS = new Set(["model", "scholar"]);
const FEED_COST = 50;                       // mirrors economy.FEED_COST; shop --json also reports it
const SLOT_KO = { head: "머리", face: "얼굴", body: "몸", room: "방" };

const $ = (id) => document.getElementById(id);
const SVG_NS = "http://www.w3.org/2000/svg";
let state = null;
let expanded = false;
let lastTurnAt = null;
let feedCost = FEED_COST;
let shop = null;          // last `pet shop --json` result while the dress panel is open

// ---------------------------------------------------------------- rendering

function spriteMarkup(s) {
  const form = SPRITES[s.form] ? s.form : "base";
  let items = "";
  const eq = s.equipped || {};
  for (const slot of ["room", "body", "face", "head"]) {
    const item = eq[slot];
    if (!item || !ITEMS[item]) continue;
    if (slot === "head" && OWN_HEADWEAR.has(form)) continue;
    if (form === "runaway") continue;
    items += ITEMS[item];
  }
  return { body: SPRITES[form], items };
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
  const key = m.body + m.items;
  if (key === lastMarkup) return;          // re-rendering every 10s must not reset the eyes
  lastMarkup = key;
  for (const id of ["sprite-small", "sprite-large"]) {
    const svg = $(id);
    svg.innerHTML = m.body;
    wrapEyes(svg);
    svg.insertAdjacentHTML("beforeend", m.items);
  }
}

function decayed(s) {
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

function render() {
  if (!state) return;
  const s = state;
  setSprite(spriteMarkup(s));
  $("sprite-small").setAttribute("aria-label", s.name);
  $("sprite-large").setAttribute("aria-label", s.name);
  $("coins-small").textContent = s.coins.toLocaleString();
  $("coins").textContent = s.coins.toLocaleString();
  $("name").textContent = s.name;
  $("level").textContent = `LV.${s.level}`;
  $("speech").textContent = s.speech || "…";
  $("speech").classList.remove("error");
  const { hunger, mood } = decayed(s);
  setMood(moodOf(s, hunger, mood));
  $("hunger-bar").style.width = `${hunger}%`;
  $("mood-bar").style.width = `${mood}%`;
  $("hunger-val").textContent = hunger.toFixed(1);
  $("mood-val").textContent = mood.toFixed(1);
  $("turn").textContent = `이번 턴 +${s.last_turn_earned || 0} 코인`;
  $("fed").textContent = `마지막 식사 ${ago(s.last_fed_at)}`;
  // Feeding is refused below the cost (loansharks borrow instead): grey the button out so a
  // click never looks like a no-op, and keep the cost visible in red.
  const short = s.form !== "loanshark" && s.coins < feedCost;
  $("feed").disabled = s.form === "runaway" || short;
  $("feed").classList.toggle("short", short);
  $("feed-cost").textContent = short ? `${s.coins}/${feedCost}` : `-${feedCost}`;
  if (shop) renderDress();

  if (s.last_turn_at && s.last_turn_at !== lastTurnAt) {
    const fresh = Date.now() - new Date(s.last_turn_at).getTime() < 5000;
    if (lastTurnAt !== null && fresh && s.last_turn_earned > 0) showEarn(s.last_turn_earned);
    lastTurnAt = s.last_turn_at;
  }
  if (lastLevel !== null && s.level > lastLevel) {
    fx("hop");
    burst("sparkle", 14);
    toast(`레벨 업! LV.${s.level}`);
  }
  lastLevel = s.level;
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
    el.classList.remove("fx-hop", "fx-shake", "fx-pop");
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
function showEarn(n) {
  const el = $("earn-bubble");
  el.textContent = `+${n}`;
  el.classList.remove("hidden");
  fx("hop", "small");
  pulse($("coins-small").parentElement);
  pulse($("coins").parentElement);
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
let expandedPos = null;           // where we put the expanded window

function savePos(p) {
  try { localStorage.setItem(POS_KEY, JSON.stringify({ x: Math.round(p.x), y: Math.round(p.y) })); } catch (e) {}
}
function loadPos() {
  try { return JSON.parse(localStorage.getItem(POS_KEY) || "null"); } catch (e) { return null; }
}

async function currentPos() {
  const pos = await win.outerPosition();
  const sf = await win.scaleFactor();
  return { x: pos.x / sf, y: pos.y / sf };
}

function monitorRect(m) {
  const sf = m.scaleFactor;
  return { x: m.position.x / sf, y: m.position.y / sf, w: m.size.width / sf, h: m.size.height / sf };
}

async function clampToMonitor(p, size) {
  try {
    const m = await win.currentMonitor();
    if (!m) return p;
    const r = monitorRect(m);
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
  try {
    // only if the saved spot is still on a connected screen (a monitor may have been unplugged)
    const mons = await T.window.availableMonitors();
    const visible = mons.map(monitorRect).some((r) =>
      p.x + SMALL.w > r.x + 20 && p.x < r.x + r.w - 20 && p.y + SMALL.h > r.y + 20 && p.y < r.y + r.h - 20);
    if (visible) await win.setPosition(new LogicalPosition(p.x, p.y));
  } catch (e) {}
}

const near = (a, b) => a && b && Math.abs(a.x - b.x) < 2 && Math.abs(a.y - b.y) < 2;

async function setExpanded(on) {
  if (on === expanded) return;
  expanded = on;
  try {
    const here = await currentPos();
    let target;
    if (on) {
      collapsedPos = here;
      target = await clampToMonitor(
        { x: here.x + SMALL.w - LARGE.w, y: here.y + SMALL.h - LARGE.h }, LARGE);
      expandedPos = target;
    } else {
      target = near(here, expandedPos)
        ? collapsedPos
        : await clampToMonitor({ x: here.x + LARGE.w - SMALL.w, y: here.y + LARGE.h - SMALL.h }, SMALL);
    }
    document.body.className = on ? "expanded" : "collapsed";
    const size = on ? LARGE : SMALL;
    await win.setSize(new LogicalSize(size.w, size.h));
    await win.setPosition(new LogicalPosition(target.x, target.y));
    if (!on) savePos(target);
  } catch (e) {
    document.body.className = on ? "expanded" : "collapsed";
  }
}

// Drag anywhere on the pet. A press that moves more than a few pixels hands the window to the OS
// (startDragging); a press that does not move is a click. Buttons and the item list stay clickable.
let press = null, dragged = false;
function makeDraggable(el) {
  el.addEventListener("mousedown", (e) => {
    if (e.button !== 0 || e.target.closest("button, .dress-list")) return;
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
    win.startDragging().catch(() => {});
  }
});
window.addEventListener("mouseup", () => { press = null; });

let saveTimer = null;
win.onMoved(() => {
  // remember where the user left the collapsed pet (programmatic moves while expanded are ignored)
  if (expanded) return;
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => { if (!expanded) savePos(await currentPos()); }, 300);
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

// ---------------------------------------------------------------- dress-up

async function openDress() {
  const res = await runPet(["shop"]);
  if (!res) return;
  shop = res.result;
  feedCost = shop.feed_cost || FEED_COST;
  $("dress-panel").classList.remove("hidden");
  renderDress();
}

function closeDress() {
  shop = null;
  $("dress-panel").classList.add("hidden");
}

function itemRow(it) {
  const li = document.createElement("li");
  li.className = "item" + (it.equipped ? " equipped" : "") + (!it.owned && !it.unlocked ? " locked" : "");
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("viewBox", "0 0 64 64");
  icon.setAttribute("class", "item-icon");
  icon.setAttribute("aria-hidden", "true");
  icon.innerHTML = ITEMS[it.id] || "";
  const meta = document.createElement("div");
  meta.className = "item-meta";
  const name = document.createElement("span");
  name.className = "item-name";
  name.textContent = it.name;
  const sub = document.createElement("span");
  sub.className = "item-sub";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn small";
  const slot = SLOT_KO[it.slot] || it.slot;
  if (it.owned) {
    sub.textContent = `${slot} · ${it.equipped ? "착용 중" : "보유"}`;
    btn.textContent = it.equipped ? "벗기" : "착용";
    btn.classList.add(it.equipped ? "ghost" : "mood");
    btn.addEventListener("click", () => dressAction(it.equipped ? ["unequip", it.slot] : ["equip", it.id]));
  } else if (!it.unlocked) {
    sub.textContent = `${slot} · Lv.${it.min_level} 해금`;
    btn.textContent = "잠김";
    btn.classList.add("ghost");
    btn.disabled = true;
  } else {
    const short = state.coins < it.price;
    sub.textContent = `${slot} · ${it.price}코인` + (short ? ` (${it.price - state.coins} 부족)` : "");
    sub.classList.toggle("short", short);
    btn.textContent = "구매";
    btn.classList.add("primary");
    btn.disabled = short;
    btn.addEventListener("click", () => dressAction(["buy", it.id]));
  }
  meta.append(name, sub);
  li.append(icon, meta, btn);
  return li;
}

function renderDress() {
  if (!shop || !state) return;
  $("coins-dress").textContent = state.coins.toLocaleString();
  const note = $("dress-note");
  if (shop.blocked) {
    note.textContent = "상점이 봉쇄됐어요. 지금은 살 수 없어요";
    note.classList.remove("hidden");
  } else {
    note.classList.add("hidden");
  }
  const list = $("dress-list");
  list.replaceChildren(...shop.catalog.map(itemRow));
}

async function dressAction(args) {
  for (const b of $("dress-list").querySelectorAll("button")) b.disabled = true;
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

$("collapse").addEventListener("click", () => { closeDress(); setExpanded(false); });
$("feed").addEventListener("click", feed);
$("dress").addEventListener("click", openDress);
$("dress-close").addEventListener("click", closeDress);
window.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (shop) closeDress(); else setExpanded(false);
});
window.addEventListener("blur", () => { if (expanded) { closeDress(); setExpanded(false); } });

T.event.listen("state", (ev) => { state = ev.payload; render(); });
setInterval(render, 10 * 1000);
scheduleBlink();
setInterval(() => { if (petMood === "sleep") burst("z", 1); }, 1800);   // bars visibly tick down between file updates
restorePos();
load();
