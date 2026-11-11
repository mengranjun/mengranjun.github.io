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
  /* ======================================================================
     4. squircle（连续曲率圆角）
     border-radius 的圆角是圆弧，弧与直边相接处曲率会「突然归零」，
     视觉上留下一道生硬的接缝。Apple 式做法的思路是：角部沿超椭圆曲线
     过渡（曲率连续变化），再平滑地接入直边。
     这里为每张卡片按实际像素尺寸生成「直边 + 四段超椭圆转角」的路径，
     写到 clip-path。转角尺寸随卡片自适应，指数 n≈5 接近 iOS 图标观感。
     无 JS 时回退到 CSS 的 border-radius（普通圆角，仍可用）。
     ====================================================================== */
  var SQUIRCLE_N = 5;          // 超椭圆指数：越大角部越「方」，5 接近 iOS
  var SQUIRCLE_STEPS = 14;     // 每个转角的采样段数

  function squirclePath(w, h, n) {
    var exp = 2 / n;
    // 转角尺寸随卡片短边自适应（18~30px），再按半宽半高兜底
    var r = Math.min(Math.max(18, Math.min(w, h) * 0.14), 30);
    r = Math.min(r, w / 2, h / 2);

    // 以 (cx, cy) 为中心、半径 r 的超椭圆象限；a0 为起始角，跨 90°
    function corner(cx, cy, a0) {
      var pts = [];
      for (var i = 0; i <= SQUIRCLE_STEPS; i++) {
        var t = a0 + (i / SQUIRCLE_STEPS) * Math.PI / 2;
        var c = Math.cos(t), s = Math.sin(t);
        pts.push([
          cx + r * Math.sign(c) * Math.pow(Math.abs(c), exp),
          cy + r * Math.sign(s) * Math.pow(Math.abs(s), exp)
        ]);
      }
      return pts;
    }

    // 顺时针：上边 → 右上角 → 右边 → 右下角 → 下边 → 左下角 → 左边 → 左上角
    var pts = [[r, 0]];
    pts = pts.concat(corner(w - r, r, -Math.PI / 2));       // 右上
    pts.push([w, h - r]);
    pts = pts.concat(corner(w - r, h - r, 0));              // 右下
    pts.push([r, h]);
    pts = pts.concat(corner(r, h - r, Math.PI / 2));        // 左下
    pts.push([0, r]);
    pts = pts.concat(corner(r, r, Math.PI));                // 左上

    var d = "";
    for (var j = 0; j < pts.length; j++) {
      d += (j === 0 ? "M " : "L ") + pts[j][0].toFixed(2) + " " + pts[j][1].toFixed(2) + " ";
    }
    return d + "Z";
  }

  function applySquircle(el) {
    if (!el || !el.getBoundingClientRect) return;
    var r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) return;
    var p = 'path("' + squirclePath(r.width, r.height, SQUIRCLE_N) + '")';
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
