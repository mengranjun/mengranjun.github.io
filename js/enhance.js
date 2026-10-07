/* ==========================================================================
   MurojBlog — enhance.js
   渐进增强的交互效果。每个效果都会先检查页面上有没有对应元素，
   没有就静默跳过，所以这一个文件在所有页面通用。

   1. 主题切换的圆形扩散      （逻辑在 main.js，这里只补样式钩子）
   2. 首页跟随光标的柔光
   3. 文章卡片 3D 倾斜 + 高光
   4. 命令面板 Ctrl / Cmd + K
   5. 文章目录的滚动高亮
   6. 首页标题打字机
   7. 姓名彩蛋（多名字 + 滚轮切换）
   8. 回到顶部 + 阅读进度环
   9. 继续阅读提示（记住上次读到哪）
   ========================================================================== */
(function () {
  "use strict";

  var doc = document;
  var root = doc.documentElement;

  // 本文件所在目录，用来在文章页（posts/）里拼出 ../ 前缀
  var selfSrc = (doc.currentScript && doc.currentScript.getAttribute("src")) || "js/enhance.js";
  var PREFIX = selfSrc.replace(/js\/enhance\.js.*$/, "");

  var reduceMq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var reduced = !!(reduceMq && reduceMq.matches);
  var fineMq = window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : null;
  var canHover = !(fineMq && !fineMq.matches);
  var raf = window.requestAnimationFrame || function (f) { return setTimeout(f, 16); };

  function $(sel, ctx) { return (ctx || doc).querySelector(sel); }
  function $$(sel, ctx) { return Array.prototype.slice.call((ctx || doc).querySelectorAll(sel)); }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }


  /* ======================================================================
     6. 首页标题打字机（放最前面，尽早接管，避免闪一下完整标题）
     ====================================================================== */
  (function typewriter() {
    var h1 = $(".hero h1");
    if (!h1 || reduced) return;

    var source = h1.innerHTML;

    // 把 HTML 拆成「一个字 / 换行 / 开标签 / 闭标签」的序列
    var toks = [];
    (function walk(node) {
      Array.prototype.forEach.call(node.childNodes, function (n) {
        if (n.nodeType === 3) {
          var txt = n.textContent;
          for (var i = 0; i < txt.length; i++) toks.push({ k: "c", v: txt[i] });
        } else if (n.nodeType === 1) {
          if (n.tagName === "BR") { toks.push({ k: "br" }); return; }
          toks.push({ k: "o", tag: n.tagName, cls: n.className });
          walk(n);
          toks.push({ k: "x", tag: n.tagName });
        }
      });
    })((function () { var t = doc.createElement("div"); t.innerHTML = source; return t; })());

    var total = toks.filter(function (t) { return t.k === "c"; }).length;
    if (total < 4) return;

    function paint(n) {
      // 结构（<br>、<em>）始终完整输出，只控制"字"显示到第几个，
      // 这样标题高度从头到尾都是两行，不会打字时上下跳。
      var out = "", open = [], count = 0, caretDone = false;

      function caret() {
        if (!caretDone) { out += '<span class="tw-caret" aria-hidden="true"></span>'; caretDone = true; }
      }

      for (var i = 0; i < toks.length; i++) {
        var t = toks[i];
        if (t.k === "c") {
          if (count < n) out += esc(t.v);
          else caret();
          count++;
        } else if (t.k === "br") {
          out += "<br>";
        } else if (t.k === "o") {
          out += "<" + t.tag + (t.cls ? ' class="' + t.cls + '"' : "") + ">";
          open.push(t.tag);
        } else {
          out += "</" + t.tag + ">";
          open.pop();
        }
      }
      caret();
      while (open.length) out += "</" + open.pop() + ">";
      h1.innerHTML = out;
    }

    h1.setAttribute("aria-label", h1.textContent);
    var n = 0;
    paint(0);
    (function tick() {
      n++;
      paint(n);
      if (n < total) {
        window.setTimeout(tick, 52 + (Math.random() * 34));
      } else {
        window.setTimeout(function () {
          var c = $(".tw-caret", h1);
          if (c) c.remove();
        }, 900);
      }
    })();
  })();


  /* ======================================================================
     2. 首页：跟随光标的柔光
     ====================================================================== */
  (function heroGlow() {
    var hero = $(".hero");
    if (!hero || reduced || !canHover) return;

    var tx = 62, ty = 28, cx = tx, cy = ty, running = false;

    function step() {
      cx += (tx - cx) * 0.12;
      cy += (ty - cy) * 0.12;
      hero.style.setProperty("--mx", cx.toFixed(2) + "%");
      hero.style.setProperty("--my", cy.toFixed(2) + "%");
      if (Math.abs(tx - cx) > 0.08 || Math.abs(ty - cy) > 0.08) raf(step);
      else running = false;
    }

    hero.addEventListener("pointermove", function (e) {
      var r = hero.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width) * 100;
      ty = ((e.clientY - r.top) / r.height) * 100;
      hero.classList.add("is-tracking");
      if (!running) { running = true; raf(step); }
    });

    hero.addEventListener("pointerleave", function () {
      hero.classList.remove("is-tracking");
    });
  })();


  /* ======================================================================
     3. 文章卡片：3D 倾斜 + 跟着光标的高光
     ====================================================================== */
  (function cardTilt() {
    var cards = $$(".post-card");
    if (!cards.length || reduced || !canHover) return;

    cards.forEach(function (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        var px = (e.clientX - r.left) / r.width;
        var py = (e.clientY - r.top) / r.height;
        card.style.setProperty("--rx", ((0.5 - py) * 6).toFixed(2) + "deg");
        card.style.setProperty("--ry", ((px - 0.5) * 8).toFixed(2) + "deg");
        card.style.setProperty("--sheen-x", (px * 100).toFixed(1) + "%");
        card.style.setProperty("--sheen-y", (py * 100).toFixed(1) + "%");
      });
      card.addEventListener("pointerleave", function () {
        card.style.removeProperty("--rx");
        card.style.removeProperty("--ry");
      });
    });
  })();


  /* ======================================================================
     5. 文章目录：滚动时高亮当前小节
     ====================================================================== */
  (function tocHighlight() {
    var links = $$(".toc-list a");
    if (!links.length) return;

    var targets = links.map(function (a) {
      var raw = a.getAttribute("href").slice(1);
      var el = doc.getElementById(raw);
      if (!el) { try { el = doc.getElementById(decodeURIComponent(raw)); } catch (e) {} }
      return el;
    });

    var current = -1;
    function update() {
      var y = window.pageYOffset + 130;
      var idx = 0;
      for (var i = 0; i < targets.length; i++) {
        if (targets[i] && targets[i].getBoundingClientRect().top + window.pageYOffset <= y) idx = i;
      }
      // 滚到底部时强制高亮最后一节
      if (window.innerHeight + window.pageYOffset >= doc.documentElement.scrollHeight - 4) {
        idx = targets.length - 1;
      }
      if (idx === current) return;
      current = idx;
      links.forEach(function (a, i) {
        a.classList.toggle("active", i === idx);
        if (i === idx) a.setAttribute("aria-current", "true");
        else a.removeAttribute("aria-current");
      });
    }

    var queued = false;
    window.addEventListener("scroll", function () {
      if (queued) return;
      queued = true;
      raf(function () { queued = false; update(); });
    }, { passive: true });

    window.addEventListener("resize", update);
    update();
  })();


  /* ======================================================================
     7. 姓名彩蛋：支持任意多个名字 +「余韵」
     桌面端：悬浮展开菜单 → 滚轮在名字之间切换 → 鼠标移开菜单保持展开
     移动端：点一下切到下一个名字
     键盘  ：聚焦后 ↑ / ↓ 切换，Esc 收起
     ====================================================================== */
  (function aliasSwitcher() {
    var alias = $(".alias");
    if (!alias) return;

    var menu = $(".alias-menu", alias);
    var opts = $$(".alias-opt", alias);
    var names = $$(".alias-name", alias);
    var stage = $(".alias-stage", alias);
    var grid = $(".about-grid");
    var n = Math.min(opts.length, names.length);
    if (!menu || n < 1) return;

    var coarseMq = window.matchMedia ? window.matchMedia("(hover: none), (pointer: coarse)") : null;
    var coarse = !!(coarseMq && coarseMq.matches);
    var cur = 0;
    var open = false;
    var timer = null;
    var CHOSEN = "muroj-alias-chosen";
    var header = $(".site-header");

    /* ---- 框宽跟随当前名字 ----
       名字全部叠在同一格，舞台宽度本来会被「最长的名字」撑死。
       这里逐个量出每个名字的真实宽度，切换时把当前宽度显式写到 stage 上，
       配合 css/style.css 里 .alias-stage 的 width 过渡，外框平滑伸缩。 */
    var stagePadX = 0;
    var nameWidths = null;

    function measureNames() {
      if (!stage) return;
      var ps = window.getComputedStyle(stage);
      stagePadX = (parseFloat(ps.paddingLeft) || 0) + (parseFloat(ps.paddingRight) || 0);
      nameWidths = names.map(function (el) {
        var cs = window.getComputedStyle(el);
        var probe = doc.createElement("span");
        probe.style.position = "absolute";
        probe.style.visibility = "hidden";
        probe.style.whiteSpace = "nowrap";
        probe.style.font = cs.font ||
          (cs.fontStyle + " " + cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily);
        probe.style.letterSpacing = cs.letterSpacing;
        probe.textContent = el.textContent;
        doc.body.appendChild(probe);
        var w = probe.getBoundingClientRect().width;
        doc.body.removeChild(probe);
        return w;
      });
    }

    function fitName() {
      if (!stage || !nameWidths || !nameWidths[cur]) return;
      // +1px 余量，避免个别字体下边缘像素被 overflow:hidden 裁掉
      stage.style.width = Math.ceil(nameWidths[cur] + stagePadX + 1) + "px";
    }

    // 纯拉丁字母的名字自动换成无衬线粗体，中文名保持衬线体
    names.forEach(function (el) {
      if (/^[\x20-\x7E]+$/.test(el.textContent.trim())) el.classList.add("is-latin");
    });

    /* 名字贴着置顶导航时，菜单往上弹会被挡住 —— 量一下上方还剩多少空间，
       不够就翻到名字下面去。 */
    function placeMenu() {
      var room = alias.getBoundingClientRect().top -
                 (header ? header.getBoundingClientRect().bottom : 0);
      alias.classList.toggle("is-flip", room < menu.offsetHeight + 26);
    }

    function render() {
      menu.style.setProperty("--sel", cur);
      opts.forEach(function (o, i) { o.classList.toggle("is-on", i === cur); });
      names.forEach(function (el, i) {
        var off = i - cur;
        el.style.setProperty("--off", off);
        el.classList.toggle("is-on", off === 0);
      });
      // 描述跟着「当前选中的名字」走，而不是跟着「菜单开着」走
      alias.classList.toggle("is-alt", cur > 0);
      fitName();   // 外框宽度跟着当前名字走
    }

    function setOpen(v) {
      open = v;
      if (v) placeMenu();
      alias.classList.toggle("is-open", v);
    }

    function select(i) {
      if (i < 0 || i >= n || i === cur) return false;
      cur = i;
      render();
      if (fitSwap) window.setTimeout(fitSwap, 320);   // 描述容器高度跟着当前那一段
      return true;
    }

    function markChosen() {
      if (grid) grid.classList.add("is-chosen");
      try { sessionStorage.setItem(CHOSEN, "1"); } catch (e) {}
    }

    try { if (grid && sessionStorage.getItem(CHOSEN) === "1") grid.classList.add("is-chosen"); } catch (e) {}

    /* ---- 让描述容器的高度跟随当前显示的那一段（方案 B 专用）---- */
    var fitSwap = null;
    var swap = $(".about-swap");
    if (swap) {
      var kids = Array.prototype.filter.call(swap.children, function (nd) { return nd.nodeType === 1; });
      var altIdx = -1;
      kids.forEach(function (nd, i) {
        if (nd.classList && nd.classList.contains("about-swap-alt")) altIdx = i;
      });
      if (altIdx > 0) {
        swap.style.overflow = "hidden";
        swap.style.transition = "height 0.42s cubic-bezier(0.22, 1, 0.36, 1)";
        fitSwap = function () {
          var el = kids[alias.classList.contains("is-alt") ? altIdx : 0];
          if (!el) return;
          var mb = parseFloat(window.getComputedStyle(el).marginBottom) || 0;
          swap.style.height = Math.round(el.getBoundingClientRect().height + mb) + "px";
        };
        fitSwap();
        window.addEventListener("resize", fitSwap);
        if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) {
          doc.fonts.ready.then(function () { fitSwap(); }).catch(function () {});
        }
      }
    }

    measureNames();
    render();

    /* 字体加载完成 / 窗口尺寸变化后，名字宽度可能变，重新量一遍 */
    window.addEventListener("resize", function () { measureNames(); fitName(); });
    if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) {
      doc.fonts.ready.then(function () { measureNames(); fitName(); }).catch(function () {});
    }

    /* ---- 滚动 / 改窗口大小时重新判断菜单该往上还是往下弹 ---- */
    var placeQueued = false;
    function queuePlace() {
      if (!open || placeQueued) return;
      placeQueued = true;
      raf(function () { placeQueued = false; placeMenu(); });
    }
    window.addEventListener("scroll", queuePlace, { passive: true });
    window.addEventListener("resize", placeMenu);
    placeMenu();

    /* ---- 桌面：悬浮展开，且不因鼠标移开而收起 ---- */
    if (!coarse) {
      alias.addEventListener("pointerenter", function () {
        setOpen(true);
        markChosen();
      });
    }

    /* ---- 滚轮切换名字 ---- */
    alias.addEventListener("wheel", function (e) {
      if (coarse || !open) return;
      var dir = e.deltaY > 0 ? 1 : -1;
      // 已经滚到列表两端就放行，让页面正常滚动，别把用户"卡"在这里
      if (!select(cur + dir)) return;
      e.preventDefault();
    }, { passive: false });

    /* ---- 移动端：点一下切到下一个（循环） ---- */
    alias.addEventListener("click", function (e) {
      if (!coarse) return;
      e.preventDefault();
      select((cur + 1) % n);
      setOpen(true);
      markChosen();
      clearTimeout(timer);
      timer = setTimeout(function () { setOpen(false); }, 2200);
    });

    /* ---- 键盘 ---- */
    alias.addEventListener("keydown", function (e) {
      var k = e.key;
      if (k === "ArrowDown" || k === "ArrowRight" || k === "Enter" || k === " ") {
        e.preventDefault();
        setOpen(true);
        markChosen();
        select(cur + 1 < n ? cur + 1 : 0);
      } else if (k === "ArrowUp" || k === "ArrowLeft") {
        e.preventDefault();
        setOpen(true);
        markChosen();
        select(cur - 1 >= 0 ? cur - 1 : n - 1);
      }
    });

    /* ---- Esc / 点击别处 收起 ---- */
    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && open) setOpen(false);
    });
    doc.addEventListener("click", function (e) {
      if (!open) return;
      if (e.target === alias || alias.contains(e.target)) return;
      setOpen(false);
    });
  })();


  /* ======================================================================
     8. 回到顶部 + 阅读进度环
     ====================================================================== */
  (function backToTop() {
    var CIRC = 119.4; // 2πr, r = 19

    var btn = doc.createElement("button");
    btn.className = "to-top";
    btn.type = "button";
    btn.setAttribute("aria-label", "回到顶部");
    btn.innerHTML =
      '<svg class="ring" viewBox="0 0 46 46" aria-hidden="true">' +
        '<circle class="to-top-track" cx="23" cy="23" r="19"/>' +
        '<circle class="to-top-arc" cx="23" cy="23" r="19"/>' +
      "</svg>" +
      '<svg class="arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>';
    doc.body.appendChild(btn);

    var arc = $(".to-top-arc", btn);
    var queued = false;

    function update() {
      var d = doc.documentElement;
      var total = d.scrollHeight - d.clientHeight;
      var p = total > 0 ? Math.min(1, Math.max(0, window.pageYOffset / total)) : 0;
      arc.style.strokeDashoffset = (CIRC - CIRC * p).toFixed(1);
      btn.classList.toggle("show", window.pageYOffset > 420);
    }

    window.addEventListener("scroll", function () {
      if (queued) return;
      queued = true;
      raf(function () { queued = false; update(); });
    }, { passive: true });

    btn.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
    });

    update();
  })();


  /* ======================================================================
     4. 命令面板：Ctrl / Cmd + K
     ====================================================================== */
  (function commandPalette() {
    var PAGES = [
      { t: "首页", u: "index.html", kind: "页面" },
      { t: "归档", u: "archive.html", kind: "页面" },
      { t: "关于", u: "about.html", kind: "页面" },
      { t: "RSS 订阅", u: "feed.xml", kind: "页面" }
    ];

    var posts = null;
    var loading = false;
    var panel = null, input = null, list = null;
    var items = [], active = 0, lastFocus = null;

    /* ---- 把搜索索引按需加载进来 ---- */
    function loadIndex(cb) {
      if (posts) { cb(); return; }
      if (window.__SEARCH_INDEX__) { posts = window.__SEARCH_INDEX__; cb(); return; }
      if (loading) return;
      loading = true;
      var s = doc.createElement("script");
      s.src = PREFIX + "js/search-index.js";
      s.onload = function () { posts = window.__SEARCH_INDEX__ || []; loading = false; cb(); };
      s.onerror = function () { posts = []; loading = false; cb(); };
      doc.head.appendChild(s);
    }

    /* ---- 极简打分：标题 > 标签 > 摘要 > 正文 ---- */
    function fuzzy(q, t) {
      var i = 0;
      for (var k = 0; k < t.length && i < q.length; k++) if (t[k] === q[i]) i++;
      return i === q.length;
    }

    function scoreOf(item, q) {
      if (!q) return 1;
      var t = item.t.toLowerCase();
      var s = (item.s || "").toLowerCase();
      var b = (item.b || "").toLowerCase();
      var g = (item.g || []).join(" ").toLowerCase();
      var n = 0, at = t.indexOf(q);
      if (at >= 0) n += 120 - Math.min(at, 40);
      else if (fuzzy(q, t)) n += 45;
      if (g.indexOf(q) >= 0) n += 70;
      if (s.indexOf(q) >= 0) n += 30;
      if (b.indexOf(q) >= 0) n += 14;
      return n;
    }

    function highlight(text, q) {
      if (!q) return esc(text);
      var i = text.toLowerCase().indexOf(q);
      if (i < 0) return esc(text);
      return esc(text.slice(0, i)) + "<mark>" + esc(text.slice(i, i + q.length)) + "</mark>" +
             esc(text.slice(i + q.length));
    }

    function build(query) {
      var q = query.trim().toLowerCase();
      var out = [];

      PAGES.forEach(function (p) {
        if (!q || p.t.toLowerCase().indexOf(q) >= 0) out.push({ kind: p.kind, t: p.t, u: p.u, meta: "" });
      });

      var scored = (posts || []).map(function (it) {
        return { it: it, s: scoreOf(it, q) };
      }).filter(function (x) { return x.s > 0; })
        .sort(function (a, b) { return b.s - a.s || (a.it.d < b.it.d ? 1 : -1); })
        .slice(0, 40);

      scored.forEach(function (x) {
        out.push({
          kind: x.it.g && x.it.g[0] ? x.it.g[0] : "文章",
          t: x.it.t, u: x.it.u, meta: x.it.d, _q: q
        });
      });
      return out;
    }

    function render(query) {
      items = build(query);
      active = 0;
      if (!items.length) {
        list.innerHTML = '<li class="cmdk-empty">没有找到匹配的内容</li>';
        return;
      }
      list.innerHTML = items.map(function (it, i) {
        return '<li class="cmdk-item' + (i === 0 ? " is-active" : "") + '" role="option" ' +
          'aria-selected="' + (i === 0) + '" data-i="' + i + '">' +
          '<span class="cmdk-kind">' + esc(it.kind) + "</span>" +
          '<span class="cmdk-item-title">' + highlight(it.t, it._q || "") + "</span>" +
          (it.meta ? '<span class="cmdk-item-meta">' + esc(it.meta) + "</span>" : "") +
          "</li>";
      }).join("");
    }

    function setActive(i) {
      var nodes = $$(".cmdk-item", list);
      if (!nodes.length) return;
      active = (i + nodes.length) % nodes.length;
      nodes.forEach(function (n, k) {
        n.classList.toggle("is-active", k === active);
        n.setAttribute("aria-selected", k === active ? "true" : "false");
      });
      var cur = nodes[active];
      if (cur.scrollIntoView) cur.scrollIntoView({ block: "nearest" });
    }

    function open() {
      if (panel) { close(); return; }
      lastFocus = doc.activeElement;

      panel = doc.createElement("div");
      panel.className = "cmdk";
      panel.innerHTML =
        '<div class="cmdk-backdrop" data-cmdk-close></div>' +
        '<div class="cmdk-panel" role="dialog" aria-modal="true" aria-label="站内搜索">' +
          '<div class="cmdk-input-row">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
              'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/>' +
              '<path d="M20 20l-3.6-3.6"/></svg>' +
            '<input class="cmdk-input" type="text" autocomplete="off" spellcheck="false" ' +
              'placeholder="搜索文章、标签，或跳转到页面…" aria-label="搜索">' +
            '<kbd class="cmdk-esc">Esc</kbd>' +
          "</div>" +
          '<ul class="cmdk-results" role="listbox" aria-label="搜索结果"></ul>' +
          '<div class="cmdk-foot">' +
            "<span><kbd>↑</kbd><kbd>↓</kbd>选择</span>" +
            "<span><kbd>↵</kbd>打开</span>" +
            "<span><kbd>Esc</kbd>关闭</span>" +
            "<span><kbd>Ctrl</kbd><kbd>K</kbd>随时呼出</span>" +
          "</div>" +
        "</div>";

      doc.body.appendChild(panel);
      input = $(".cmdk-input", panel);
      list = $(".cmdk-results", panel);

      render("");
      loadIndex(function () { render(input.value); });
      input.focus();

      input.addEventListener("input", function () { render(input.value); });
      input.addEventListener("keydown", onKey);
      panel.addEventListener("mousedown", function (e) {
        if (e.target.closest("[data-cmdk-close]")) close();
      });
      list.addEventListener("mousemove", function (e) {
        var li = e.target.closest(".cmdk-item");
        if (li) setActive(parseInt(li.getAttribute("data-i"), 10));
      });
      list.addEventListener("click", function (e) {
        var li = e.target.closest(".cmdk-item");
        if (li) go(parseInt(li.getAttribute("data-i"), 10));
      });
      doc.addEventListener("keydown", onDocKey, true);
    }

    function close() {
      if (!panel) return;
      doc.removeEventListener("keydown", onDocKey, true);
      panel.remove();
      panel = input = list = null;
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    }

    function go(i) {
      var it = items[i];
      if (!it) return;
      if (/^https?:/.test(it.u)) window.location.href = it.u;
      else window.location.href = PREFIX + it.u;
    }

    function onKey(e) {
      if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
      else if (e.key === "Enter") { e.preventDefault(); go(active); }
      else if (e.key === "Escape") { e.preventDefault(); close(); }
    }

    function onDocKey(e) {
      if (e.key === "Escape") { e.preventDefault(); close(); }
    }

    // 全局快捷键：Ctrl / Cmd + K，以及不在输入框里时的 “/”
    doc.addEventListener("keydown", function (e) {
      var k = e.key;
      if ((e.ctrlKey || e.metaKey) && (k === "k" || k === "K")) {
        e.preventDefault();
        if (panel) close(); else open();
        return;
      }
      if (k === "/" && !panel) {
        var el = e.target;
        var tag = el && el.tagName ? el.tagName.toLowerCase() : "";
        if (tag === "input" || tag === "textarea" || (el && el.isContentEditable)) return;
        e.preventDefault();
        open();
      }
    });

    // 页头加一个搜索按钮（触屏用户没有 Ctrl+K）
    var nav = $(".main-nav");
    if (nav) {
      var b = doc.createElement("button");
      b.className = "nav-search";
      b.type = "button";
      b.setAttribute("aria-label", "站内搜索（快捷键 Ctrl 或 Cmd + K）");
      b.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
        'stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"/>' +
        '<path d="M20 20l-3.6-3.6"/></svg>';
      b.addEventListener("click", open);
      var toggle = $(".theme-toggle", nav);
      nav.insertBefore(b, toggle || null);
    }
  })();


  /* ======================================================================
     9. 继续阅读：记住上次读到哪，回来时给一个「继续阅读」的提示
     不自动跳转 —— 强行滚动页面比不恢复更烦人。
     ====================================================================== */
  (function resumeReading() {
    var body = $(".article-body");
    var hud = $(".progress-bar");
    if (!body || !hud) return;              // 只在文章页生效

    var KEY = "muroj-read:" + location.pathname;
    var save = null;
    try { save = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) {}

    var queued = false;
    function remember() {
      var d = doc.documentElement;
      var total = d.scrollHeight - d.clientHeight;
      if (total < 400) return;
      var pct = Math.round((window.pageYOffset / total) * 100);
      try { localStorage.setItem(KEY, JSON.stringify({ p: pct, t: Date.now() })); } catch (e) {}
    }

    window.addEventListener("scroll", function () {
      if (queued) return;
      queued = true;
      raf(function () { queued = false; remember(); });
    }, { passive: true });

    // 刚写过不到 5 秒就刷新（比如误按 F5）不弹提示
    if (!save || typeof save.p !== "number" || save.p < 8 || save.p > 92) return;
    if (Date.now() - (save.t || 0) < 5000) return;

    var box = doc.createElement("div");
    box.className = "resume";
    box.setAttribute("role", "status");
    box.innerHTML =
      '<span class="resume-text">上次读到 <b>' + save.p + '%</b></span>' +
      '<button class="resume-btn" type="button">继续阅读</button>' +
      '<button class="resume-close" type="button" aria-label="关闭提示">&times;</button>';
    doc.body.appendChild(box);

    function hide() { box.classList.remove("show"); window.setTimeout(function () { box.remove(); }, 400); }

    $(".resume-btn", box).addEventListener("click", function () {
      var d = doc.documentElement;
      var total = d.scrollHeight - d.clientHeight;
      window.scrollTo({ top: total * save.p / 100, behavior: reduced ? "auto" : "smooth" });
      hide();
    });
    $(".resume-close", box).addEventListener("click", hide);

    window.setTimeout(function () { box.classList.add("show"); }, 700);
    window.setTimeout(hide, 14000);
  })();

})();
