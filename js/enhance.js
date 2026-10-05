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
   7. 姓名彩蛋的「余韵」
   8. 回到顶部 + 阅读进度环
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
     7. 姓名彩蛋的「余韵」：玩过一次之后记住这个选择
     ====================================================================== */
  (function aliasAfterglow() {
    var grid = $(".about-grid");
    var alias = $(".alias");
    if (!grid || !alias) return;

    var KEY = "muroj-alias-chosen";

    function mark() {
      grid.classList.add("is-chosen");
      try { sessionStorage.setItem(KEY, "1"); } catch (e) {}
    }

    try { if (sessionStorage.getItem(KEY) === "1") grid.classList.add("is-chosen"); } catch (e) {}

    alias.addEventListener("pointerenter", mark, { once: true });
    alias.addEventListener("focus", mark, { once: true });
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

})();
