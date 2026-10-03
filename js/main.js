/* MineAI Blog — main.js (zero dependency) */
(function () {
  "use strict";

  var root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  /* ---------- Theme ----------
     The real no-flash initialisation lives in a tiny inline <script> in
     each page's <head>; this is only a safety net if that is missing. */
  var stored = null;
  try { stored = localStorage.getItem("blog-theme"); } catch (e) {}

  if (!root.getAttribute("data-theme")) {
    if (stored) root.setAttribute("data-theme", stored);
    else if (mq && mq.matches) root.setAttribute("data-theme", "dark");
  }

  function isDark() { return root.getAttribute("data-theme") === "dark"; }

  function syncThemeButtons() {
    document.querySelectorAll("[data-action='toggle-theme']").forEach(function (b) {
      b.setAttribute("aria-pressed", isDark() ? "true" : "false");
    });
  }

  function toggleTheme() {
    var next = isDark() ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("blog-theme", next); } catch (e) {}
    syncThemeButtons();
  }

  // Follow the system only while the reader has not made an explicit choice.
  if (mq && mq.addEventListener) {
    mq.addEventListener("change", function (e) {
      if (stored) return;
      root.setAttribute("data-theme", e.matches ? "dark" : "light");
      syncThemeButtons();
    });
  }

  syncThemeButtons();

  /* ---------- Delegated clicks ---------- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='toggle-theme']");
    if (btn) toggleTheme();

    var copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
      var code = copyBtn.parentElement.querySelector("code");
      if (code && navigator.clipboard) {
        navigator.clipboard.writeText(code.innerText).then(function () {
          copyBtn.textContent = "已复制";
          setTimeout(function () { copyBtn.textContent = "复制"; }, 1600);
        }).catch(function () {
          copyBtn.textContent = "复制失败";
          setTimeout(function () { copyBtn.textContent = "复制"; }, 1600);
        });
      }
    }
  });

  document.querySelectorAll(".copy-btn").forEach(function (b) {
    b.setAttribute("aria-live", "polite");
  });

  /* ---------- Mobile nav ---------- */
  var menuBtn = document.querySelector(".menu-btn");
  var nav = document.querySelector(".main-nav");
  if (menuBtn && nav) {
    var setNav = function (open) {
      nav.classList.toggle("open", open);
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      menuBtn.setAttribute("aria-label", open ? "关闭菜单" : "打开菜单");
    };
    menuBtn.addEventListener("click", function () {
      setNav(!nav.classList.contains("open"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setNav(false);
    });
  }

  /* ---------- Reading progress (article pages) ---------- */
  var progress = document.querySelector(".progress-bar");
  if (progress) {
    var onScroll = function () {
      var doc = document.documentElement;
      var total = doc.scrollHeight - doc.clientHeight;
      var pct = total > 0 ? (doc.scrollTop / total) * 100 : 0;
      progress.style.width = pct + "%";
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- Reveal on scroll ---------- */
  var revealEls = document.querySelectorAll(".reveal");
  if (revealEls.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("visible"); });
  }

  /* ---------- Tag filter (archive page) ---------- */
  var filterBar = document.querySelector(".filter-bar");
  if (filterBar) {
    filterBar.addEventListener("click", function (e) {
      var btn = e.target.closest(".filter-btn");
      if (!btn) return;
      filterBar.querySelectorAll(".filter-btn").forEach(function (b) {
        b.classList.remove("active");
        b.setAttribute("aria-pressed", "false");
      });
      btn.classList.add("active");
      btn.setAttribute("aria-pressed", "true");
      var tag = btn.getAttribute("data-tag");
      document.querySelectorAll(".post-list li").forEach(function (li) {
        var tags = (li.getAttribute("data-tags") || "").split(",");
        li.style.display = (tag === "all" || tags.indexOf(tag) !== -1) ? "" : "none";
      });
    });
  }

  /* ---------- Footer year ---------- */
  var yearEl = document.querySelector("[data-year]");
  if (yearEl) yearEl.textContent = new Date().getFullYear();
})();
