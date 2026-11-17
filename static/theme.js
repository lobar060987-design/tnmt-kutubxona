(function () {
  var saved = null;
  try { saved = localStorage.getItem("theme"); } catch (e) {}
  var dark = saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  var m = document.querySelector('meta[name="theme-color"]');
  function paint() {
    var d = document.documentElement.dataset.theme === "dark";
    if (m) m.content = d ? "#0F161D" : "#0B6E78";
    document.querySelectorAll("[data-theme-btn]").forEach(function (b) {
      b.setAttribute("aria-label", d ? "Kun rejimi" : "Tun rejimi");
      b.innerHTML = d
        ? '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
        : '<svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
    });
  }
  window.toggleTheme = function () {
    var next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) {}
    paint();
    document.dispatchEvent(new Event("themechange"));
  };
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-theme-btn]").forEach(function (b) { b.addEventListener("click", window.toggleTheme); });
    paint();
  });
})();
