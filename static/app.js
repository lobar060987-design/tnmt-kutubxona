"use strict";
// O'quvchi paneli: qidiruv, bo'limlar, saralash, saqlanganlar, davom ettirish, kitob oynasi.
var LIMIT = 24;
var $ = function (id) { return document.getElementById(id); };
var st = { q: "", category: "", sort: "new", offset: 0, total: 0, items: [], loading: false, fav: false };
var current = null;

function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function hue(s) { var h = 0; s = String(s || ""); for (var i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360; return h; }
function coverStyle(b) { var h = hue(b.category); return "background:linear-gradient(150deg,hsl(" + h + " 45% 36%),hsl(" + ((h + 28) % 360) + " 50% 24%))"; }
function api(u, o) { return fetch(u, o).then(function (r) { if (!r.ok) throw new Error(r.status === 404 ? "Topilmadi" : "Server javob bermadi"); return r.json(); }); }
function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k)); localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} return null; }
function toast(t, err) { var el = $("toast"); el.textContent = t; el.className = "toast on" + (err ? " err" : ""); clearTimeout(toast.t); toast.t = setTimeout(function () { el.className = "toast"; }, 2600); }

// ---- saqlanganlar ----
function favs() { return store("kt_fav") || []; }
function isFav(id) { return favs().indexOf(id) >= 0; }
function toggleFav(id) {
  var f = favs(), i = f.indexOf(id);
  if (i >= 0) f.splice(i, 1); else f.unshift(id);
  store("kt_fav", f); updateFavN();
  return i < 0;
}
function updateFavN() { var n = favs().length; $("favN").textContent = n ? "(" + n + ")" : ""; }

// ---- kartalar ----
var HEART = '<svg viewBox="0 0 24 24"><path d="M12 21s-7.5-4.6-9.5-9.2C1.3 8.6 3 5 6.5 5c2 0 3.6 1.1 5.5 3 1.9-1.9 3.5-3 5.5-3 3.5 0 5.2 3.6 4 6.800C19.5 16.4 12 21 12 21z"/></svg>';
function cardHTML(b, i) {
  return '<div class="book" style="--i:' + (i % LIMIT) + '">' +
    '<button class="fav" type="button" data-f="' + b.id + '" aria-pressed="' + isFav(b.id) + '" aria-label="Saqlash">' + HEART + '</button>' +
    '<button class="book-open" type="button" data-id="' + b.id + '">' +
    '<div class="cover" style="' + coverStyle(b) + '"><b>' + esc(b.title) + '</b><small>' + esc(b.author || b.category) + '</small></div>' +
    '<div class="meta"><strong>' + esc(b.title) + '</strong><span>' + esc(b.author || "Muallif ko'rsatilmagan") + '</span></div></button></div>';
}
function skeletons(el, n) { el.innerHTML = new Array(n + 1).join('<div class="skel"></div>'); }

// ---- ro'yxat ----
function params(extra) {
  var p = new URLSearchParams({ q: st.q, category: st.category, sort: st.sort, limit: LIMIT, offset: st.offset });
  if (st.fav) p.set("ids", favs().join(",") || "0");
  for (var k in extra) p.set(k, extra[k]);
  return p;
}
function load(reset) {
  if (st.loading) return;
  st.loading = true;
  if (reset) { st.offset = 0; st.items = []; skeletons($("grid"), 8); }
  api("/api/books?" + params()).then(function (d) {
    st.total = d.total; st.items = st.items.concat(d.items); st.offset = st.items.length; render();
  }).catch(function (e) {
    $("grid").innerHTML = '<div class="state">' + esc(e.message) + '. Internetni tekshiring.<br><br><button class="btn" id="retry" type="button">Qayta urinish</button></div>';
    $("retry").onclick = function () { load(true); };
    $("more").hidden = true;
  }).then(function () { st.loading = false; });
}
function render() {
  var empty = !st.items.length;
  $("count").textContent = empty ? "" : st.total + " ta kitob";
  $("grid").innerHTML = empty
    ? '<div class="state"><svg viewBox="0 0 24 24"><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 5v16"/></svg><br>' +
      (st.fav ? "Hali kitob saqlamadingiz. Kitobdagi yurakchani bosing." : (st.q || st.category) ? "Hech narsa topilmadi. Boshqa so'z bilan qidirib ko'ring." : "Kutubxonada hali kitob yo'q.") + "</div>"
    : st.items.map(cardHTML).join("");
  $("more").hidden = st.items.length >= st.total;
  $("listTitle").textContent = st.fav ? "Saqlangan kitoblar" : st.category || (st.q ? "Qidiruv natijalari" : "Hamma kitoblar");
  var plain = !st.q && !st.category && !st.fav;
  if (plain && st.sort === "new") loadPopular(); else $("popular").hidden = true;
}
var popCache = {};
function loadPopular() {
  api("/api/books?sort=popular&limit=6").then(function (d) {
    var top = d.items.filter(function (b) { return b.views > 0; });
    top.forEach(function (b) { popCache[b.id] = b; });
    $("popular").hidden = top.length < 3 || d.total < 8;
    if (!$("popular").hidden) $("popGrid").innerHTML = top.map(cardHTML).join("");
  }).catch(function () {});
}
function loadCats() {
  api("/api/categories").then(function (list) {
    var total = list.reduce(function (a, c) { return a + c.count; }, 0);
    var h = '<button class="chip" type="button" data-c="" aria-pressed="' + (st.category === "") + '">Hammasi<small>' + total + "</small></button>";
    list.forEach(function (c) { h += '<button class="chip" type="button" data-c="' + esc(c.name) + '" aria-pressed="' + (st.category === c.name) + '">' + esc(c.name) + "<small>" + c.count + "</small></button>"; });
    $("chips").innerHTML = h;
  }).catch(function () {});
}
function loadStats() {
  api("/api/stats").then(function (s) {
    $("stats").hidden = !s.books;
    $("stats").innerHTML = "<span><b>" + s.books + "</b> kitob</span><span><b>" + s.categories + "</b> bo'lim</span>" + (s.views ? "<span><b>" + s.views + "</b> marta o'qilgan</span>" : "");
  }).catch(function () {});
}

// ---- davom ettirish ----
function showResume() {
  var p = store("kt_progress") || {}, last = null;
  Object.keys(p).forEach(function (k) { if (p[k].page > 1 && p[k].page < p[k].total && (!last || p[k].ts > last.ts)) last = Object.assign({ id: k }, p[k]); });
  var box = $("resume");
  box.hidden = !last;
  if (!last) return;
  var pct = Math.round(last.page / last.total * 100);
  box.innerHTML = '<div class="resume"><div class="cover" style="' + coverStyle(last) + '"><b>' + esc(last.title) + '</b></div>' +
    '<div class="t"><small>Davom ettirish</small><b>' + esc(last.title) + '</b><small>' + last.page + " / " + last.total + " sahifa</small>" +
    '<div class="pbar"><i style="width:' + pct + '%"></i></div></div>' +
    '<a class="btn primary" href="/reader.html?id=' + last.id + '">Ochish</a></div>';
}

// ---- hodisalar ----
function onGrid(e) {
  var f = e.target.closest("[data-f]"), o = e.target.closest("[data-id]");
  if (f) {
    var id = +f.dataset.f, on = toggleFav(id);
    document.querySelectorAll('[data-f="' + id + '"]').forEach(function (x) { x.setAttribute("aria-pressed", on); });
    toast(on ? "Saqlandi" : "Saqlanganlardan olib tashlandi");
    if (st.fav && !on) load(true);
    return;
  }
  if (o) {
    var id2 = +o.dataset.id, b = st.items.find(function (x) { return x.id === id2; }) || popCache[id2];
    openDetail(b);
  }
}
$("grid").addEventListener("click", onGrid);
$("popGrid").addEventListener("click", onGrid);
$("chips").addEventListener("click", function (e) {
  var b = e.target.closest("[data-c]"); if (!b) return;
  st.category = b.dataset.c;
  document.querySelectorAll(".chip").forEach(function (c) { c.setAttribute("aria-pressed", c === b); });
  load(true);
});
$("sort").onchange = function () { st.sort = this.value; load(true); };
var timer;
$("q").addEventListener("input", function () {
  $("qx").hidden = !this.value;
  clearTimeout(timer);
  var v = this.value.trim();
  timer = setTimeout(function () { st.q = v; load(true); }, 300);
});
$("qx").onclick = function () { $("q").value = ""; $("qx").hidden = true; st.q = ""; load(true); $("q").focus(); };
$("more").onclick = function () { load(false); };
function setTab(fav) {
  st.fav = fav;
  $("tAll").setAttribute("aria-selected", !fav); $("tFav").setAttribute("aria-selected", fav);
  load(true);
}
$("tAll").onclick = function () { setTab(false); };
$("tFav").onclick = function () { setTab(true); };

// ---- kitob oynasi ----
function openDetail(b) {
  if (!b) return;
  current = b;
  $("dcv").style.cssText = coverStyle(b);
  $("dct").textContent = b.title; $("dca").textContent = b.author;
  $("dt").textContent = b.title;
  $("da").textContent = b.author || "Muallif ko'rsatilmagan";
  $("df").innerHTML = [b.category, b.year, b.size_mb + " MB", b.views ? b.views + " marta o'qilgan" : ""].filter(Boolean).map(function (x) { return "<span>" + esc(x) + "</span>"; }).join("");
  $("dd").textContent = b.description; $("dd").hidden = !b.description;
  var p = (store("kt_progress") || {})[b.id];
  $("dread").textContent = p && p.page > 1 ? p.page + "-sahifadan davom etish" : "O'qish";
  $("dread").href = "/reader.html?id=" + b.id;
  $("ddl").href = b.pdf_url + "?download=1";
  $("dfav").setAttribute("aria-pressed", isFav(b.id));
  history.replaceState(null, "", "#book-" + b.id);
  if (!$("det").open) $("det").showModal();
}
$("dx").onclick = function () { $("det").close(); };
$("det").addEventListener("close", function () { history.replaceState(null, "", location.pathname + location.search); });
$("det").addEventListener("click", function (e) { if (e.target === $("det")) $("det").close(); });
$("dfav").onclick = function () {
  var on = toggleFav(current.id);
  this.setAttribute("aria-pressed", on);
  document.querySelectorAll('[data-f="' + current.id + '"]').forEach(function (x) { x.setAttribute("aria-pressed", on); });
  toast(on ? "Saqlandi" : "Saqlanganlardan olib tashlandi");
};
$("dsh").onclick = function () {
  var url = location.origin + "/#book-" + current.id;
  if (navigator.share) navigator.share({ title: current.title, url: url }).catch(function () {});
  else if (navigator.clipboard) navigator.clipboard.writeText(url).then(function () { toast("Havola nusxalandi"); });
};
function openFromHash() {
  var m = location.hash.match(/^#book-(\d+)$/);
  if (m) api("/api/books/" + m[1]).then(openDetail).catch(function () { toast("Kitob topilmadi", true); });
}

// ---- ishga tushirish ----
api("/api/config").then(function (c) { $("site").textContent = c.site_name; document.title = c.site_name; $("foot").textContent = c.site_name; }).catch(function () {});
updateFavN(); showResume(); loadCats(); loadStats(); load(true); openFromHash();
window.addEventListener("pageshow", showResume);
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(function () {});
