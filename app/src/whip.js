// 채찍질: the whip follows the mouse over the whole screen (this transparent window, opened by `whip_open`).
// A rope of points with fixed lengths (Verlet), the handle on the cursor. A fast snap of the tip cracks;
// a fast part of the lash sweeping through the pet (its box comes from the main window) is a hit, which the
// main window answers with the pet's reaction. A click or Esc puts the whip down.

const T = window.__TAURI__;
const win = T.window.getCurrentWindow();
const cv = document.getElementById("cv");
const ctx = cv.getContext("2d");

const N = 26, SEG = 11, GRAVITY = 0.45, DAMP = 0.985;
const CRACK_SPEED = 20, HIT_SPEED = 4, CRACK_GAP = 300, HIT_GAP = 400, HIT_PAD = 16;
let mouse = null;                     // no whip drawn until the mouse moves
let pts = [];
let pet = null;                       // the pet's box in this window's coordinates
let origin = { x: 0, y: 0 };
let lastCrack = 0, lastHit = 0;
let star = null;

function resize() {
  const r = window.devicePixelRatio || 1;
  cv.width = innerWidth * r;
  cv.height = innerHeight * r;
  ctx.setTransform(r, 0, 0, r, 0, 0);
}
addEventListener("resize", resize);
resize();

// The window is hidden, not closed, when the whip is put down; each time it is shown again it starts fresh
// on whichever screen the cursor is on.
async function start() {
  mouse = null;
  pts = [];
  star = null;
  pet = null;
  down = false;
  const hint = document.querySelector(".hint");
  hint.style.animation = "none"; void hint.offsetWidth; hint.style.animation = "";
  try {
    const p = await win.outerPosition(), sf = await win.scaleFactor();
    origin = { x: p.x / sf, y: p.y / sf };
  } catch (e) {}
  ask();
}
function ask() { if (!down) T.event.emit("whip-ask", null).catch(() => {}); }
T.event.listen("whip-pet", (ev) => {
  const b = ev.payload;
  pet = b ? { x: b.x - origin.x, y: b.y - origin.y, w: b.w, h: b.h } : null;
});
T.event.listen("whip-shown", start);
setInterval(ask, 1000);               // the pet may be dragged meanwhile
let down = false;
start();

addEventListener("mousemove", (e) => {
  if (!mouse) for (let i = 0; i < N; i++) pts.push({ x: e.clientX, y: e.clientY + i * SEG, px: e.clientX, py: e.clientY + i * SEG });
  mouse = { x: e.clientX, y: e.clientY };
});
const putDown = () => {
  if (down) return;
  down = true;
  mouse = null;
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  T.core.invoke("whip_close").catch(() => win.hide());
};
addEventListener("mousedown", putDown);
addEventListener("keydown", (e) => { if (e.key === "Escape") putDown(); });

// The sound is played by the pet's window (app.js), which got a real click: a window that only ever sees
// mouse moves isn't allowed to start audio.
function crackSound() { T.event.emit("whip-crack", null).catch(() => {}); }

function inPet(x, y) {
  return pet && x >= pet.x - HIT_PAD && x <= pet.x + pet.w + HIT_PAD && y >= pet.y - HIT_PAD && y <= pet.y + pet.h + HIT_PAD;
}

function step() {
  if (!mouse) return;
  const p = pts;
  for (let i = 1; i < N; i++) {
    const q = p[i], vx = (q.x - q.px) * DAMP, vy = (q.y - q.py) * DAMP;
    q.px = q.x; q.py = q.y;
    q.x += vx; q.y += vy + GRAVITY;
  }
  for (let k = 0; k < 10; k++) {
    p[0].x = mouse.x; p[0].y = mouse.y;
    for (let i = 1; i < N; i++) {
      const a = p[i - 1], b = p[i], dx = b.x - a.x, dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 1, diff = (dist - SEG) / dist;
      if (i === 1) { b.x -= dx * diff; b.y -= dy * diff; }
      else { a.x += dx * diff * 0.5; a.y += dy * diff * 0.5; b.x -= dx * diff * 0.5; b.y -= dy * diff * 0.5; }
    }
  }
  const now = performance.now(), tip = p[N - 1], tipSpeed = Math.hypot(tip.x - tip.px, tip.y - tip.py);
  if (tipSpeed > CRACK_SPEED && now - lastCrack > CRACK_GAP) {
    lastCrack = now;
    crackSound();
    star = { x: tip.x, y: tip.y, t: now };
  }
  if (now - lastHit > HIT_GAP && pet) {
    for (let i = 6; i < N; i++) {          // any part of the lash past the handle
      const q = p[i];
      if (Math.hypot(q.x - q.px, q.y - q.py) < HIT_SPEED) continue;
      let hit = false;
      for (let s = 0; s <= 6 && !hit; s++) hit = inPet(q.px + (q.x - q.px) * s / 6, q.py + (q.y - q.py) * s / 6);
      if (hit) {
        lastHit = now;
        star = { x: q.x, y: q.y, t: now, hit: true };
        T.event.emit("whip-hit", null).catch(() => {});
        break;
      }
    }
  }
}

function draw() {
  ctx.clearRect(0, 0, innerWidth, innerHeight);
  if (!mouse) return;
  const p = pts;
  ctx.lineCap = "round";
  for (let i = N - 1; i > 0; i--) {
    ctx.strokeStyle = i < 4 ? "#8A5A3C" : "#5C3A26";
    ctx.lineWidth = i < 4 ? 8 : Math.max(1.4, 5 - i * 0.16);
    ctx.beginPath(); ctx.moveTo(p[i - 1].x, p[i - 1].y); ctx.lineTo(p[i].x, p[i].y); ctx.stroke();
  }
  ctx.fillStyle = "#5C3A26";
  ctx.fillRect(mouse.x - 5, mouse.y - 5, 10, 10);
  if (star) {
    const age = (performance.now() - star.t) / 350;
    if (age >= 1) { star = null; return; }
    const k = 8 + age * 16, a = 1 - age;
    ctx.globalAlpha = a;
    ctx.fillStyle = "#F5C451";
    ctx.fillRect(star.x - 2, star.y - k - 8, 4, 10); ctx.fillRect(star.x - 2, star.y + k - 2, 4, 10);
    ctx.fillRect(star.x - k - 8, star.y - 2, 10, 4); ctx.fillRect(star.x + k - 2, star.y - 2, 10, 4);
    ctx.font = "800 18px 'IBM Plex Sans KR', system-ui, sans-serif";
    ctx.fillStyle = "#F4F1FF";
    ctx.strokeStyle = "#23203A"; ctx.lineWidth = 4;
    const word = star.hit ? "착! 호치호치!" : "착!";
    ctx.strokeText(word, star.x + 12, star.y - 14); ctx.fillText(word, star.x + 12, star.y - 14);
    ctx.globalAlpha = 1;
  }
}

function loop() { step(); draw(); requestAnimationFrame(loop); }
requestAnimationFrame(loop);
