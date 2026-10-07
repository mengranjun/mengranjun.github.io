/* MurojBlog — main.js (zero dependency) */
(function () {
  "use strict";

  var root = document.documentElement;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- 按时间自动切换深浅色 ----------
     THEME_AUTO_BY_TIME = true  → 白天浅色、夜里深色（默认）
                          = false → 改回跟随系统设置
     下面两个数字是「白天」的小时区间，注意要和各页面 <head> 里
     那段内联脚本保持一致（搜索结果里搜 "autoTheme" 就能找到）。 */
  var THEME_AUTO_BY_TIME = true;
  var DAY_START = 7;    // 7:00 起算白天
  var DAY_END = 19;     // 19:00 起算夜里

  function preferredTheme() {
    if (THEME_AUTO_BY_TIME) {
      var h = new Date().getHours();
      return (h >= DAY_START && h < DAY_END) ? "light" : "dark";
    }
    return (mq && mq.matches) ? "dark" : "light";
  }

  /* ---------- Theme ----------
     The real no-flash initialisation lives in a tiny inline <script> in
     each page's <head>; this is only a safety net if that is missing. */
  var stored = null;
  try { stored = localStorage.getItem("blog-theme"); } catch (e) {}

  if (!root.getAttribute("data-theme")) {
    root.setAttribute("data-theme", stored || preferredTheme());
  }

  function isDark() { return root.getAttribute("data-theme") === "dark"; }

  function syncThemeButtons() {
    document.querySelectorAll("[data-action='toggle-theme']").forEach(function (b) {
      b.setAttribute("aria-pressed", isDark() ? "true" : "false");
    });
  }

  /* 主题切换。支持 View Transitions 的浏览器里，新主题会从按钮的位置
     以一个圆形扩散铺满整屏；不支持、或用户关闭了动效时，直接切换。 */
  function toggleTheme(originEl) {
    var next = isDark() ? "light" : "dark";
    var apply = function () {
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("blog-theme", next); } catch (e) {}
      stored = next;                    // 手动选过之后，自动切换就不再干预
      syncThemeButtons();
    };

    if (reduced || !document.startViewTransition || !originEl) { apply(); return; }

    var r = originEl.getBoundingClientRect();
    var x = r.left + r.width / 2;
    var y = r.top + r.height / 2;
    var far = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));

    var vt;
    try { vt = document.startViewTransition(apply); } catch (e) { apply(); return; }
    if (!vt || !vt.ready) { apply(); return; }

    vt.ready.then(function () {
      document.documentElement.animate(
        { clipPath: ["circle(0px at " + x + "px " + y + "px)",
                     "circle(" + far + "px at " + x + "px " + y + "px)"] },
        { duration: 560, easing: "cubic-bezier(0.4, 0, 0.2, 1)",
          pseudoElement: "::view-transition-new(root)" }
      );
    }).catch(function () {});
    if (vt.finished && vt.finished.catch) vt.finished.catch(function () {});
  }

  // 读者没手动选过时：按时间自动切换；手动选过就完全听读者的。
  function autoTheme() {
    if (stored) return;
    var want = preferredTheme();
    if (root.getAttribute("data-theme") !== want) {
      root.setAttribute("data-theme", want);
      syncThemeButtons();
    }
  }

  if (THEME_AUTO_BY_TIME) {
    autoTheme();
    window.setInterval(autoTheme, 10 * 60 * 1000);          // 每 10 分钟看一眼
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) autoTheme();                     // 切回标签页时也看一眼
    });
  } else if (mq && mq.addEventListener) {
    // 跟随系统时，系统主题变了要跟着变
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
    if (btn) toggleTheme(btn);

    var copyBtn = e.target.closest(".copy-btn");
    if (copyBtn) {
      var code = copyBtn.parentElement.querySelector("code");
      if (code && navigator.clipboard) {
        // 行号在 .cl-n 里，复制前先从克隆节点里摘掉，别混进剪贴板
        var clone = code.cloneNode(true);
        Array.prototype.forEach.call(clone.querySelectorAll(".cl-n"), function (n) {
          if (n.parentNode) n.parentNode.removeChild(n);
        });
        navigator.clipboard.writeText(clone.textContent).then(function () {
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
