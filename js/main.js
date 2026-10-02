/* MineAI Blog — main.js (zero dependency) */
(function () {
  "use strict";

  /* ---------- Theme: init early choice, toggle, persist ---------- */
  var root = document.documentElement;
  var stored = null;
  try { stored = localStorage.getItem("blog-theme"); } catch (e) {}

  if (stored) {
    root.setAttribute("data-theme", stored);
  } else if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.setAttribute("data-theme", "dark");
  }

  function toggleTheme() {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("blog-theme", next); } catch (e) {}
  }

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
        });
      }
    }
  });

  /* ---------- Mobile nav ---------- */
  var menuBtn = document.querySelector(".menu-btn");
  var nav = document.querySelector(".main-nav");
  if (menuBtn && nav) {
    menuBtn.addEventListener("click", function () {
      nav.classList.toggle("open");
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
      filterBar.querySelectorAll(".filter-btn").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
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
