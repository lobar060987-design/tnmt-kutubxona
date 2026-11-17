"use strict";
// PDF o'qish oynasi: sahifalar kerak bo'lganda chiziladi, oxirgi sahifa va kattalashtirish eslab qolinadi.
var $ = function (id) { return document.getElementById(id); };
var qs = new URLSearchParams(location.search), id = qs.get("id");
function store(k, v) { try { if (v === undefined) return JSON.parse(localStorage.getItem(k)); localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} return null; }
function fail(msg, url) {
  $("status").innerHTML = msg + (url ? ' <br><br><a class="btn" href="' + url + '">PDF faylni to\'g\'ridan-to\'g\'ri ochish</a>' : ' <br><br><a class="btn" href="/">Kitoblar ro\'yxatiga qaytish</a>');
}

(async function () {
  var book;
  try {
    var r = await fetch("/api/books/" + encodeURIComponent(id));
    if (!r.ok) throw 0;
    book = await r.json();
  } catch (e) { return fail("Kitob topilmadi."); }

  $("title").textContent = book.title; document.title = book.title;
  $("dl").href = book.pdf_url + "?download=1"; $("dl").hidden = false;
  if (!window.pdfjsLib) return fail("O'qish oynasi yuklanmadi.", book.pdf_url);
  pdfjsLib.GlobalWorkerOptions.workerSrc = "/vendor/pdf.worker.min.js";

  var pdf;
  try {
    var task = pdfjsLib.getDocument({ url: book.pdf_url, rangeChunkSize: 262144 });
    task.onProgress = function (p) { if (p.total) $("stt").textContent = "Yuklanmoqda… " + Math.round(p.loaded / p.total * 100) + "%"; };
    pdf = await task.promise;
  } catch (e) { return fail("PDF ochilmadi.", book.pdf_url); }

  fetch("/api/books/" + book.id + "/view", { method: "POST" }).catch(function () {});

  var N = pdf.numPages, box = $("pages"), slots = [], cur = 1, zoom = store("kt_zoom") || 1, ratio = 1.414, token = 0;
  $("tot").textContent = N;
  var first = await pdf.getPage(1), v1 = first.getViewport({ scale: 1 });
  ratio = v1.height / v1.width;
  box.innerHTML = "";

  function baseWidth() { return Math.min(window.innerWidth - 16, 900); }
  function pageWidth() { return Math.round(baseWidth() * zoom); }

  for (var i = 1; i <= N; i++) {
    var d = document.createElement("div");
    d.className = "page"; d.dataset.n = i; box.appendChild(d); slots.push(d);
  }

  async function render(slot, tk) {
    if (slot.dataset.s) return;
    slot.dataset.s = "busy";
    var page = await pdf.getPage(+slot.dataset.n);
    var w = pageWidth(), vp1 = page.getViewport({ scale: 1 });
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var vp = page.getViewport({ scale: (w / vp1.width) * dpr });
    var c = document.createElement("canvas");
    c.width = vp.width; c.height = vp.height; c.style.width = w + "px"; c.style.height = (vp.height / dpr) + "px";
    await page.render({ canvasContext: c.getContext("2d"), viewport: vp }).promise;
    if (tk !== token || slot.dataset.s !== "busy") return;
    slot.replaceChildren(c); slot.dataset.s = "done";
  }
  function unrender(slot) { if (slot.dataset.s === "done" || slot.dataset.s === "busy") { slot.replaceChildren(); } slot.dataset.s = ""; }

  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { e.isIntersecting ? render(e.target, token) : unrender(e.target); });
  }, { rootMargin: "1100px 0px" });

  var mid = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) setCur(+e.target.dataset.n); });
  }, { rootMargin: "-50% 0px -49% 0px" });

  var saveT;
  function setCur(n) {
    cur = n; $("pin").value = n; $("prog").style.width = (n / N * 100) + "%";
    clearTimeout(saveT);
    saveT = setTimeout(function () {
      var p = store("kt_progress") || {};
      p[book.id] = { page: n, total: N, ts: Date.now(), title: book.title, author: book.author, category: book.category };
      store("kt_progress", p);
    }, 400);
  }

  function layout() {
    token++;
    var w = pageWidth(), h = Math.round(w * ratio);
    slots.forEach(function (s) {
      io.unobserve(s); mid.unobserve(s);
      s.replaceChildren(); s.dataset.s = ""; s.style.width = w + "px"; s.style.height = h + "px";
    });
    slots.forEach(function (s) { io.observe(s); mid.observe(s); });
  }
  function go(n) { n = Math.max(1, Math.min(N, n)); slots[n - 1].scrollIntoView({ block: "start" }); setCur(n); }
  function setZoom(z) {
    var keep = cur; zoom = Math.max(0.6, Math.min(3, z)); store("kt_zoom", zoom);
    layout(); go(keep);
  }

  layout();
  $("dock").hidden = false;
  var p0 = (store("kt_progress") || {})[book.id], start = +qs.get("page") || (p0 && p0.page) || 1;
  if (start > 1 && start <= N) requestAnimationFrame(function () { go(start); });
  setCur(start > 1 && start <= N ? start : 1);

  $("zin").onclick = function () { setZoom(zoom + 0.25); };
  $("zout").onclick = function () { setZoom(zoom - 0.25); };
  $("prev").onclick = function () { go(cur - 1); };
  $("next").onclick = function () { go(cur + 1); };
  $("pin").addEventListener("change", function () { var n = parseInt(this.value, 10); if (n) go(n); else this.value = cur; });
  $("pin").addEventListener("focus", function () { this.select(); });
  document.addEventListener("keydown", function (e) {
    if (e.target.tagName === "INPUT") return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { go(cur + 1); e.preventDefault(); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { go(cur - 1); e.preventDefault(); }
    if (e.key === "+" || e.key === "=") setZoom(zoom + 0.25);
    if (e.key === "-") setZoom(zoom - 0.25);
  });
  var rt, lastW = window.innerWidth;
  window.addEventListener("resize", function () {
    clearTimeout(rt);
    rt = setTimeout(function () { if (window.innerWidth !== lastW) { lastW = window.innerWidth; var k = cur; layout(); go(k); } }, 200);
  });
})();
