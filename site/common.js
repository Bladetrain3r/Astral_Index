// Shared helpers. No libraries.
const $ = (s, el = document) => el.querySelector(s);
const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

async function getCSV(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + ": " + r.status);
  const lines = (await r.text()).trim().split("\n");
  const head = lines.shift().split(",");
  return lines.map(l => {
    const c = l.split(","), o = {};
    head.forEach((h, i) => (o[h] = c[i] ?? ""));
    return o;
  });
}
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + ": " + r.status);
  return r.json();
}
const num = x => (x === "" || x == null ? null : +x);
const fmt = (x, d = 1) => (x == null || Number.isNaN(x) ? "–" : (+x).toFixed(d));
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// Colour ramp: dark blue (low) to yellow (high), readable in both themes.
function ramp(t) {
  t = Math.max(0, Math.min(1, t));
  const stops = [[38, 70, 160], [40, 150, 170], [120, 200, 110], [245, 200, 60]];
  const i = Math.min(stops.length - 2, Math.floor(t * (stops.length - 1))), f = t * (stops.length - 1) - i;
  const c = stops[i].map((a, k) => Math.round(a + (stops[i + 1][k] - a) * f));
  return `rgb(${c[0]},${c[1]},${c[2]})`;
}
const RAMP_CSS = "linear-gradient(90deg,rgb(38,70,160),rgb(40,150,170),rgb(120,200,110),rgb(245,200,60))";

function setupCanvas(cv, h) {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth;
  cv.width = w * dpr; cv.height = h * dpr; cv.style.height = h + "px";
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  return [g, w, h];
}

// Scatter plot with axes. pts: [{x,y,c,o}], returns a hit-test function.
function scatter(cv, pts, opt) {
  const [g, W, H] = setupCanvas(cv, opt.h || 300);
  const m = { l: 52, r: 10, t: 10, b: 36 };
  const [x0, x1] = opt.xr, [y0, y1] = opt.yr;
  const X = v => m.l + (v - x0) / (x1 - x0) * (W - m.l - m.r), Y = v => H - m.b - (v - y0) / (y1 - y0) * (H - m.t - m.b);
  g.clearRect(0, 0, W, H);
  g.strokeStyle = css("--line"); g.fillStyle = css("--muted"); g.font = "11px system-ui"; g.lineWidth = 1;
  const ticks = (a, b, n) => { const s = (b - a) / n; return Array.from({ length: n + 1 }, (_, i) => a + i * s); };
  g.textAlign = "center";
  for (const v of ticks(x0, x1, 5)) { g.beginPath(); g.moveTo(X(v), m.t); g.lineTo(X(v), H - m.b); g.stroke(); g.fillText(fmt(v, opt.xd ?? 1), X(v), H - m.b + 14); }
  g.textAlign = "right";
  for (const v of ticks(y0, y1, 4)) { g.beginPath(); g.moveTo(m.l, Y(v)); g.lineTo(W - m.r, Y(v)); g.stroke(); g.fillText(fmt(v, opt.yd ?? 1), m.l - 5, Y(v) + 4); }
  g.textAlign = "center"; g.fillText(opt.xl, (m.l + W - m.r) / 2, H - 6);
  g.save(); g.translate(12, (m.t + H - m.b) / 2); g.rotate(-Math.PI / 2); g.fillText(opt.yl, 0, 0); g.restore();
  if (opt.zero) { g.strokeStyle = css("--muted"); g.beginPath(); if (y0 < 0 && y1 > 0) { g.moveTo(m.l, Y(0)); g.lineTo(W - m.r, Y(0)); } if (opt.zero === "xy" && x0 < 0 && x1 > 0) { g.moveTo(X(0), m.t); g.lineTo(X(0), H - m.b); } g.stroke(); }
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const placed = [];
  for (const pass of [0, 1]) for (const p of pts) {
    if (!!p.o !== !!pass) continue;                         // outliers drawn last, on top
    const px = X(clamp(p.x, x0, x1)), py = Y(clamp(p.y, y0, y1));
    g.fillStyle = p.o ? css("--warn") : css("--accent"); g.globalAlpha = p.o ? 0.95 : 0.45;
    g.beginPath(); g.arc(px, py, p.o ? 3.2 : 1.8, 0, 6.3); g.fill();
    placed.push([px, py, p]);
  }
  g.globalAlpha = 1;
  return (mx, my) => { let best = null, bd = 64; for (const [px, py, p] of placed) { const d = (px - mx) ** 2 + (py - my) ** 2; if (d < bd) { bd = d; best = p; } } return best; };
}

function tip(ev, html) {
  const t = $("#tip");
  if (!html) { t.style.display = "none"; return; }
  t.innerHTML = html; t.style.display = "block";
  t.style.left = Math.min(ev.clientX + 12, innerWidth - 290) + "px"; t.style.top = ev.clientY + 12 + "px";
}

function sortable(table, rows, cols, render) {
  let key = null, dir = 1;
  const draw = () => {
    const r = key == null ? rows : [...rows].sort((a, b) => {
      const x = a[key], y = b[key], nx = parseFloat(x), ny = parseFloat(y);
      const both = !Number.isNaN(nx) && !Number.isNaN(ny);
      return dir * (both ? nx - ny : String(x).localeCompare(String(y)));
    });
    table.innerHTML = "<thead><tr>" + cols.map(c => `<th data-k="${c.k}" title="${esc(c.t || "")}">${esc(c.h)}</th>`).join("") +
      "</tr></thead><tbody>" + r.map(render).join("") + "</tbody>";
    table.querySelectorAll("th").forEach(th => th.onclick = () => { dir = key === th.dataset.k ? -dir : 1; key = th.dataset.k; draw(); });
  };
  draw();
}
const CREDIT = `Data from ESA Euclid/Euclid Consortium/NASA/DR1-2026 and from the ESA mission Gaia, processed by the Gaia DPAC.
 Derived tables are modified from the originals and are CC BY-NC 3.0 IGO. Not endorsed by ESA. Code MIT.`;
