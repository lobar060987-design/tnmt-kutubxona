"use strict";
var $ = function (s) { return document.querySelector(s); };
var books = [], editId = null;
function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
function show(logged) { $("#login").hidden = logged; $("#panel").hidden = !logged; }
function say(t, cls) { var m = $("#msg"); m.textContent = t; m.className = "msg " + (cls || ""); }

function send(method, url, body, onp) {
  return new Promise(function (res, rej) {
    var x = new XMLHttpRequest();
    x.open(method, url);
    if (!(body instanceof FormData) && body) x.setRequestHeader("Content-Type", "application/json");
    if (x.upload && onp) x.upload.onprogress = function (e) { if (e.lengthComputable) onp(e.loaded / e.total); };
    x.onload = function () {
      var d = {}; try { d = JSON.parse(x.responseText); } catch (e) {}
      if (x.status >= 200 && x.status < 300) return res(d);
      if (x.status === 401 && url.indexOf("login") < 0) show(false);
      rej({ status: x.status, msg: typeof d.detail === "string" ? d.detail : "Ma'lumotlarni tekshiring" });
    };
    x.onerror = function () { rej({ msg: "Tarmoq xatosi. Internetni tekshiring" }); };
    x.send(body instanceof FormData ? body : body ? JSON.stringify(body) : null);
  });
}

function render() {
  var f = $("#filter").value.trim().toLowerCase();
  var list = books.filter(function (b) { return !f || (b.title + " " + b.author + " " + b.category).toLowerCase().indexOf(f) >= 0; });
  $("#n").textContent = "(" + books.length + ")";
  $("#list").innerHTML = list.length ? list.map(function (b) {
    return '<div class="item"><div class="tt"><b>' + esc(b.title) + "</b><span>" + esc(b.author || "Muallif yo'q") + " · " + esc(b.category) + " · " + b.size_mb + " MB · " + b.views + ' ko\'rilgan</span></div>' +
      '<div class="btns"><a class="btn" href="/reader.html?id=' + b.id + '" target="_blank" rel="noopener">Ko\'rish</a><button type="button" data-e="' + b.id + '">Tahrirlash</button><button type="button" class="danger" data-d="' + b.id + '">O\'chirish</button></div></div>';
  }).join("") : '<p style="text-align:center;color:var(--muted);padding:24px 0">Kitoblar yo\'q.</p>';
  $("#cats").innerHTML = Array.from(new Set(books.map(function (b) { return b.category; }))).map(function (c) { return '<option value="' + esc(c) + '">'; }).join("");
}

function load() {
  return Promise.all([send("GET", "/api/books?limit=500&sort=title"), send("GET", "/api/admin/stats")]).then(function (r) {
    books = r[0].items; render();
    var s = r[1];
    $("#kBooks").textContent = s.books; $("#kViews").textContent = s.views; $("#kSize").textContent = s.size_mb;
    $("#kTop").innerHTML = s.top.length ? s.top.map(function (t) { return "<li>" + esc(t.title) + " (" + t.views + ")</li>"; }).join("") : "<li>Hozircha yo'q</li>";
  });
}

function reset() {
  editId = null;
  ["title", "author", "category", "year", "desc"].forEach(function (k) { $("#" + k).value = ""; });
  $("#pdf").value = "";
  $("#formTitle").textContent = "Yangi kitob qo'shish";
  $("#pdfLabel").textContent = "PDF fayl *";
  $("#cancel").hidden = true; $("#prog").hidden = true;
}

$("#loginBtn").onclick = function () {
  send("POST", "/api/admin/login", { username: $("#u").value, password: $("#p").value })
    .then(function () { $("#p").value = ""; $("#loginMsg").textContent = ""; show(true); return load(); })
    .catch(function (e) { $("#loginMsg").textContent = e.msg; });
};
$("#p").addEventListener("keydown", function (e) { if (e.key === "Enter") $("#loginBtn").click(); });
$("#logout").onclick = function () { send("POST", "/api/admin/logout").then(function () { show(false); }); };
$("#filter").oninput = render;
$("#cancel").onclick = function () { reset(); say(""); };

$("#list").onclick = function (e) {
  var ed = e.target.closest("[data-e]"), del = e.target.closest("[data-d]");
  if (ed) {
    var b = books.find(function (x) { return x.id == ed.dataset.e; });
    editId = b.id;
    $("#title").value = b.title; $("#author").value = b.author; $("#category").value = b.category;
    $("#year").value = b.year || ""; $("#desc").value = b.description; $("#pdf").value = "";
    $("#formTitle").textContent = "Kitobni tahrirlash";
    $("#pdfLabel").textContent = "Yangi PDF (kerak bo'lmasa bo'sh qoldiring)";
    $("#cancel").hidden = false; say("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  if (del) {
    var bk = books.find(function (x) { return x.id == del.dataset.d; });
    if (!confirm("«" + bk.title + "» kitobini o'chirasizmi? Buni qaytarib bo'lmaydi.")) return;
    send("DELETE", "/api/admin/books/" + bk.id).then(function () { if (editId === bk.id) reset(); say("Kitob o'chirildi", "ok"); return load(); })
      .catch(function (er) { say(er.msg, "err"); });
  }
};

// PDF tanlanganda nom bo'sh bo'lsa, fayl nomidan to'ldiriladi
$("#pdf").addEventListener("change", function () {
  var f = this.files[0];
  if (f && !$("#title").value.trim()) $("#title").value = f.name.replace(/\.pdf$/i, "").replace(/[_]+/g, " ");
});

$("#save").onclick = function () {
  var file = $("#pdf").files[0];
  if (!$("#title").value.trim()) return say("Kitob nomini kiriting", "err");
  if (!editId && !file) return say("PDF faylni tanlang", "err");
  var fd = new FormData();
  fd.append("title", $("#title").value); fd.append("author", $("#author").value);
  fd.append("category", $("#category").value); fd.append("year", $("#year").value);
  fd.append("description", $("#desc").value);
  if (file) fd.append("pdf", file);
  var btn = $("#save"); btn.disabled = true; say("Saqlanmoqda…");
  $("#prog").hidden = !file; $("#prog").value = 0;
  var wasEdit = !!editId;
  send(editId ? "PUT" : "POST", editId ? "/api/admin/books/" + editId : "/api/admin/books", fd, function (p) { $("#prog").value = p; })
    .then(function () { reset(); say(wasEdit ? "O'zgarishlar saqlandi" : "Kitob qo'shildi", "ok"); return load(); })
    .catch(function (e) { say(e.msg, "err"); })
    .then(function () { btn.disabled = false; $("#prog").hidden = true; });
};

send("GET", "/api/admin/check").then(function () { show(true); return load(); }).catch(function () { show(false); });
