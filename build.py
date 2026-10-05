#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MurojBlog 构建脚本（零第三方依赖，只用 Python 标准库）

用法
----
    python build.py                  # 构建：Markdown → HTML，并刷新首页/归档/站点地图/订阅
    python build.py new "文章标题"    # 新建一篇文章的 Markdown 草稿
    python build.py list             # 列出所有文章
    python build.py url <网址>        # 一次性改好全站网址（推荐部署前先跑这条）

你只需要在 posts/ 目录里写 .md 文件，其余全部自动生成。
"""

from __future__ import annotations

import datetime as dt
import html
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"


def _force_utf8_console() -> None:
    """Windows 控制台默认是 GBK，中文日志会乱码；这里统一切成 UTF-8。"""
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass
    for stream in ("stdout", "stderr"):
        s = getattr(sys, stream, None)
        if hasattr(s, "reconfigure"):
            try:
                s.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_force_utf8_console()

# --------------------------------------------------------------------------
# 站点配置
# 部署前用这条命令一次改好网址：python build.py url https://你的用户名.github.io
# --------------------------------------------------------------------------
SITE = {
    "name": "MurojBlog",
    "tagline": "孟然君的个人博客",
    "description": "MurojBlog —— 孟然君的个人博客。写技术，也写想法和日常；内容用 Markdown 书写，站点托管在 GitHub Pages 上。",
    "author": "孟然君",
    "lang": "zh-CN",
    "url": "https://example.github.io",   # ←← 用 python build.py url <地址> 自动修改
    "latest": 3,                          # 首页「最新文章」显示几篇
}

# 阅读速度：中文每分钟多少字（改这两个数字即可调整「约 N 分钟读完」）
READ_CJK_PER_MIN = 300
READ_WORD_PER_MIN = 180

BUILD_START = "<!-- BUILD:{0}:START -->"
BUILD_END = "<!-- BUILD:{0}:END -->"

CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]")
CJK_PUNCT = "，。！？；：、）》」』】…—·"


# ==========================================================================
# 1. Markdown → HTML
# ==========================================================================

def _escape_keep_tags(text: str) -> str:
    """转义 & < >，但保留看起来像 HTML 标签的部分（让 <br> 之类的原生标签可用）。"""
    stash: list[str] = []

    def keep(m):
        stash.append(m.group(0))
        return "\x01%d\x01" % (len(stash) - 1)

    text = re.sub(r"</?[a-zA-Z][^>]*>", keep, text)
    text = html.escape(text, quote=False)
    for i, tag in enumerate(stash):
        text = text.replace("\x01%d\x01" % i, tag)
    return text


def _join_soft(lines: list[str]) -> str:
    """把折行的段落合并成一行。中英文之间才补空格，避免中文里被塞进多余空格。"""
    out = ""
    for ln in lines:
        if not out:
            out = ln
        elif CJK_RE.match(out[-1]) or CJK_RE.match(ln[0]) or ln[0] in CJK_PUNCT:
            out += ln
        else:
            out += " " + ln
    return out


def inline(text: str) -> str:
    """行内语法：`code`、**粗体**、*斜体*、~~删除线~~、[链接](url)、![图片](src)"""
    codes: list[str] = []

    def stash_code(m):
        codes.append(m.group(1))
        return "\x02%d\x02" % (len(codes) - 1)

    text = re.sub(r"`([^`]+)`", stash_code, text)
    text = _escape_keep_tags(text)

    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)

    def unstash(m):
        return "<code>" + html.escape(codes[int(m.group(1))], quote=False) + "</code>"

    return re.sub(r"\x02(\d+)\x02", unstash, text)


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    if not s or "-" not in s:
        return False
    return bool(re.match(r"^\|?[\s:|-]+\|[\s:|-]*$", s))


def _is_block_start(lines: list[str], i: int) -> bool:
    s = lines[i].strip()
    if not s:
        return True
    if re.match(r"^```", s):
        return True
    if re.match(r"^#{1,6}\s+", s):
        return True
    if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
        return True
    if s.startswith(">"):
        return True
    if re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
        return True
    if "|" in lines[i] and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
        return True
    return False


def _render_list(lines: list[str], i: int) -> tuple[str, int]:
    """渲染有序/无序列表，按缩进支持任意层级嵌套。"""
    first = lines[i]
    base_indent = len(first) - len(first.lstrip())
    items: list[tuple[int, bool, str]] = []

    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            break
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", raw)
        if not m:
            break
        indent = len(m.group(1))
        if indent < base_indent:
            break
        items.append((indent, m.group(2)[0].isdigit(), m.group(3).strip()))
        i += 1

    parts: list[str] = []
    # 每一层：[缩进, 标签, 是否有未闭合的 <li>, 该 <li> 内是否已有子列表]
    stack: list[list] = []

    def close_li(lvl: list, depth: int) -> None:
        """闭合某一层的 <li>：叶子节点直接接在文本后面，含子列表的另起一行。"""
        if not lvl[2]:
            return
        if lvl[3]:
            parts.append("%s</li>" % ("  " * depth))
        else:
            parts[-1] += "</li>"
        lvl[2] = lvl[3] = False

    for indent, ordered, text in items:
        tag = "ol" if ordered else "ul"

        while stack and indent < stack[-1][0]:
            lvl = stack.pop()
            close_li(lvl, len(stack))
            parts.append("%s</%s>" % ("  " * len(stack), lvl[1]))

        if not stack or indent > stack[-1][0]:
            if stack:
                stack[-1][3] = True          # 父级 <li> 内嵌入了子列表
            parts.append("%s<%s>" % ("  " * len(stack), tag))
            stack.append([indent, tag, False, False])
        else:
            close_li(stack[-1], len(stack))

        parts.append("%s<li>%s" % ("  " * len(stack), inline(text)))
        stack[-1][2] = True

    while stack:
        lvl = stack.pop()
        close_li(lvl, len(stack))
        parts.append("%s</%s>" % ("  " * len(stack), lvl[1]))

    return "\n".join(parts), i


def _heading_id(text: str) -> str:
    s = unicodedata.normalize("NFKC", text).strip().lower()
    s = re.sub(r"[\s]+", "-", s)
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def md_to_html(src: str, headings: list | None = None) -> str:
    """Markdown → HTML。传入 headings 列表时，会把 h2/h3 的锚点收进去（用于生成目录）。"""
    lines = src.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    used_ids: set[str] = set()

    while i < n:
        s = lines[i].strip()

        if not s:
            i += 1
            continue

        # ---- 围栏代码块 ----
        m = re.match(r"^```\s*([^\s`]*)\s*$", s)
        if m:
            lang = m.group(1)
            i += 1
            buf = []
            while i < n and not re.match(r"^```\s*$", lines[i].strip()):
                buf.append(lines[i])
                i += 1
            i += 1
            code = html.escape("\n".join(buf), quote=False)
            cls = ' class="language-%s"' % lang if lang else ""
            out.append(
                '<div class="code-block">\n'
                '  <button class="copy-btn">复制</button>\n'
                "<pre><code%s>%s</code></pre>\n"
                "</div>" % (cls, code)
            )
            continue

        # ---- 分隔线 ----
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            out.append("<hr>")
            i += 1
            continue

        # ---- 标题（# 与 ## 都输出 h2，### 输出 h3，以此类推）----
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if m:
            lvl = len(m.group(1))
            lvl = 2 if lvl <= 2 else lvl
            raw = m.group(2)
            plain = re.sub(r"[*`~\[\]]|\(([^)]*)\)", lambda mm: mm.group(1) or "", raw)
            attr = ""
            if headings is not None and lvl in (2, 3):
                hid = _heading_id(plain) or "section"
                base, k = hid, 2
                while hid in used_ids:
                    hid, k = "%s-%d" % (base, k), k + 1
                used_ids.add(hid)
                headings.append((lvl, hid, plain))
                attr = ' id="%s"' % hid
            out.append("<h%d%s>%s</h%d>" % (lvl, attr, inline(raw), lvl))
            i += 1
            continue

        # ---- 引用 ----
        if s.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]).strip())
                i += 1
            out.append("<blockquote>\n  <p>%s</p>\n</blockquote>" % inline(_join_soft(buf)))
            continue

        # ---- 列表 ----
        if re.match(r"^\s*([-*+]|\d+[.)])\s+", lines[i]):
            block, i = _render_list(lines, i)
            out.append(block)
            continue

        # ---- 表格 ----
        if "|" in lines[i] and i + 1 < n and _is_table_sep(lines[i + 1]):
            head = _split_row(lines[i])
            i += 2
            body = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                body.append(_split_row(lines[i]))
                i += 1
            t = ["<table>", "  <thead>", "    <tr>"]
            for c in head:
                t.append("      <th>%s</th>" % inline(c))
            t += ["    </tr>", "  </thead>", "  <tbody>"]
            for row in body:
                t.append("    <tr>")
                for c in row:
                    t.append("      <td>%s</td>" % inline(c))
                t.append("    </tr>")
            t += ["  </tbody>", "</table>"]
            out.append("\n".join(t))
            continue

        # ---- 段落 ----
        buf = []
        while i < n and lines[i].strip() and not _is_block_start(lines, i):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append("<p>%s</p>" % inline(_join_soft(buf)))
        else:                      # 保险：避免死循环
            out.append("<p>%s</p>" % inline(s))
            i += 1

    return "\n\n".join(out)


# ==========================================================================
# 2. Front matter + 文章读取
# ==========================================================================

def parse_front_matter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta: dict = {}
    for raw in m.group(1).split("\n"):
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        meta[key.strip().lower()] = val.strip()
    return meta, m.group(2)


def reading_minutes(body_md: str) -> int:
    """按正文字数估算阅读时长。想固定某个值，在 front matter 里写 minutes: 8。"""
    code_lines = sum(m.group(0).count("\n") for m in re.finditer(r"```.*?```", body_md, re.S))
    plain = re.sub(r"```.*?```", " ", body_md, flags=re.S)
    cjk = len(CJK_RE.findall(plain))
    words = len(re.findall(r"[A-Za-z0-9]+", plain))
    minutes = cjk / READ_CJK_PER_MIN + words / READ_WORD_PER_MIN + code_lines / 15.0
    return max(1, int(math.ceil(minutes)))


def word_count(body_md: str) -> int:
    plain = re.sub(r"```.*?```", " ", body_md, flags=re.S)
    plain = re.sub(r"[#>*`\[\]()!-]", "", plain)
    return len(CJK_RE.findall(plain)) + len(re.findall(r"[A-Za-z0-9]+", plain))


def slugify(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).strip().lower()
    name = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name)
    return re.sub(r"-{2,}", "-", name).strip("-") or "post"


def load_posts() -> list[dict]:
    posts = []
    for f in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        title = meta.get("title") or f.stem
        date = meta.get("date") or dt.date.fromtimestamp(f.stat().st_mtime).isoformat()
        tags = [t.strip() for t in re.split(r"[,，]", meta.get("tags", "")) if t.strip()]
        posts.append({
            "slug": meta.get("slug") or f.stem,
            "file": f,
            "title": title,
            "date": date,
            "sort": _parse_date(date),
            "tags": tags,
            "summary": meta.get("summary", ""),
            "ai": str(meta.get("ai", "true")).strip().lower() not in ("false", "no", "0", "否"),
            "minutes": int(meta["minutes"]) if meta.get("minutes", "").isdigit()
                       else reading_minutes(body),
            "words": word_count(body),
            "body_md": body,
        })
    # 首页置顶
    posts.sort(key=lambda p: (str(p.get("pin", "")), p["sort"]), reverse=True)
    posts.sort(key=lambda p: p["sort"], reverse=True)
    return posts


def _parse_date(s: str) -> dt.date:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return dt.date(1970, 1, 1)


# ==========================================================================
# 3. 页面片段
# ==========================================================================

LOGO_MARK = (
    '<span class="logo-mark" aria-hidden="true">'
    '<svg viewBox="0 0 32 32"><path d="M9 23.2V8.8L16 18.2L23 8.8V23.2" fill="none" '
    'stroke="currentColor" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/>'
    "</svg></span>"
)

AI_BADGE = (
    '<span class="ai-notice" title="本文内容由 AI 生成，仅供参考">\n'
    '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/>'
    '<path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z"/></svg>\n'
    "  <span>由AI生成</span>\n"
    "</span>"
)


def render_toc(headings: list) -> str:
    """由 h2/h3 生成文章目录。少于两个标题就不生成。"""
    if len(headings) < 2:
        return ""
    items = []
    for lvl, hid, text in headings:
        cls = ' class="toc-sub"' if lvl >= 3 else ""
        items.append('          <li%s><a href="#%s">%s</a></li>'
                     % (cls, hid, html.escape(text)))
    return (
        '<nav class="toc" aria-label="文章目录">\n'
        '        <div class="toc-head">\n'
        '          <span>目录</span>\n'
        '          <span class="toc-count">%d 节</span>\n'
        '        </div>\n'
        '        <ol class="toc-list">\n%s\n        </ol>\n'
        '      </nav>\n\n      ' % (len(headings), "\n".join(items))
    )


def head_block(title: str, description: str, prefix: str, url_path: str,
               og_type="website", og_title: str | None = None) -> str:
    full = SITE["url"].rstrip("/") + "/" + url_path.lstrip("/")
    desc = html.escape(description or SITE["description"], quote=True)
    ogt = html.escape(og_title or title, quote=True)
    return (
        '<meta charset="UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "  <title>%s</title>\n"
        '  <meta name="description" content="%s">\n'
        '  <link rel="canonical" href="%s">\n'
        '  <meta property="og:type" content="%s">\n'
        '  <meta property="og:site_name" content="%s">\n'
        '  <meta property="og:title" content="%s">\n'
        '  <meta property="og:description" content="%s">\n'
        '  <meta property="og:url" content="%s">\n'
        '  <meta property="og:image" content="%s/og-image.png">\n'
        '  <meta name="twitter:card" content="summary_large_image">\n'
        '  <link rel="stylesheet" href="%scss/style.css">\n'
        '  <link rel="icon" href="%sfavicon.svg" type="image/svg+xml">\n'
        '  <link rel="alternate icon" href="%sfavicon.ico" sizes="any">\n'
        '  <link rel="apple-touch-icon" href="%sapple-touch-icon.png">\n'
        '  <link rel="alternate" type="application/rss+xml" title="%s" href="%s/feed.xml">\n'
        '  <script>document.documentElement.className+=" js";'
        'try{var t=localStorage.getItem("blog-theme");'
        'if(!t&&window.matchMedia&&window.matchMedia("(prefers-color-scheme: dark)").matches)t="dark";'
        'if(t)document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>'
        % (
            html.escape(title), desc, full, og_type, SITE["name"],
            ogt, desc, full, SITE["url"].rstrip("/"),
            prefix, prefix, prefix, prefix, SITE["name"], SITE["url"].rstrip("/"),
        )
    )


def header_block(prefix: str, active: str) -> str:
    def cls(name):
        return ' class="active"' if name == active else ""

    return (
        '<div class="progress-bar"></div>\n'
        '  <header class="site-header">\n'
        '    <div class="header-inner">\n'
        '      <a class="logo" href="%sindex.html">%s%s</a>\n'
        '      <button class="menu-btn" aria-label="打开菜单" aria-expanded="false">\n'
        '        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/>'
        '<line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>\n'
        "      </button>\n"
        '      <nav class="main-nav">\n'
        '        <a href="%sindex.html"%s>首页</a>\n'
        '        <a href="%sarchive.html"%s>归档</a>\n'
        '        <a href="%sabout.html"%s>关于</a>\n'
        '        <button class="theme-toggle" data-action="toggle-theme" aria-label="切换深浅色主题" '
        'aria-pressed="false">\n'
        '          <svg class="moon-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>\n'
        '          <svg class="sun-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/>'
        '<line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>'
        '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>'
        '<line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>'
        '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>\n'
        "        </button>\n"
        "      </nav>\n"
        "    </div>\n"
        "  </header>"
        % (prefix, LOGO_MARK, SITE["name"],
           prefix, cls("home"), prefix, cls("archive"), prefix, cls("about"))
    )


def footer_block(prefix: str) -> str:
    return (
        '<footer class="site-footer">\n'
        '    <div class="footer-inner">\n'
        '      <span>© <span data-year>%d</span> %s · Powered by GitHub Pages</span>\n'
        '      <div class="footer-links">\n'
        '        <a href="%sarchive.html">归档</a>\n'
        '        <a href="%sabout.html">关于</a>\n'
        '        <a href="%sfeed.xml">RSS</a>\n'
        '        <a href="https://github.com" target="_blank" rel="noopener">GitHub</a>\n'
        "      </div>\n"
        "    </div>\n"
        "  </footer>"
        % (dt.date.today().year, SITE["name"], prefix, prefix, prefix)
    )


def render_card(p: dict, prefix: str = "") -> str:
    badge = ("\n            " + AI_BADGE.replace("\n", "\n            ")) if p["ai"] else ""
    return (
        '<article class="post-card reveal">\n'
        '            <div class="card-top"><span class="tag">%s</span><span>%s</span></div>\n'
        '            <h3><a href="%sposts/%s.html">%s</a></h3>%s\n'
        '            <p>%s</p>\n'
        '            <div class="card-foot"><span>约 %d 分钟读完</span>'
        '<a class="read-more" href="%sposts/%s.html">阅读全文 →</a></div>\n'
        "          </article>"
        % (
            html.escape(p["tags"][0] if p["tags"] else "随笔"),
            p["date"], prefix, p["slug"], html.escape(p["title"]), badge,
            html.escape(p["summary"]), p["minutes"], prefix, p["slug"],
        )
    )


def render_archive_item(p: dict) -> str:
    tags = "".join('<span class="tag">%s</span>' % html.escape(t) for t in p["tags"])
    badge = ("\n            " + AI_BADGE.replace("\n", "\n            ")) if p["ai"] else ""
    return (
        '<li data-tags="%s">\n'
        '          <span class="date">%s</span>\n'
        "          <div>\n"
        '            <h3><a href="posts/%s.html">%s</a></h3>%s\n'
        "            <p>%s</p>\n"
        '            <div class="meta-tags">%s</div>\n'
        "          </div>\n"
        "        </li>"
        % (html.escape(",".join(p["tags"])), p["date"], p["slug"],
           html.escape(p["title"]), badge, html.escape(p["summary"]), tags)
    )


def render_post(p: dict, newer: dict | None, older: dict | None) -> str:
    left = ('<a href="%s.html">← 上一篇：%s</a>' % (newer["slug"], html.escape(newer["title"]))
            if newer else '<a href="../archive.html">← 返回归档</a>')
    right = ('<a href="%s.html">下一篇：%s →</a>' % (older["slug"], html.escape(older["title"]))
             if older else '<a href="../archive.html">返回归档 →</a>')
    badge = ("\n        " + AI_BADGE.replace("\n", "\n        ")) if p["ai"] else ""
    meta = '          <span class="tag">%s</span>\n' % html.escape(p["tags"][0]) if p["tags"] else ""
    meta += "          <span>%s</span>\n" % p["date"]
    meta += '          <span>·</span>\n          <span>约 %d 分钟读完</span>' % p["minutes"]

    headings: list = []
    body_html = md_to_html(p["body_md"], headings)
    toc = render_toc(headings)

    return (
        "<!DOCTYPE html>\n"
        '<html lang="%s">\n'
        "<head>\n  %s\n</head>\n"
        "<body>\n"
        "  %s\n\n"
        "  <main>\n"
        '    <article class="article-wrap">\n'
        '      <header class="article-header">\n'
        '        <div class="meta">\n%s\n        </div>\n'
        "        <h1>%s</h1>%s\n"
        "      </header>\n\n"
        "      %s"
        '      <div class="article-body">\n%s\n      </div>\n\n'
        '      <nav class="article-nav">\n        %s\n        %s\n      </nav>\n'
        "    </article>\n"
        "  </main>\n\n"
        "  %s\n\n"
        '  <script src="../js/main.js"></script>\n'
        '  <script src="../js/enhance.js"></script>\n'
        "</body>\n"
        "</html>\n"
        % (
            SITE["lang"],
            head_block("%s — %s" % (p["title"], SITE["name"]), p["summary"],
                       "../", "posts/%s.html" % p["slug"], og_type="article",
                       og_title=p["title"]),
            header_block("../", ""),
            meta,
            html.escape(p["title"]),
            badge,
            toc,
            body_html,
            left, right,
            footer_block("../"),
        )
    )


# ==========================================================================
# 4. 注入静态页面的 BUILD 区块
# ==========================================================================

def inject(path: Path, name: str, content: str, indent: str = "          ") -> bool:
    text = path.read_text(encoding="utf-8")
    start, end = BUILD_START.format(name), BUILD_END.format(name)
    if start not in text or end not in text:
        print("  ! %s 缺少 %s 标记，已跳过" % (path.name, name))
        return False
    body = "\n".join(indent + ln if ln.strip() else "" for ln in content.split("\n"))
    new = re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        start + "\n" + body + "\n" + indent + end,
        text, flags=re.S,
    )
    path.write_text(new, encoding="utf-8", newline="\n")
    return True


def build_search_index(posts: list[dict]) -> None:
    """生成 js/search-index.js（用 JS 文件而不是 JSON，这样 file:// 直接打开也能搜索）。"""
    items = []
    for p in posts:
        plain = re.sub(r"```.*?```", " ", p["body_md"], flags=re.S)
        plain = re.sub(r"[#>*`\[\]()!|~-]", " ", plain)
        plain = re.sub(r"\s+", " ", plain).strip()[:1500]
        items.append({
            "t": p["title"],
            "u": "posts/%s.html" % p["slug"],
            "d": p["date"],
            "g": p["tags"],
            "s": p["summary"],
            "b": plain,
            "ai": p["ai"],
            "m": p["minutes"],
        })
    js = ("/* 由 build.py 自动生成，不要手改。用于站内搜索（Ctrl/Cmd + K）。 */\n"
          "window.__SEARCH_INDEX__ = "
          + json.dumps(items, ensure_ascii=False, separators=(",", ":"))
          + ";\n")
    (ROOT / "js" / "search-index.js").write_text(js, encoding="utf-8", newline="\n")


def build_sitemap(posts: list[dict]) -> None:
    base = SITE["url"].rstrip("/")
    urls = [("", "1.0"), ("archive.html", "0.6"), ("about.html", "0.5")]
    urls += [("posts/%s.html" % p["slug"], "0.8") for p in posts]
    items = []
    for path, pri in urls:
        loc = "%s/%s" % (base, path) if path else base + "/"
        lastmod = ""
        if path.startswith("posts/"):
            match = next((p for p in posts if "posts/%s.html" % p["slug"] == path), None)
            lastmod = "\n    <lastmod>%s</lastmod>" % match["date"] if match else ""
        items.append("  <url>\n    <loc>%s</loc>%s\n    <priority>%s</priority>\n  </url>"
                     % (loc, lastmod, pri))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(items) + "\n</urlset>\n")
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8", newline="\n")


def build_feed(posts: list[dict]) -> None:
    base = SITE["url"].rstrip("/")
    updated = max((p["sort"] for p in posts), default=dt.date.today())
    items = []
    for p in posts[:20]:
        link = "%s/posts/%s.html" % (base, p["slug"])
        items.append(
            "    <item>\n"
            "      <title>%s</title>\n"
            "      <link>%s</link>\n"
            '      <guid isPermaLink="true">%s</guid>\n'
            "      <pubDate>%s</pubDate>\n"
            "      <description>%s</description>\n"
            "    </item>"
            % (html.escape(p["title"]), link, link,
               p["sort"].strftime("%a, %d %b %Y 00:00:00 +0800"),
               html.escape(p["summary"]))
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
           "  <channel>\n"
           "    <title>%s</title>\n"
           "    <link>%s/</link>\n"
           "    <description>%s</description>\n"
           "    <language>%s</language>\n"
           '    <atom:link href="%s/feed.xml" rel="self" type="application/rss+xml"/>\n'
           "    <lastBuildDate>%s</lastBuildDate>\n"
           "%s\n"
           "  </channel>\n"
           "</rss>\n"
           % (html.escape(SITE["name"]), base, html.escape(SITE["description"]), SITE["lang"],
              base, updated.strftime("%a, %d %b %Y 00:00:00 +0800"), "\n".join(items)))
    (ROOT / "feed.xml").write_text(xml, encoding="utf-8", newline="\n")


# ==========================================================================
# 5. 命令
# ==========================================================================

def cmd_build() -> int:
    posts = load_posts()
    if not posts:
        print("posts/ 下没有 .md 文件。先运行：python build.py new \"我的第一篇文章\"")
        return 1

    print("读取到 %d 篇文章：" % len(posts))
    for p in posts:
        print("  · %s  %-34s %s" % (p["date"], p["title"], "AI" if p["ai"] else "  "))

    # 文章页
    for idx, p in enumerate(posts):
        newer = posts[idx - 1] if idx > 0 else None
        older = posts[idx + 1] if idx + 1 < len(posts) else None
        out = POSTS_DIR / ("%s.html" % p["slug"])
        out.write_text(render_post(p, newer, older), encoding="utf-8", newline="\n")
    print("生成 %d 个文章页" % len(posts))

    # 首页卡片
    latest = posts[: SITE["latest"]]
    inject(ROOT / "index.html", "POSTS",
           "\n\n".join(render_card(p) for p in latest), "          ")

    # 归档
    inject(ROOT / "archive.html", "ARCHIVE",
           "\n".join(render_archive_item(p) for p in posts), "        ")
    tags: list[str] = []
    for p in posts:
        for t in p["tags"]:
            if t not in tags:
                tags.append(t)
    filters = ['<button class="filter-btn active" data-tag="all" aria-pressed="true">全部</button>']
    filters += ['<button class="filter-btn" data-tag="%s" aria-pressed="false">%s</button>'
                % (html.escape(t), html.escape(t)) for t in tags]
    inject(ROOT / "archive.html", "FILTERS", "\n".join(filters), "        ")
    inject(ROOT / "archive.html", "COUNT",
           "<span>共 %d 篇 · 按时间倒序</span>" % len(posts), "          ")

    build_sitemap(posts)
    build_feed(posts)
    build_search_index(posts)
    print("生成 sitemap.xml、feed.xml、js/search-index.js")
    print("\n完成。本地预览：python -m http.server 8080")
    return 0


def cmd_new(title: str, slug_arg: str | None = None) -> int:
    today = dt.date.today().isoformat()
    slug = slugify(slug_arg or title)[:60]
    path = POSTS_DIR / ("%s.md" % slug)
    if path.exists():
        print("已存在：%s" % path)
        return 1
    path.write_text(
        "---\n"
        "title: %s\n"
        "date: %s\n"
        "tags: 随笔\n"
        "summary: 这里写一句话摘要，会显示在首页卡片和归档列表里。\n"
        "ai: true\n"
        "---\n\n"
        "在这里直接写正文，用 Markdown 语法：\n\n"
        "## 这是小节标题\n\n"
        "正文段落。**粗体**、*斜体*、`行内代码`、[链接](https://example.com)。\n\n"
        "- 列表项一\n"
        "- 列表项二\n\n"
        "> 引用文字。\n\n"
        "```bash\n"
        "echo \"代码块带一键复制按钮\"\n"
        "```\n\n"
        "### 更小的标题\n\n"
        "| 表头 A | 表头 B |\n"
        "| --- | --- |\n"
        "| 单元格 | 单元格 |\n"
        % (title, today),
        encoding="utf-8", newline="\n")
    print("已创建：%s" % path)
    if not re.search(r"[A-Za-z0-9]", slug):
        print("提示：文件名是中文，网址里会显示成编码后的形式。")
        print("      想要更简短的英文地址，可以这样重建：")
        print("      python build.py new \"%s\" my-post-name" % title)
    print("写完后运行：python build.py")
    return 0


def cmd_list() -> int:
    posts = load_posts()
    print("%-12s  %-38s %-16s %s" % ("日期", "标题", "标签", "AI"))
    for p in posts:
        print("%-12s  %-38s %-16s %s" % (p["date"], p["title"], ",".join(p["tags"]),
                                         "是" if p["ai"] else "否"))
    print("\n共 %d 篇" % len(posts))
    return 0


def cmd_url(new_url: str) -> int:
    """一条命令改好全站网址：改 build.py 自己的配置 + 替换静态页里写死的地址。"""
    new_url = new_url.strip().rstrip("/")
    if not re.match(r"^https?://", new_url):
        print("地址要以 http:// 或 https:// 开头，例如：")
        print("  python build.py url https://yourname.github.io")
        print("  python build.py url https://yourname.github.io/my-blog")
        return 1

    old_url = SITE["url"].rstrip("/")

    # 1) 改 build.py 自己的 SITE["url"]
    me = Path(__file__).resolve()
    src = me.read_text(encoding="utf-8")
    new_src, n_cfg = re.subn(
        r'("url"\s*:\s*)"[^"]*"',
        lambda m: m.group(1) + '"%s"' % new_url,
        src, count=1,
    )
    if n_cfg:
        me.write_text(new_src, encoding="utf-8", newline="\n")
        SITE["url"] = new_url          # 同步内存里的配置，否则下面的构建还用旧地址
        print("已更新 build.py 的 SITE[\"url\"] -> %s" % new_url)
    else:
        print("! 没能在 build.py 里找到 SITE[\"url\"]，请手动修改")
        SITE["url"] = new_url

    # 2) 替换静态页面里写死的 canonical / og:url / og:image / feed.xml 地址
    targets = ["index.html", "archive.html", "about.html", "404.html", "README.md"]
    changed = 0
    for name in targets:
        f = ROOT / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        if old_url and old_url in text:
            f.write_text(text.replace(old_url, new_url), encoding="utf-8", newline="\n")
            print("  已替换 %s" % name)
            changed += 1
    if not changed:
        print("  静态页面里没有找到旧地址 %s，无需替换" % old_url)

    # 3) 重新构建，让 sitemap.xml / feed.xml / 文章页一起更新
    print()
    return cmd_build()


def main() -> int:
    args = sys.argv[1:]
    if not args:
        return cmd_build()
    cmd = args[0].lower()
    if cmd == "new":
        if len(args) < 2:
            print('用法：python build.py new "文章标题" [英文文件名]')
            return 1
        return cmd_new(args[1], args[2] if len(args) > 2 else None)
    if cmd == "list":
        return cmd_list()
    if cmd == "url":
        if len(args) < 2:
            print("用法：python build.py url https://你的用户名.github.io")
            return 1
        return cmd_url(args[1])
    if cmd in ("build", "-h", "--help", "help"):
        print(__doc__)
        return 0
    print("未知命令：%s\n" % cmd)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
