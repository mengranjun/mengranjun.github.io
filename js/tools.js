/* ==========================================================================
   MurojBlog — 小工具集合 · 渲染 / 筛选 / squircle 圆角
   依赖：js/tools-data.js（先于本文件加载，提供 window.MUROJ_TOOLS）
   ========================================================================== */
(function () {
  "use strict";

  var doc = document;
  var grid = doc.getElementById("tool-grid");
  if (!grid) return;
  var tools = window.MUROJ_TOOLS || [];
  var searchInput = doc.getElementById("tool-search");
  var chipsBox = doc.getElementById("tool-chips");
  var countEl = doc.getElementById("tool-count");

  var activeTag = "全部";
  var query = "";

  /* ── 1. 收集所有标签，渲染筛选 chips ── */
  var tagSet = ["全部"];
  tools.forEach(function (t) {
    (t.tags || []).forEach(function (tag) {
      if (tagSet.indexOf(tag) < 0) tagSet.push(tag);
    });
  });

  function renderChips() {
    if (!chipsBox) return;
    chipsBox.innerHTML = "";
    tagSet.forEach(function (tag) {
      var b = doc.createElement("button");
      b.type = "button";
      b.className = "tool-chip" + (tag === activeTag ? " is-on" : "");
      b.textContent = tag;
      b.addEventListener("click", function () {
        activeTag = tag;
        renderChips();
        renderGrid();
      });
      chipsBox.appendChild(b);
    });
  }

  /* ── 2. 过滤 ── */
  function passes(t) {
    if (activeTag !== "全部" && !(t.tags || []).length) return false;
    if (activeTag !== "全部" && (t.tags || []).indexOf(activeTag) < 0) return false;
    if (query) {
      var hay = (t.title + " " + t.desc + " " + (t.tags || []).join(" ")).toLowerCase();
      if (hay.indexOf(query) < 0) return false;
    }
    return true;
  }

  /* ── 3. 渲染卡片 ── */
  function makeCard(t) {
    var card = doc.createElement("article");
    card.className = "tool-card" + (t.type === "planned" ? " is-planned" : "");
    card.setAttribute("data-id", t.id);

    var icon = doc.createElement("div");
    icon.className = "tool-icon";
    if (t.icon && t.icon.indexOf("<svg") === 0) {
      icon.innerHTML = t.icon;
      icon.classList.add("tool-icon--svg");
    } else {
      icon.textContent = t.icon || "🔧";
    }

    var title = doc.createElement("h3");
    title.className = "tool-title";
    title.textContent = t.title;

    var desc = doc.createElement("p");
    desc.className = "tool-desc";
    desc.textContent = t.desc;

    var tags = doc.createElement("div");
    tags.className = "tool-tags";
    (t.tags || []).forEach(function (tag) {
      var s = doc.createElement("span");
      s.className = "tool-tag";
      s.textContent = tag;
      tags.appendChild(s);
    });

    card.appendChild(icon);
    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(tags);

    if (t.type === "external" && t.url) {
      card.classList.add("is-link");
      card.tabIndex = 0;
      card.setAttribute("role", "link");
      card.setAttribute("aria-label", t.title + "（在新标签页打开）");
      var go = doc.createElement("span");
      go.className = "tool-go";
      go.textContent = "进入 ↗";
      card.appendChild(go);
      var open = function () { window.open(t.url, "_blank", "noopener,noreferrer"); };
      card.addEventListener("click", open);
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); }
      });
    } else if (t.type === "native" && t.url) {
      card.classList.add("is-link");
      card.tabIndex = 0;
      var goN = doc.createElement("span");
      goN.className = "tool-go";
      goN.textContent = "打开 →";
      card.appendChild(goN);
      var goNative = function () { window.location.href = t.url; };
      card.addEventListener("click", goNative);
      card.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); goNative(); }
      });
    }
    /* planned：不绑定跳转，CSS 自动显示「敬请期待」 */
    return card;
  }

  function renderGrid() {
    grid.innerHTML = "";
    var matched = tools.filter(passes);
    if (matched.length === 0) {
      var empty = doc.createElement("div");
      empty.className = "tool-empty";
      empty.textContent = "没有匹配的工具，换个关键词试试？";
      grid.appendChild(empty);
    } else {
      matched.forEach(function (t) { grid.appendChild(makeCard(t)); });
    }
    if (countEl) {
      countEl.textContent = "共 " + matched.length + " / " + tools.length + " 个工具";
    }
    applySquircleAll();
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      query = searchInput.value.trim().toLowerCase();
      renderGrid();
    });
  }

  /* ======================================================================
     4. squircle（连续曲率圆角 / 超椭圆）
     border-radius 只能画椭圆弧，曲率在接缝处不连续；
     squircle 用超椭圆 |x/a|^n + |y/b|^n = 1（n=4 即经典 iOS 圆角），
     在角部平滑过渡。这里按每张卡片的实际像素尺寸生成 path，写到 clip-path。
     无 JS 时回退到 CSS 的 border-radius（仍是普通圆角，但不影响可用性）。
     ====================================================================== */
  var SQUIRCLE_N = 4;          // 超椭圆指数，越大越接近直角；4 = 经典 squircle
  var SQUIRCLE_STEPS = 80;     // 路径采样点数

  function squirclePath(w, h, n, steps) {
    var cx = w / 2, cy = h / 2, a = w / 2, b = h / 2;
    var exp = 2 / n;            // 超椭圆参数化里的指数
    var d = "";
    for (var i = 0; i <= steps; i++) {
      var t = (i / steps) * Math.PI * 2;
      var c = Math.cos(t), s = Math.sin(t);
      var x = cx + a * Math.sign(c) * Math.pow(Math.abs(c), exp);
      var y = cy + b * Math.sign(s) * Math.pow(Math.abs(s), exp);
      d += (i === 0 ? "M " : "L ") + x.toFixed(2) + " " + y.toFixed(2) + " ";
    }
    return d + "Z";
  }

  function applySquircle(el) {
    if (!el || !el.getBoundingClientRect) return;
    var r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    var p = 'path("' + squirclePath(r.width, r.height, SQUIRCLE_N, SQUIRCLE_STEPS) + '")';
    el.style.clipPath = p;
    el.style.webkitClipPath = p;
  }

  function applySquircleAll() {
    var cards = grid.querySelectorAll(".tool-card");
    for (var i = 0; i < cards.length; i++) applySquircle(cards[i]);
  }

  /* 窗口尺寸变化 → 卡片尺寸变化 → 重新生成 squircle */
  var resizeQueued = false;
  function onResize() {
    if (resizeQueued) return;
    resizeQueued = true;
    if (window.requestAnimationFrame) {
      window.requestAnimationFrame(function () { resizeQueued = false; applySquircleAll(); });
    } else {
      setTimeout(function () { resizeQueued = false; applySquircleAll(); }, 80);
    }
  }
  window.addEventListener("resize", onResize);
  window.addEventListener("orientationchange", onResize);

  /* 字体加载完再画一次（字体宽度差异可能改变卡片高度） */
  if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) {
    doc.fonts.ready.then(function () { applySquircleAll(); }).catch(function () {});
  }

  /* ── 启动 ── */
  renderChips();
  renderGrid();
})();
