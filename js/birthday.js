/* ==========================================================================
   MurojBlog — birthday.js
   10 月 20 日的生日彩蛋，只在首页加载。

   进入首页时：左下 / 右下角放礼花，hero 右侧出现一个简约蛋糕。
   点蛋糕：缩一下再弹回原样 + 小黄鸭「嘎」的一声 + 再放一轮礼花。
   礼花最多放 10 轮，防止被连点把浏览器干趴下。

   想提前预览（不用等到 10 月 20 日）：在地址后面加 #birthday
     http://localhost:8080/index.html#birthday
   ========================================================================== */
(function () {
  "use strict";

  var doc = document;

  /* ---- 可调参数 ---- */
  var BIRTHDAY_MONTH = 9;      // 0 = 一月，所以 9 = 十月
  var BIRTHDAY_DAY = 20;       // 20号
  var MAX_BURSTS = 10;         // 礼花最多放 10 轮
  var PER_BURST = 72;          // 每一角每轮喷多少颗粒
  var MAX_PARTICLES = 700;     // 全屏同时在跑的颗粒上限（保险丝）

  /* ---- 只在生日当天启用；加 #birthday 可提前预览 ---- */
  var now = new Date();
  var forced = /[?&#]birthday/i.test(location.href);
  if (!forced && !(now.getMonth() === BIRTHDAY_MONTH && now.getDate() === BIRTHDAY_DAY)) return;

  if (!window.requestAnimationFrame) return;

  var hero = doc.querySelector(".hero .container") || doc.querySelector(".hero");
  if (!hero) return;

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var bursts = 0;

  var COLORS = ["#0ea5e9", "#06b6d4", "#10b981", "#22d3ee", "#fbbf24", "#f472b6"];

  /* ======================================================================
     1. 蛋糕
     ====================================================================== */
  var CAKE_SVG =
    '<svg viewBox="0 0 120 128" aria-hidden="true">' +
      '<defs>' +
        '<linearGradient id="bdayGrad" x1="0" y1="0" x2="1" y2="1">' +
          '<stop offset="0" style="stop-color:var(--grad-1)"/>' +
          '<stop offset="0.5" style="stop-color:var(--grad-2)"/>' +
          '<stop offset="1" style="stop-color:var(--grad-3)"/>' +
        '</linearGradient>' +
      '</defs>' +
      '<g class="bday-body">' +
        /* 盘子 */
        '<ellipse cx="60" cy="116" rx="46" ry="6.5" fill="currentColor" opacity="0.1"/>' +
        /* 下层 */
        '<rect x="18" y="78" width="84" height="34" rx="10" fill="url(#bdayGrad)"/>' +
        /* 下层滴落的奶油 */
        '<path d="M18 84c0-6 5-10 10-10h64c5 0 10 4 10 10v2c-6 0-6 7-12 7s-6-7-12-7-6 7-12 7-6-7-12-7-6 7-12 7-6-7-12-7z" ' +
          'fill="#fff" opacity="0.9"/>' +
        /* 上层 */
        '<rect x="34" y="50" width="52" height="30" rx="9" fill="url(#bdayGrad)" opacity="0.94"/>' +
        /* 上层奶油 */
        '<path d="M34 56c0-5 4-9 9-9h34c5 0 9 4 9 9v2c-5 0-5 6-10 6s-5-6-10-6-5 6-10 6-5-6-10-6-5 6-10 6z" ' +
          'fill="#fff" opacity="0.9"/>' +
        /* 蜡烛 */
        '<rect x="57" y="26" width="6" height="24" rx="3" fill="#fff" opacity="0.95"/>' +
        '<rect x="57" y="26" width="6" height="24" rx="3" fill="url(#bdayGrad)" opacity="0.35"/>' +
        /* 烛火 */
        '<path class="bday-flame" d="M60 8c5.4 6.2 7.6 10.4 7.6 13.6A7.6 7.6 0 0 1 52.4 21.6C52.4 18.4 54.6 14.2 60 8z" ' +
          'fill="#fbbf24"/>' +
        '<path class="bday-flame" d="M60 13.5c2.6 3.1 3.6 5.2 3.6 6.8a3.6 3.6 0 0 1-7.2 0c0-1.6 1-3.7 3.6-6.8z" ' +
          'fill="#fff" opacity="0.85"/>' +
      '</g>' +
    '</svg>';

  var cake = doc.createElement("button");
  cake.className = "bday-cake";
  cake.type = "button";
  cake.setAttribute("aria-label", "10 月 20 日生日蛋糕，点一下有惊喜");
  cake.innerHTML = CAKE_SVG;
  hero.appendChild(cake);

  // 稍微等首屏文字淡入完，再让蛋糕浮现
  window.setTimeout(function () { cake.classList.add("is-in"); }, reduced ? 0 : 300);

  /* ======================================================================
     2. 礼花：左下 / 右下两个 canvas
     ====================================================================== */
  var fx = [];

  function makeFX(side) {
    var cv = doc.createElement("canvas");
    cv.className = "bday-fx bday-fx-" + side;
    cv.setAttribute("aria-hidden", "true");
    doc.body.appendChild(cv);

    var ctx = cv.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = 0, h = 0, parts = [], running = false, last = 0;

    function size() {
      var r = cv.getBoundingClientRect();
      w = r.width || 340;
      h = r.height || 340;
      cv.width = Math.round(w * dpr);
      cv.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function spawn() {
      // 从左下角往上打，从右下角也往上打，方向朝屏幕中间偏
      var ox = side === "left" ? 22 : w - 22;
      var oy = h - 8;
      var dir = side === "left" ? 1 : -1;
      var budget = Math.min(PER_BURST, MAX_PARTICLES - totalParticles());
      for (var i = 0; i < budget; i++) {
        var ang = (-60 + Math.random() * 62) * Math.PI / 180;   // 主要往上
        var spd = 5 + Math.random() * 9;
        parts.push({
          x: ox + (Math.random() - 0.5) * 26,
          y: oy - Math.random() * 18,
          vx: Math.cos(ang) * spd * dir * (0.55 + Math.random() * 0.8),
          vy: Math.sin(ang) * spd,
          life: 1,
          decay: 0.008 + Math.random() * 0.012,
          size: 1.8 + Math.random() * 2.6,
          color: COLORS[(Math.random() * COLORS.length) | 0],
          spin: (Math.random() - 0.5) * 0.3,
          rot: Math.random() * Math.PI
        });
      }
    }

    function frame(t) {
      if (!last) last = t;
      var dt = Math.min(48, t - last) / 16.67;
      last = t;

      ctx.clearRect(0, 0, w, h);
      var alive = 0;
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i];
        if (p.life <= 0) continue;
        p.vy += 0.17 * dt;              // 重力
        p.vx *= Math.pow(0.985, dt);    // 空气阻力
        p.vy *= Math.pow(0.99, dt);
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.rot += p.spin * dt;
        p.life -= p.decay * dt;
        if (p.life <= 0) continue;
        alive++;

        ctx.globalAlpha = Math.max(0, p.life);
        ctx.fillStyle = p.color;
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 1.6);
        ctx.restore();
      }
      ctx.globalAlpha = 1;

      if (alive) {
        requestAnimationFrame(frame);
      } else {
        parts.length = 0;
        running = false;
        cv.classList.remove("on");
      }
    }

    size();
    window.addEventListener("resize", size);

    return {
      node: cv,
      fire: function () {
        if (reduced) return;
        cv.classList.add("on");
        spawn();
        if (!running) { running = true; last = 0; requestAnimationFrame(frame); }
      },
      count: function () { return parts.length; }
    };
  }

  function totalParticles() {
    var n = 0;
    for (var i = 0; i < fx.length; i++) n += fx[i].count();
    return n;
  }

  fx.push(makeFX("left"));
  fx.push(makeFX("right"));

  /* ======================================================================
     3. 小黄鸭「嘎」—— 用 Web Audio 现场合成，不依赖任何音频文件
     ====================================================================== */
  var actx = null;

  function squeak() {
    var AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    try {
      if (!actx) actx = new AC();
      if (actx.state === "suspended" && actx.resume) actx.resume();

      var t0 = actx.currentTime;
      // 两声短促的「嘎」，第二声略高一点点，像鸭子
      for (var i = 0; i < 2; i++) {
        var t = t0 + i * 0.13;
        var osc = actx.createOscillator();
        var bp = actx.createBiquadFilter();
        var gain = actx.createGain();

        osc.type = "sawtooth";
        // 音高先窜上去再落回来，这一步是「嘎」的灵魂
        osc.frequency.setValueAtTime(560 + i * 70, t);
        osc.frequency.exponentialRampToValueAtTime(1450 + i * 120, t + 0.045);
        osc.frequency.exponentialRampToValueAtTime(680 + i * 60, t + 0.105);

        bp.type = "bandpass";
        bp.frequency.setValueAtTime(1500, t);
        bp.Q.value = 5.5;

        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.2, t + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.11);

        osc.connect(bp); bp.connect(gain); gain.connect(actx.destination);
        osc.start(t);
        osc.stop(t + 0.13);
      }
    } catch (e) { /* 浏览器不给放声音就算了，不影响其他效果 */ }
  }

  /* ======================================================================
     4. 进页面先放一轮
     ====================================================================== */
  function burst() {
    // if (bursts >= MAX_BURSTS) return false; //可开可不开 烟花 >= 烟花总数回F
    bursts++;
    for (var i = 0; i < fx.length; i++) fx[i].fire();
    return true;
  }

  window.setTimeout(burst, reduced ? 0 : 500);

  /* ======================================================================
     5. 点蛋糕
     ====================================================================== */
  var tip = null;

  function showDoneTip() {
    if (tip) return;
    tip = doc.createElement("div");
    tip.className = "bday-done-tip";
    tip.setAttribute("role", "status");
    tip.textContent = "礼花放满 " + MAX_BURSTS + " 次啦，浏览器也要喘口气 🎂";
    doc.body.appendChild(tip);
    window.setTimeout(function () { tip.classList.add("show"); }, 30);
    window.setTimeout(function () {
      if (tip) { tip.classList.remove("show"); }
    }, 4200);
  }

  cake.addEventListener("click", function () {
    // ① 缩小 → 弹回原样（先摘掉再加，连点也能重播）
    cake.classList.remove("is-pop");
    void cake.offsetWidth;          // 强制回流，让动画能重新触发
    cake.classList.add("is-pop");
    // animationend 在「减少动效」时不会触发，用定时器兜底清掉 class
    window.setTimeout(function () { cake.classList.remove("is-pop"); }, 720);

    // ② 小黄鸭「嘎」
    squeak();

    // ③ 再放一轮礼花（有上限）
    if (!burst()) showDoneTip();
  });

  cake.addEventListener("animationend", function () {
    cake.classList.remove("is-pop");
  });
})();
