/* ==========================================================================
   MurojBlog — 小工具集合 · 工具注册表
   ==========================================================================
   这是「小工具」页的数据源。js/tools.js 会读取本文件渲染卡片。

   ── 加一个工具，只需要在本数组里加一条 ──

   每条字段说明：
     id     必填，唯一标识（英文/数字/连字符），用作卡片 key 和原生工具目录名
     title  必填，工具名称
     desc   必填，一句话介绍（会显示在卡片上）
     icon   必填，emoji 字符（如 "🏛️"）或一段 SVG 字符串
     tags   必填，标签数组，用于筛选；建议 1-3 个
     type   必填，取值：
              "external" → 外部网站，新标签页打开（url 必填）
              "native"   → 项目内置工具，放在 tools/<id>/ 目录下（url 填相对路径如 "tools/foo/"）
              "planned"  → 计划中尚未实现，卡片置灰显示「敬请期待」
     url    external / native 必填；planned 留空
     note   选填，额外说明（暂未渲染，留作扩展）

   ── 把外部工具改成内置工具的步骤 ──
     1. 在 tools/ 目录下新建子目录 tools/<id>/
     2. 在里面放该工具的 index.html（及所需 js/css）
     3. 把本文件里对应条目的 type 改成 "native"，url 改成 "tools/<id>/"
   ========================================================================== */
(function () {
  "use strict";
  window.MUROJ_TOOLS = [
    {
      id: "MSpan",
      title: "网页转盘",
      desc: "AI写的，点开即用。",
      icon: "🧱",
      tags: ["小工具", "分享", "开发"],
      type: "external",
      url: "https://776f2403d0974518badce27d4e1d0ea0.sh4.agentos-app.net/"
    },
    {
      id: "MSpan",
      title: "工具娃！",
      desc: "包含了更多工具",
      icon: "🐸",
      tags: ["小工具", "分享", "开发"],
      type: "external",
      url: "https://toolwa.com/"
    },
    {
      id: "palace-panorama",
      title: "全景故宫",
      desc: "足不出户，在线游览故宫的宫殿与展览。",
      icon: "🏛️",
      tags: ["文化", "在线游览"],
      type: "external",
      url: "https://pano.dpm.org.cn/"
    },
    {
      id: "excalidraw",
      title: "Excalidraw",
      desc: "手绘风格的在线白板，画流程图、草图、思路图都很顺手。",
      icon: "✏️",
      tags: ["绘图", "白板"],
      type: "external",
      url: "https://excalidraw.com/"
    },
    {
      id: "photopea",
      title: "Photopea",
      desc: "浏览器里的 Photoshop，打开 PSD、修图、做图层，不用装软件。",
      icon: "🎨",
      tags: ["图片", "编辑"],
      type: "external",
      url: "https://www.photopea.com/"
    },
    {
      id: "squoosh",
      title: "Squoosh",
      desc: "Google 出品的图片压缩 / 格式转换工具，本地处理不上传。",
      icon: "🖼️",
      tags: ["图片", "压缩"],
      type: "external",
      url: "https://squoosh.app/"
    },
    {
      id: "carbon",
      title: "Carbon",
      desc: "把代码片段生成漂亮的分享图片，配色、字体、窗口样式都可调。",
      icon: "💻",
      tags: ["代码", "分享"],
      type: "external",
      url: "https://carbon.now.sh/"
    },
    {
      id: "regex101",
      title: "Regex 101",
      desc: "正则表达式调试器，实时匹配、解释每一段含义，救命级工具。",
      icon: "🔎",
      tags: ["开发", "正则"],
      type: "external",
      url: "https://regex101.com/"
    },
    {
      id: "cyberchef",
      title: "CyberChef",
      desc: "GCHQ 开发的编解码瑞士军刀，Base64、哈希、加密、格式互转一应俱全。",
      icon: "🧰",
      tags: ["开发", "编解码"],
      type: "external",
      url: "https://gchq.github.io/CyberChef/"
    },
    {
      id: "deepl",
      title: "DeepL",
      desc: "目前最自然的机器翻译，中英互译质量明显优于同类。",
      icon: "🌐",
      tags: ["翻译"],
      type: "external",
      url: "https://www.deepl.com/translator"
    },
    {
      id: "remove-bg",
      title: "remove.bg",
      desc: "一键抠图，自动识别前景主体并去掉背景，几秒出图。",
      icon: "✂️",
      tags: ["图片", "抠图"],
      type: "external",
      url: "https://www.remove.bg/"
    },
    {
      id: "tinypng",
      title: "TinyPNG",
      desc: "智能有损压缩 PNG/JPEG，体积大幅下降而画质几乎无感。",
      icon: "📦",
      tags: ["图片", "压缩"],
      type: "external",
      url: "https://tinypng.com/"
    },
    {
      id: "muroj-markdown",
      title: "Markdown 预览",
      desc: "（计划中）本地即时预览 Markdown，写文章时随手贴一段就能看效果。",
      icon: "📝",
      tags: ["开发", "计划中"],
      type: "planned"
    }
  ];
})();
