#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MurojBlog 构建脚本（零第三方依赖，只用 Python 标准库）

用法
----
    python build.py                  # 构建：Markdown → HTML，并刷新首页/归档/站点地图/订阅
    python build.py check            # 只检查，不修改文件；发现错误时返回失败状态
    python build.py preview          # 构建到内存并打开本地预览，修改内容后自动刷新
    python build.py new "文章标题"    # 新建一篇文章的 Markdown 草稿
    python build.py list             # 列出所有文章
    python build.py url <网址>        # 一次性改好全站网址（推荐部署前先跑这条）

你只需要在 posts/ 目录里写 .md 文件，其余全部自动生成。
"""
# 26/11/12: GPT 6.1 Sol 更新

from __future__ import annotations

import datetime as dt
import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
import threading
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from collections import Counter
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"


class BuildError(ValueError):
    """可以直接告诉作者如何纠正的构建错误。"""


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
    "url": "https://mengranjun.github.io",   # ←← 用 python build.py url <地址> 自动修改
    "repo_url": "https://github.com/mengranjun/mengranjun.github.io",
    "latest": 3,                          # 首页「最新文章」显示几篇
}

# 阅读速度：中文每分钟多少字（改这两个数字即可调整「约 N 分钟读完」）
READ_CJK_PER_MIN = 300
READ_WORD_PER_MIN = 180

# 自动深浅色的「白天」时段（生成页 <head> 里的内联脚本由这两处生成）。
# 注意：index / archive / about / 404 四个静态页里手写着同一段脚本，
# 改这两个数字后要同步那几处（搜索 "h>=" 就能找到）。
THEME_DAY_START = 7
THEME_DAY_END = 19

THEME_SCRIPT = (
    '<script>document.documentElement.className+=" js";'
    'try{var t=localStorage.getItem("blog-theme");'
    'if(!t){var h=new Date().getHours();t=(h>=%d&&h<%d)?"light":"dark";}'
    'if(t)document.documentElement.setAttribute("data-theme",t);}catch(e){}</script>'
    % (THEME_DAY_START, THEME_DAY_END)
)

BUILD_START = "<!-- BUILD:{0}:START -->"
BUILD_END = "<!-- BUILD:{0}:END -->"

CJK_RE = re.compile(r"[\u2e80-\u9fff\uf900-\ufaff\uff00-\uffef\u3000-\u303f]")
CJK_PUNCT = "，。！？；：、）》」』】…—·"

# 单独成段的原生 HTML（放视频、iframe 之类）：整段原样输出，不套 <p>、不转义。
# 用法见 posts/video.md：一行 <video ...></video> 就是整篇文章。
RAW_HTML_RE = re.compile(
    r"^</?(?:video|audio|figure|figcaption|iframe|div|details|summary|section|picture|canvas|svg)\b",
    re.I,
)


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
        if not ln:
            continue
        if not out:
            out = ln
        elif CJK_RE.match(out[-1]) or CJK_RE.match(ln[0]) or ln[0] in CJK_PUNCT:
            out += ln
        else:
            out += " " + ln
    return out


def _replace_links(text: str, render) -> str:
    """识别链接目标里成对的括号，不把网址中的第一个右括号当成结尾。"""
    out, i = [], 0
    while i < len(text):
        start = i
        image = text.startswith("![", i)
        if (text[i] != "[" and not image) or (i and text[i - 1] == "\\"):
            out.append(text[i])
            i += 1
            continue
        label_start = i + (2 if image else 1)
        j, depth = label_start, 1
        while j < len(text) and depth:
            if text[j] == "\\" and j + 1 < len(text):
                j += 2
                continue
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
            if depth:
                j += 1
        if depth or text[j:j + 2] != "](":
            out.append(text[start])
            i += 1
            continue
        k, depth = j + 2, 1
        while k < len(text) and depth:
            if text[k] == "\\" and k + 1 < len(text):
                k += 2
                continue
            if text[k].isspace():
                break
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
            if depth:
                k += 1
        if depth:
            out.append(text[start])
            i += 1
            continue
        url = re.sub(r"\\([()\\])", r"\1", text[j + 2:k])
        out.append(render(image, text[label_start:j], url))
        i = k + 1
    return "".join(out)


def _emphasis(text: str) -> str:
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", text)
    return re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)


def inline(text: str) -> str:
    """行内语法：`code`、**粗体**、*斜体*、~~删除线~~、[链接](url)、![图片](src)"""
    codes: list[str] = []

    def stash_code(m):
        codes.append(m.group(2))
        return "\x02%d\x02" % (len(codes) - 1)

    text = re.sub(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", stash_code, text)
    text = _escape_keep_tags(text)

    # 注意：到这里正文已经过 html.escape(quote=False)，所以只需要处理 `"`，
    # 不能再整体 escape 一次（会把 &amp; 变成 &amp;amp;）。
    links: list[str] = []

    def keep_link(image: bool, label: str, url: str) -> str:
        url = url.replace('"', '%22')
        if image:
            label = re.sub(r"\x02(\d+)\x02", lambda m: html.escape(codes[int(m[1])]), label)
            rendered = '<img src="%s" alt="%s" loading="lazy">' % (url, label.replace('"', '&quot;'))
        else:
            rendered = '<a href="%s">%s</a>' % (url, _emphasis(label))
        links.append(rendered)
        return "\x03%d\x03" % (len(links) - 1)

    text = _emphasis(_replace_links(text, keep_link))
    text = re.sub(r"\x03(\d+)\x03", lambda m: links[int(m[1])], text)

    def unstash(m):
        return "<code>" + html.escape(codes[int(m.group(1))], quote=False) + "</code>"

    return re.sub(r"\x02(\d+)\x02", unstash, text)


def _split_row(line: str) -> list[str]:
    line = line.strip()
    cells, buf, ticks, i = [], [], 0, 0
    while i < len(line):
        if line[i:i + 2] == "\\|":
            buf.append("|")
            i += 2
            continue
        if line[i] == "`":
            end = i + 1
            while end < len(line) and line[end] == "`":
                end += 1
            run = end - i
            ticks = 0 if ticks == run else (run if not ticks else ticks)
            buf.append(line[i:end])
            i = end
            continue
        if line[i] == "|" and not ticks:
            cells.append("".join(buf).strip())
            buf = []
        else:
            buf.append(line[i])
        i += 1
    cells.append("".join(buf).strip())
    if line.startswith("|"):
        cells.pop(0)
    if len(cells) > 1 and not cells[-1] and line.endswith("|"):
        cells.pop()
    return cells


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
    if RAW_HTML_RE.match(s):
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
            nxt = i + 1
            while nxt < len(lines) and not lines[nxt].strip():
                nxt += 1
            if nxt < len(lines) and re.match(r"^(\s*)([-*+]|\d+[.)])\s+", lines[nxt]):
                if len(lines[nxt]) - len(lines[nxt].lstrip()) >= base_indent:
                    i = nxt
                    continue
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
        elif tag != stack[-1][1]:
            # 同一缩进层级从 ul 换成 ol（或反过来）：先闭合旧列表再开新列表，
            # 否则有序项会被塞进 <ul> 里
            lvl = stack.pop()
            close_li(lvl, len(stack))
            parts.append("%s</%s>" % ("  " * len(stack), lvl[1]))
            if stack:
                stack[-1][3] = True
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
            out.append(render_code_block("\n".join(buf), lang))
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
            # [文字](链接) 只留「文字」，URL 不能混进目录文字和锚点 id
            plain = re.sub(r"\([^)]*\)", "", raw)
            plain = re.sub(r"[*`~\[\]]", "", plain).strip()
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
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>\n%s\n</blockquote>" % md_to_html("\n".join(buf)))
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

        # ---- 原生 HTML 块（视频、iframe 之类）：整段照抄，不转义也不套 <p> ----
        if RAW_HTML_RE.match(s):
            buf = []
            while i < n and lines[i].strip():
                buf.append(lines[i].rstrip())
                i += 1
            out.append("\n".join(buf))
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
# 1b. 极简语法高亮（零依赖，逐行处理，够用就好）
# ==========================================================================

_HL_SHELL = ("if then else elif fi for while do done case esac in function return export source "
             "echo cd ls mkdir rm cp mv cat touch chmod sudo git npm pnpm python pip curl wget "
             "grep sed awk find set local")
_HL_JS = ("var let const function return if else for while do switch case break continue new this "
          "typeof instanceof in of class extends try catch finally throw async await yield delete "
          "void null undefined true false import export from default")
_HL_PY = ("def class return if elif else for while in not and or is None True False import from as "
          "with try except finally raise lambda yield global nonlocal pass break continue assert "
          "del async await")

HL_KEYWORDS = {
    "bash": _HL_SHELL, "sh": _HL_SHELL, "shell": _HL_SHELL, "zsh": _HL_SHELL,
    "js": _HL_JS, "javascript": _HL_JS, "json": "true false null",
    "python": _HL_PY, "py": _HL_PY,
    "css": "", "html": "", "xml": "", "yaml": "true false null", "yml": "true false null",
}

HL_COMMENT = {
    "python": r"#[^\n]*", "py": r"#[^\n]*",
    "bash": r"#[^\n]*", "sh": r"#[^\n]*", "shell": r"#[^\n]*", "zsh": r"#[^\n]*",
    "yaml": r"#[^\n]*", "yml": r"#[^\n]*",
    "js": r"//[^\n]*|/\*.*?\*/", "javascript": r"//[^\n]*|/\*.*?\*/",
    "css": r"/\*.*?\*/",
}


def _hl_line(line: str, lang: str) -> str:
    """把一行代码变成带高亮 span 的 HTML（入参是原始代码，内部负责转义）。"""
    # 注意：每个规则要用不同的组名，否则 re 会因为重名直接报错
    rules = []                                  # (组名, 样式名, 正则)
    cpat = HL_COMMENT.get(lang)
    if cpat:
        rules.append(("c", "c", cpat))
    if lang in ("html", "xml"):
        rules.append(("t", "t", r"</?[a-zA-Z][^>]*>"))
    rules.append(("s1", "s", r'"(?:\\.|[^"\\])*"'))
    rules.append(("s2", "s", r"'(?:\\.|[^'\\])*'"))
    rules.append(("s3", "s", r"`(?:\\.|[^`\\])*`"))
    kws = HL_KEYWORDS.get(lang, "")
    if kws:
        rules.append(("k", "k",
                      r"\b(?:%s)\b" % "|".join(sorted(kws.split(), key=len, reverse=True))))
    rules.append(("n", "n", r"\b\d+(?:\.\d+)?(?:px|em|rem|%|s|ms|dvh|vh|vw)?\b"))
    if lang == "css":
        rules.append(("p", "p", r"--?[a-zA-Z][\w-]*(?=\s*:)"))

    if not rules:
        return html.escape(line, quote=False)

    try:
        pat = re.compile("|".join("(?P<%s>%s)" % (g, p) for g, _, p in rules))
    except re.error:
        return html.escape(line, quote=False)

    cls_of = {g: c for g, c, _ in rules}
    out, pos = [], 0
    for m in pat.finditer(line):
        if m.start() > pos:
            out.append(html.escape(line[pos:m.start()], quote=False))
        out.append('<span class="tk tk-%s">%s</span>'
                   % (cls_of[m.lastgroup], html.escape(m.group(0), quote=False)))
        pos = m.end()
    if pos < len(line):
        out.append(html.escape(line[pos:], quote=False))
    return "".join(out)


def render_code_block(raw: str, lang: str) -> str:
    """代码块：语法高亮 + 行号 + 复制按钮。
    行号放在 .cl-n 里，复制时由 main.js 从克隆节点里剥掉，不会混进剪贴板。"""
    lang = (lang or "").lower()
    lines = raw.split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    body = "\n".join(
        '<span class="cl"><span class="cl-n" aria-hidden="true">%d</span>%s</span>'
        % (i + 1, _hl_line(ln, lang))
        for i, ln in enumerate(lines)
    )
    cls = ' class="language-%s"' % lang if lang else ""
    return ('<div class="code-block">\n'
            '  <button class="copy-btn" type="button">复制</button>\n'
            "<pre><code%s>%s</code></pre>\n"
            "</div>" % (cls, body))


# ==========================================================================
# 2. Front matter + 文章读取
# ==========================================================================

def parse_front_matter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not re.match(r"^---[ \t]*\n", text):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        raise BuildError("文章开头的元信息缺少结束分隔线 ---")
    meta: dict = {}
    for raw in m.group(1).split("\n"):
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip()
        if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
            val = val[1:-1]
        meta[key.strip().lower()] = val
    return meta, m.group(2)


def reading_minutes(body_md: str) -> int:
    """按正文字数估算阅读时长。想固定某个值，在 front matter 里写 minutes: 8。"""
    code_lines = sum(m.group(0).count("\n") for m in re.finditer(r"```.*?```", body_md, re.S))
    plain = re.sub(r"```.*?```", " ", body_md, flags=re.S)
    plain = re.sub(r"<[^>]*>", " ", plain)          # 原生 HTML 标签本身不算正文
    cjk = len(CJK_RE.findall(plain))
    words = len(re.findall(r"[A-Za-z0-9]+", plain))
    minutes = cjk / READ_CJK_PER_MIN + words / READ_WORD_PER_MIN + code_lines / 15.0
    return max(1, int(math.ceil(minutes)))


def word_count(body_md: str) -> int:
    plain = re.sub(r"```.*?```", " ", body_md, flags=re.S)
    plain = re.sub(r"<[^>]*>", " ", plain)          # 同上：视频/iframe 的标签不算字
    plain = re.sub(r"[#>*`\[\]()!-]", "", plain)
    return len(CJK_RE.findall(plain)) + len(re.findall(r"[A-Za-z0-9]+", plain))


def slugify(name: str) -> str:
    name = unicodedata.normalize("NFKC", name).strip().lower()
    name = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name)
    return re.sub(r"-{2,}", "-", name).strip("-") or "post"


def validate_slug(slug: str) -> None:
    """同时符合站内 URL 和 Windows 文件名规则，不允许跳出 posts/。"""
    reserved = {"con", "prn", "aux", "nul"} | {"%s%d" % (p, n) for p in ("com", "lpt") for n in range(1, 10)}
    if (not re.fullmatch(r"[\w-]+(?:\.[\w-]+)*", slug)
            or slug.split(".")[0].casefold() in reserved or len(slug) > 120):
        raise BuildError("slug %r 不适合作为文件名；请使用中文、字母、数字、连字符或下划线，不能包含路径" % slug)


def load_posts() -> list[dict]:
    posts = []
    seen_slugs: dict[str, str] = {}
    for f in sorted(POSTS_DIR.glob("*.md")):
        # utf-8-sig：Windows 编辑器常给文件加 BOM，不去掉的话 front matter 会整段失效
        try:
            meta, body = parse_front_matter(f.read_text(encoding="utf-8-sig"))
        except BuildError as exc:
            raise BuildError("%s：%s" % (f.name, exc)) from exc
        title = meta.get("title") or f.stem
        date = meta.get("date") or dt.date.fromtimestamp(f.stat().st_mtime).isoformat()
        try:
            sort_date = _parse_date(date)
            slug = meta.get("slug") or f.stem
            validate_slug(slug)
            minutes = meta.get("minutes", "")
            if minutes and (not re.fullmatch(r"[0-9]+", minutes) or int(minutes) < 1):
                raise BuildError("minutes 必须是大于 0 的整数")
        except ValueError as exc:
            raise BuildError("%s：%s" % (f.name, exc)) from exc
        key = unicodedata.normalize("NFKC", slug).casefold()
        if key in seen_slugs:
            raise BuildError("%s 与 %s 使用了相同的文章网址 %r（不区分大小写）" % (f.name, seen_slugs[key], slug))
        seen_slugs[key] = f.name
        tags = [t.strip() for t in re.split(r"[,，]", meta.get("tags", "")) if t.strip()]
        posts.append({
            "slug": slug,
            "file": f,
            "title": title,
            "date": sort_date.isoformat(),
            "sort": sort_date,
            "tags": tags,
            "pin": str(meta.get("pin", "")).strip().lower() in ("true", "yes", "1", "on", "是"),
            "summary": meta.get("summary", ""),
            # type: video 的文章正文只有一段视频，卡片上就不显示「约 N 分钟读完」
            "kind": (meta.get("type") or "post").strip().lower(),
            "ai": str(meta.get("ai", "true")).strip().lower() not in ("false", "no", "0", "否"),
            "minutes": int(minutes) if minutes else reading_minutes(body),
            "words": word_count(body),
            "body_md": body,
        })

    # 只归并大小写不同的同名标签，C++ / C# 等有实际区别的标签必须保留。
    canon: dict[str, str] = {}
    for p in posts:
        merged = []
        for t in p["tags"]:
            s = unicodedata.normalize("NFKC", t).casefold()
            if s in canon:
                t = canon[s]
            else:
                canon[s] = t
            if t not in merged:
                merged.append(t)
        p["tags"] = merged

    # 置顶优先，其次按日期倒序（一次排序搞定）
    posts.sort(key=lambda p: (p["pin"], p["sort"]), reverse=True)
    return posts


def _parse_date(s: str) -> dt.date:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise BuildError("日期 %r 无法识别；请使用 YYYY-MM-DD，例如 2026-11-12" % s)


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
        '  %s'
        % (
            html.escape(title), desc, full, og_type, SITE["name"],
            ogt, desc, full, SITE["url"].rstrip("/"),
            prefix, prefix, prefix, prefix, SITE["name"], SITE["url"].rstrip("/"),
            THEME_SCRIPT,
        )
    )


def header_block(prefix: str, active: str, include_progress: bool = True) -> str:
    def cls(name):
        return ' class="active"' if name == active else ""

    return (
        ('<div class="progress-bar"></div>\n' if include_progress else "") +
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
        '        <a href="%sabout.html"%s>关于</a>\n'
        '        <a href="%sarchive.html"%s>归档</a>\n'
        '        <a href="%stools.html"%s>小工具</a>\n'
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
           prefix, cls("home"), prefix, cls("about"), prefix, cls("archive"),
           prefix, cls("tools"))
    )


def footer_block(prefix: str, note: str = "") -> str:
    return (
        '<footer class="site-footer">\n'
        '    <div class="footer-inner">\n'
        '      <span>© <span data-year>%d</span> %s · Powered by GitHub Pages%s</span>\n'
        '      <div class="footer-links">\n'
        '        <a href="%sarchive.html">归档</a>\n'
        '        <a href="%sabout.html">关于</a>\n'
        '        <a href="%stools.html">小工具</a>\n'
        '        <a href="%sfeed.xml">RSS</a>\n'
        '        <a href="%s" target="_blank" rel="noopener noreferrer">GitHub</a>\n'
        "      </div>\n"
        "    </div>\n"
        "  </footer>"
        % (dt.date.today().year, SITE["name"], html.escape(note),
           prefix, prefix, prefix, prefix, html.escape(SITE["repo_url"], quote=True))
    )


def vt_name(slug: str) -> str:
    """给卡片和文章标题取一个配对用的 view-transition-name（纯 ASCII，稳定）。"""
    return "post-" + hashlib.md5(slug.encode("utf-8")).hexdigest()[:10]


def render_card(p: dict, prefix: str = "") -> str:
    badge = ("\n            " + AI_BADGE.replace("\n", "\n            ")) if p["ai"] else ""
    pin = '<span class="tag">置顶</span>' if p.get("pin") else ""
    video = p.get("kind") == "video"
    foot = "视频" if video else "约 %d 分钟读完" % p["minutes"]
    more = "观看 →" if video else "阅读全文 →"
    # 没有摘要就不输出空段落，免得卡片上多一块空白
    desc = ('            <p>%s</p>\n' % html.escape(p["summary"])) if p["summary"] else ""
    return (
        '<article class="post-card reveal" style="view-transition-name:%s">\n'
        '            <div class="card-top">%s<span class="tag">%s</span><span>%s</span></div>\n'
        '            <h3><a href="%sposts/%s.html">%s</a></h3>%s\n'
        "%s"
        '            <div class="card-foot"><span>%s</span>'
        '<a class="read-more" href="%sposts/%s.html">%s</a></div>\n'
        "          </article>"
        % (
            vt_name(p["slug"]), pin,
            html.escape(p["tags"][0] if p["tags"] else "随笔"),
            p["date"], prefix, p["slug"], html.escape(p["title"]), badge,
            desc, foot, prefix, p["slug"], more,
        )
    )


def render_archive_item(p: dict, prefix: str = "") -> str:
    tags = '<span class="tag">置顶</span>' if p.get("pin") else ""
    tags += "".join(
        '<a class="tag" href="%stags/%s.html">%s</a>'
        % (prefix, tag_slug(t), html.escape(t)) for t in p["tags"]
    )
    badge = ("\n            " + AI_BADGE.replace("\n", "\n            ")) if p["ai"] else ""
    desc = ('            <p>%s</p>\n' % html.escape(p["summary"])) if p["summary"] else ""
    return (
        '<li data-tags="%s">\n'
        '          <span class="date">%s</span>\n'
        "          <div>\n"
        '            <h3><a href="%sposts/%s.html">%s</a></h3>%s\n'
        "%s"
        '            <div class="meta-tags">%s</div>\n'
        "          </div>\n"
        "        </li>"
        % (html.escape(",".join(p["tags"])), p["date"], prefix, p["slug"],
           html.escape(p["title"]), badge, desc, tags)
    )


def render_post(p: dict, newer: dict | None, older: dict | None) -> str:
    left = ('<a href="%s.html">← 上一篇：%s</a>' % (newer["slug"], html.escape(newer["title"]))
            if newer else '<a href="../archive.html">← 返回归档</a>')
    right = ('<a href="%s.html">下一篇：%s →</a>' % (older["slug"], html.escape(older["title"]))
             if older else '<a href="../archive.html">返回归档 →</a>')
    badge = ("\n        " + AI_BADGE.replace("\n", "\n        ")) if p["ai"] else ""
    meta = '          <span class="tag">%s</span>\n' % html.escape(p["tags"][0]) if p["tags"] else ""
    meta += "          <span>%s</span>\n" % p["date"]
    if p.get("kind") == "video":
        meta += '          <span>·</span>\n          <span>视频</span>'
    else:
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
        '        <h1 style="view-transition-name:%s">%s</h1>%s\n'
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
            vt_name(p["slug"]),
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

@dataclass
class BuildPlan:
    """先完整生成到内存；所有转换成功后，才替换正式文件。"""
    files: dict[Path, str] = field(default_factory=dict)
    deletes: set[Path] = field(default_factory=set)

    def read(self, path: Path) -> str:
        return self.files[path] if path in self.files else path.read_text(encoding="utf-8")

    def write(self, path: Path, text: str) -> None:
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise BuildError("输出位置超出项目目录：%s" % path)
        self.files[path] = text

    def changes(self) -> list[Path]:
        return [p for p, text in self.files.items()
                if not p.exists() or p.read_bytes() != text.encode("utf-8")]

    def commit(self) -> tuple[int, int]:
        changed = self.changes()
        deleted = sorted(p for p in self.deletes if p.exists())
        if not changed and not deleted:
            return 0, 0
        stage = Path(tempfile.mkdtemp(prefix=".muroj-build-", dir=ROOT))
        backups: dict[Path, Path] = {}
        staged: dict[Path, Path] = {}
        applied: list[Path] = []
        created_dirs: list[Path] = []
        cleanup = True
        try:
            # 准备全部新文件与原件备份；此阶段不修改正式页面。
            for i, path in enumerate(changed + deleted):
                if not path.resolve().is_relative_to(ROOT.resolve()):
                    raise BuildError("拒绝修改项目外的文件：%s" % path)
                if path.exists():
                    backup = stage / ("old-%d" % i)
                    shutil.copy2(path, backup)
                    backups[path] = backup
                if path in self.files:
                    new = stage / ("new-%d" % i)
                    new.write_text(self.files[path], encoding="utf-8", newline="\n")
                    staged[path] = new
            for path in changed:
                if not path.parent.exists():
                    path.parent.mkdir(parents=True)
                    created_dirs.append(path.parent)
                os.replace(staged[path], path)
                applied.append(path)
            for path in deleted:
                path.unlink()
                applied.append(path)
        except BaseException as exc:
            failures = []
            for path in reversed(applied):
                try:
                    if path in backups:
                        os.replace(backups[path], path)
                    else:
                        path.unlink(missing_ok=True)
                except OSError as restore_error:
                    failures.append(str(restore_error))
            for directory in reversed(created_dirs):
                try:
                    directory.rmdir()
                except OSError:
                    pass
            if failures:
                cleanup = False
                raise BuildError("写入失败且未能完整恢复；原件备份保存在 %s：%s" % (stage, "; ".join(failures))) from exc
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            raise BuildError("写入失败，已恢复原文件：%s" % exc) from exc
        finally:
            if cleanup:
                shutil.rmtree(stage)
        return len(changed), len(deleted)


def version_local_assets(page: Path, text: str, plan: BuildPlan | None = None) -> str:
    """内容变化时更新 CSS / JS 的版本，避免手机拿新 HTML 配旧缓存资源。"""
    def replace(match):
        raw = html.unescape(match["url"])
        try:
            url = urlsplit(raw)
        except ValueError:
            return match[0]
        if url.scheme or url.netloc or Path(url.path).suffix.lower() not in (".css", ".js"):
            return match[0]
        path = ((ROOT / unquote(url.path).lstrip("/")) if url.path.startswith("/")
                else page.parent / unquote(url.path)).resolve()
        if not path.is_relative_to(ROOT.resolve()):
            return match[0]
        if plan is not None and path in plan.files:
            content = plan.files[path].encode("utf-8")
        elif path.is_file():
            content = path.read_bytes()
        else:
            return match[0]
        version = hashlib.sha256(content).hexdigest()[:12]
        query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True) if k != "v"]
        query.append(("v", version))
        value = urlunsplit(("", "", url.path, urlencode(query), url.fragment))
        return match["prefix"] + match["quote"] + html.escape(value, quote=True) + match["quote"]

    return re.sub(r'''(?P<prefix>\b(?:src|href)\s*=\s*)(?P<quote>["'])(?P<url>[^"']+)(?P=quote)''', replace, text)


def inject(path: Path, name: str, content: str, indent: str = "          ",
           plan: BuildPlan | None = None) -> bool:
    text = plan.read(path) if plan else path.read_text(encoding="utf-8")
    start, end = BUILD_START.format(name), BUILD_END.format(name)
    if text.count(start) != 1 or text.count(end) != 1 or text.index(start) >= text.index(end):
        raise BuildError("%s 的 BUILD:%s 标记缺失、重复或顺序错误；请保留一对 START / END 标记" % (path.name, name))
    body = "\n".join(indent + ln if ln.strip() else "" for ln in content.split("\n"))
    # 文本直接拼接，反斜杠等文章内容不会被当成正则替换指令。
    new = (text[:text.index(start)] + start + "\n" + body + "\n" + indent + end
           + text[text.index(end) + len(end):])
    if plan:
        plan.write(path, new)
    else:
        path.write_text(new, encoding="utf-8", newline="\n")
    return True


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip: list[str] = []

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "").split()
        if self.skip or tag in ("script", "style") or "cl-n" in classes or "copy-btn" in classes:
            if tag not in ("img", "br", "hr", "input", "source", "wbr"):
                self.skip.append(tag)
        elif tag in ("p", "div", "li", "pre", "br", "tr", "td", "th", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")
        elif tag == "img":
            self.parts.append(dict(attrs).get("alt", ""))

    def handle_endtag(self, tag):
        if self.skip:
            if tag == self.skip[-1]:
                self.skip.pop()
        elif tag in ("p", "div", "li", "pre", "tr", "td", "th", "h2", "h3", "h4", "h5", "h6"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def build_search_index(posts: list[dict], plan: BuildPlan | None = None) -> None:
    """生成 js/search-index.js（用 JS 文件而不是 JSON，这样 file:// 直接打开也能搜索）。"""
    items = []
    for p in posts:
        extractor = _VisibleText()
        extractor.feed(md_to_html(p["body_md"]))
        plain = re.sub(r"\s+", " ", "".join(extractor.parts)).strip()
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
    path = ROOT / "js" / "search-index.js"
    if plan:
        plan.write(path, js)
    else:
        path.write_text(js, encoding="utf-8", newline="\n")


def tag_slug(tag: str) -> str:
    normal = unicodedata.normalize("NFKC", tag).strip().casefold()
    base = _heading_id(normal) or "tag"
    if normal != base or base == "index" or len(base) > 80:
        return base[:80] + "--" + hashlib.sha256(normal.encode("utf-8")).hexdigest()[:12]
    return base


def collect_tags(posts: list[dict]) -> list[str]:
    tags: list[str] = []
    for p in posts:
        for t in p["tags"]:
            if t not in tags:
                tags.append(t)
    return tags


def render_tag_page(tag: str, tagged: list, all_tags: list) -> str:
    items = "\n".join(render_archive_item(p, "../") for p in tagged)
    chips = "".join(
        '<a class="chip%s" href="%s.html">%s</a>'
        % (" is-current" if t == tag else "", tag_slug(t), html.escape(t))
        for t in all_tags
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="%s">\n'
        "<head>\n  %s\n</head>\n"
        "<body>\n"
        "  %s\n\n"
        "  <main>\n"
        '    <div class="article-wrap" style="max-width: 820px;">\n'
        '      <div class="article-header">\n'
        "        <h1>标签：%s</h1>\n"
        '        <div class="meta"><span>共 %d 篇 · 按时间倒序</span></div>\n'
        "      </div>\n\n"
        '      <div class="skill-chips">%s</div>\n\n'
        '      <ul class="post-list">\n%s\n      </ul>\n\n'
        '      <nav class="article-nav">\n'
        '        <a href="index.html">← 全部标签</a>\n'
        '        <a href="../archive.html">返回归档 →</a>\n'
        "      </nav>\n"
        "    </div>\n"
        "  </main>\n\n"
        "  %s\n\n"
        '  <script src="../js/main.js"></script>\n'
        '  <script src="../js/enhance.js"></script>\n'
        "</body>\n"
        "</html>\n"
        % (SITE["lang"],
           head_block("标签：%s — %s" % (tag, SITE["name"]),
                      "标签「%s」下的全部文章。" % tag,
                      "../", "tags/%s.html" % tag_slug(tag)),
           header_block("../", "archive"),
           html.escape(tag), len(tagged), chips, items,
           footer_block("../"))
    )


def render_tags_index(tags: list, posts: list) -> str:
    counts = {}
    for p in posts:
        for t in p["tags"]:
            counts[t] = counts.get(t, 0) + 1
    cards = "\n".join(
        '        <a class="tag-card" href="%s.html">'
        '<span class="tag-card-name">%s</span>'
        '<span class="tag-card-count">%d 篇</span></a>'
        % (tag_slug(t), html.escape(t), counts.get(t, 0))
        for t in tags
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="%s">\n'
        "<head>\n  %s\n</head>\n"
        "<body>\n"
        "  %s\n\n"
        "  <main>\n"
        '    <div class="article-wrap" style="max-width: 820px;">\n'
        '      <div class="article-header">\n'
        "        <h1>全部标签</h1>\n"
        '        <div class="meta"><span>%d 个标签 · %d 篇文章</span></div>\n'
        "      </div>\n\n"
        '      <div class="tag-cards">\n%s\n      </div>\n\n'
        '      <nav class="article-nav">\n'
        '        <a href="../index.html">← 回到首页</a>\n'
        '        <a href="../archive.html">文章归档 →</a>\n'
        "      </nav>\n"
        "    </div>\n"
        "  </main>\n\n"
        "  %s\n\n"
        '  <script src="../js/main.js"></script>\n'
        '  <script src="../js/enhance.js"></script>\n'
        "</body>\n"
        "</html>\n"
        % (SITE["lang"],
           head_block("全部标签 — %s" % SITE["name"], "按标签浏览 MurojBlog 的全部文章。",
                      "../", "tags/index.html"),
           header_block("../", "archive"),
           len(tags), len(posts), cards, footer_block("../"))
    )


def build_tag_pages(posts: list[dict], plan: BuildPlan | None = None) -> list[str]:
    tags = collect_tags(posts)
    own_plan = plan is None
    plan = plan if plan is not None else BuildPlan()
    out_dir = ROOT / "tags"
    for t in tags:
        tagged = [p for p in posts if t in p["tags"]]
        plan.write(out_dir / ("%s.html" % tag_slug(t)), render_tag_page(t, tagged, tags))
    plan.write(out_dir / "index.html", render_tags_index(tags, posts))
    # 标签改名/删除后，旧标签页同样要清掉
    keep = {"%s.html" % tag_slug(t) for t in tags} | {"index.html"}
    for old in out_dir.glob("*.html"):
        if old.name not in keep:
            plan.deletes.add(old)
    if own_plan:
        plan.commit()
    return tags


def build_heatmap(posts: list[dict]) -> str:
    """按「年 × 月」统计发文量，做成一张热力图，注入归档页。"""
    if not posts:
        return ""
    counts: dict = {}
    for p in posts:
        d = p["sort"]
        counts[(d.year, d.month)] = counts.get((d.year, d.month), 0) + 1
    years = sorted({y for y, _ in counts}, reverse=True)
    top = max(counts.values())

    def level(n: int) -> int:
        if n <= 0:
            return 0
        if top <= 1:
            return 3
        return min(4, 1 + int((n - 1) / max(1, top - 1) * 3 + 0.5))

    rows = []
    for y in years:
        cells = []
        for m in range(1, 13):
            n = counts.get((y, m), 0)
            cells.append(
                '<span class="hm-cell" data-lv="%d" title="%d 年 %d 月 · %d 篇"></span>'
                % (level(n), y, m, n))
        total = sum(counts.get((y, m), 0) for m in range(1, 13))
        rows.append('        <span class="hm-year">%d</span>\n        %s\n'
                    '        <span class="hm-total">%d</span>'
                    % (y, "\n        ".join(cells), total))

    months = "".join('<span class="hm-m">%d</span>' % m for m in range(1, 13))
    return (
        '<div class="heatmap">\n'
        '          <div class="heatmap-head">\n'
        "            <span>写作热力图</span>\n"
        '            <span class="heatmap-sum">%d 篇 · %d 个月有更新</span>\n'
        "          </div>\n"
        '          <div class="heatmap-grid">\n'
        '            <span class="hm-year"></span>\n'
        "            %s\n"
        '            <span class="hm-total"></span>\n'
        "%s\n"
        "          </div>\n"
        "        </div>"
        % (len(posts), len(counts), months, "\n".join(rows))
    )


def build_sitemap(posts: list[dict], plan: BuildPlan | None = None) -> None:
    base = SITE["url"].rstrip("/")
    urls = [("", "1.0"), ("archive.html", "0.6"), ("about.html", "0.5"), ("tools.html", "0.5")]
    urls += [("posts/%s.html" % p["slug"], "0.8") for p in posts]
    urls += [("tags/index.html", "0.5")]
    urls += [("tags/%s.html" % tag_slug(t), "0.4") for t in collect_tags(posts)]
    items = []
    for path, pri in urls:
        loc = "%s/%s" % (base, path) if path else base + "/"
        lastmod = ""
        if path.startswith("posts/"):
            match = next((p for p in posts if "posts/%s.html" % p["slug"] == path), None)
            # 用解析后的日期而不是 front matter 原文，保证输出一定是 YYYY-MM-DD
            lastmod = "\n    <lastmod>%s</lastmod>" % match["sort"].isoformat() if match else ""
        items.append("  <url>\n    <loc>%s</loc>%s\n    <priority>%s</priority>\n  </url>"
                     % (html.escape(loc, quote=False), lastmod, pri))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(items) + "\n</urlset>\n")
    path = ROOT / "sitemap.xml"
    if plan:
        plan.write(path, xml)
    else:
        path.write_text(xml, encoding="utf-8", newline="\n")


def build_feed(posts: list[dict], plan: BuildPlan | None = None) -> None:
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
            % (html.escape(p["title"]), html.escape(link, quote=False), html.escape(link, quote=False),
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
           % (html.escape(SITE["name"]), html.escape(base, quote=False), html.escape(SITE["description"]), SITE["lang"],
               html.escape(base, quote=True), updated.strftime("%a, %d %b %Y 00:00:00 +0800"), "\n".join(items)))
    path = ROOT / "feed.xml"
    if plan:
        plan.write(path, xml)
    else:
        path.write_text(xml, encoding="utf-8", newline="\n")


# ==========================================================================
# 5. 命令
# ==========================================================================

def make_build_plan(plan: BuildPlan | None = None) -> tuple[BuildPlan, list[dict]]:
    plan = plan if plan is not None else BuildPlan()
    posts = load_posts()
    if not posts:
        raise BuildError("posts/ 下没有 .md 文件。先运行：python build.py new \"我的第一篇文章\"")

    # 常规页面的共享页头 / 页脚集中维护在 header_block / footer_block。
    # 404 页使用独立布局，不参与这组模板。
    for page, active in (("index.html", "home"), ("about.html", "about"),
                         ("archive.html", "archive"), ("tools.html", "tools")):
        path = ROOT / page
        inject(path, "HEADER", header_block("", active, include_progress=False), "", plan)
        note = " · 26.10.07.19.50--4+1+7" if page == "index.html" else ""
        inject(path, "FOOTER", footer_block("", note=note), "", plan)

    # 文章页
    for idx, p in enumerate(posts):
        newer = posts[idx - 1] if idx > 0 else None
        older = posts[idx + 1] if idx + 1 < len(posts) else None
        out = POSTS_DIR / ("%s.html" % p["slug"])
        try:
            plan.write(out, render_post(p, newer, older))
        except (ValueError, IndexError, re.error) as exc:
            raise BuildError("%s 渲染失败：%s" % (p["file"].name, exc)) from exc

    # 清理「幽灵页面」：.md 删除/改名后，旧 HTML 不能留在站里继续被发布
    live = {"%s.html" % p["slug"] for p in posts}
    for old in POSTS_DIR.glob("*.html"):
        if old.name not in live:
            plan.deletes.add(old)

    # 首页卡片
    latest = posts[: SITE["latest"]]
    inject(ROOT / "index.html", "POSTS",
           "\n\n".join(render_card(p) for p in latest), "          ", plan)

    # 归档
    inject(ROOT / "archive.html", "ARCHIVE",
           "\n".join(render_archive_item(p) for p in posts), "        ", plan)
    tags = collect_tags(posts)
    filters = ['<button class="filter-btn active" data-tag="all" aria-pressed="true">全部</button>']
    filters += ['<button class="filter-btn" data-tag="%s" aria-pressed="false">%s</button>'
                % (html.escape(t), html.escape(t)) for t in tags]
    inject(ROOT / "archive.html", "FILTERS", "\n".join(filters), "        ", plan)
    inject(ROOT / "archive.html", "COUNT",
           "<span>共 %d 篇 · 按时间倒序</span>" % len(posts), "          ", plan)
    inject(ROOT / "archive.html", "HEATMAP", build_heatmap(posts), "        ", plan)

    build_tag_pages(posts, plan)
    build_sitemap(posts, plan)
    build_feed(posts, plan)
    build_search_index(posts, plan)
    for path, text in list(plan.files.items()):
        if path.suffix == ".html":
            plan.write(path, version_local_assets(path, text, plan))
    return plan, posts


def cmd_build() -> int:
    plan, posts = make_build_plan()
    written, removed = plan.commit()
    print("完成：%d 篇文章、%d 个标签；更新 %d 个文件，清理 %d 个旧页面。" %
          (len(posts), len(collect_tags(posts)), written, removed))
    for path in sorted(plan.deletes):
        print("  清理过期页面：%s" % path.relative_to(ROOT).as_posix())
    print("检查：python build.py check\n本地预览：python build.py preview")
    return 0


class _PageReferences(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.refs: list[str] = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        elif tag == "a" and values.get("name"):
            self.ids.append(values["name"])
        for key in ("href", "src", "poster"):
            if values.get(key):
                self.refs.append(values[key])


def check_site(plan: BuildPlan, include_stale: bool = True) -> list[str]:
    """检查即将生成的站点，连同磁盘上的资源；不访问外部网站、不写文件。"""
    errors: list[str] = []
    for name in ("feed.xml", "sitemap.xml"):
        try:
            ET.fromstring(plan.read(ROOT / name))
        except (ET.ParseError, OSError) as exc:
            errors.append("%s 格式不正确或无法读取：%s" % (name, exc))
    if include_stale:
        changed = plan.changes()
        if changed or plan.deletes:
            errors.append("生成结果尚未同步，请运行 python build.py：%s" % ", ".join(
                p.relative_to(ROOT).as_posix() for p in sorted(set(changed) | plan.deletes)))
    paths = {ROOT / name for name in ("index.html", "archive.html", "about.html", "tools.html", "404.html")}
    for directory in ("posts", "tags", "tools"):
        paths.update((ROOT / directory).rglob("*.html"))
    paths.update(p for p in plan.files if p.suffix == ".html")
    paths.difference_update(plan.deletes)
    pages: dict[Path, _PageReferences] = {}
    for path in sorted(paths):
        if path not in plan.files and not path.exists():
            errors.append("缺少页面：%s" % path.relative_to(ROOT).as_posix())
            continue
        page = _PageReferences(plan.read(path))
        pages[path] = page
        for name, count in Counter(page.ids).items():
            if count > 1:
                errors.append("%s：重复的段落编号 id=%r" % (path.relative_to(ROOT).as_posix(), name))
    site = urlsplit(SITE["url"])
    site_path = unquote(site.path).rstrip("/")
    planned_names = {p.relative_to(ROOT).as_posix() for p in plan.files}

    def resolve_ref(source: Path, ref: str):
        url = urlsplit(ref)
        if url.scheme and url.scheme not in ("http", "https"):
            return None
        if url.netloc and url.netloc.casefold() != site.netloc.casefold():
            return None
        raw = unquote(url.path)
        if raw.startswith("/") and site_path and (raw == site_path or raw.startswith(site_path + "/")):
            raw = raw[len(site_path):] or "/"
        if not raw:
            target = source
        else:
            target = ROOT / raw.lstrip("/") if raw.startswith("/") else source.parent / raw
        target = Path(os.path.abspath(target))
        if raw.endswith("/") or target.is_dir():
            target /= "index.html"
        return target, unquote(url.fragment)

    def exists_exact(path: Path) -> bool:
        if not path.resolve().is_relative_to(ROOT.resolve()) or path in plan.deletes:
            return False
        rel = path.relative_to(ROOT)
        if path in plan.files:
            return rel.as_posix() in planned_names
        current = ROOT
        for part in rel.parts:
            if not current.is_dir() or part not in {p.name for p in current.iterdir()}:
                return False
            current /= part
        return current.is_file()

    references = [(p, ref) for p, page in pages.items() for ref in page.refs]
    for path in (ROOT / "css").rglob("*.css"):
        for ref in re.findall(r"url\(\s*['\"]?([^)'\"]+)['\"]?\s*\)", path.read_text(encoding="utf-8")):
            references.append((path, ref.strip()))
    for source, ref in references:
        try:
            resolved = resolve_ref(source, ref)
        except ValueError:
            errors.append("%s：链接格式不正确 %r" % (source.relative_to(ROOT).as_posix(), ref))
            continue
        if resolved is None:
            continue
        target, fragment = resolved
        if not exists_exact(target):
            errors.append("%s：找不到本地文件或大小写不一致 %r" % (source.relative_to(ROOT).as_posix(), ref))
        elif fragment and not fragment.startswith(":~:text=") and target in pages and fragment not in pages[target].ids:
            errors.append("%s：链接 %r 指向不存在的段落" % (source.relative_to(ROOT).as_posix(), ref))
    return list(dict.fromkeys(errors))


def cmd_check() -> int:
    plan, posts = make_build_plan()
    errors = check_site(plan)
    if errors:
        print("检查发现 %d 项问题：" % len(errors))
        for error in errors:
            print("  ! " + error)
        return 1
    print("检查通过：%d 篇文章，页面、段落链接、图片、脚本等本地引用有效，生成结果已同步。" % len(posts))
    return 0


def _preview_snapshot() -> dict[Path, tuple[int, int]]:
    paths = {ROOT / name for name in ("index.html", "archive.html", "about.html", "tools.html", "404.html")}
    for name in ("posts", "css", "js", "tools", "video", "PostPic"):
        for path in (ROOT / name).rglob("*"):
            if path.is_file() and not (name == "posts" and path.suffix == ".html"):
                if path.name != "search-index.js":
                    paths.add(path)
    return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists()}


def cmd_preview(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python build.py preview", description="在内存中构建并预览，修改后自动刷新")
    parser.add_argument("--port", type=int, default=8080, help="本地端口，默认 8080")
    parser.add_argument("--no-browser", action="store_true", help="只启动服务，不自动打开浏览器")
    options = parser.parse_args(args)
    if not 0 <= options.port <= 65535:
        raise BuildError("端口应在 0 到 65535 之间")
    plan, _ = make_build_plan()
    state = {"plan": plan, "version": 1}
    stop = threading.Event()

    class PreviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(ROOT), **kw)

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def virtual(self, head_only=False):
            route = urlsplit(self.path).path
            if route == "/__muroj_preview_version":
                data = str(state["version"]).encode("ascii")
                mime, status = "application/json", 200
            else:
                target = Path(self.translate_path(self.path))
                if target.is_dir() or route.endswith("/"):
                    target /= "index.html"
                current = state["plan"]
                if target in current.deletes or (target not in current.files and not target.is_file()):
                    target, status = ROOT / "404.html", 404
                else:
                    status = 200
                if target not in current.files and target.suffix != ".html":
                    return False
                text = current.read(target)
                if target.suffix == ".html":
                    script = ('<script data-muroj-preview>(function(){var v=%d;setInterval(function(){'
                              'fetch("/__muroj_preview_version",{cache:"no-store"}).then(function(r){return r.json();})'
                              '.then(function(n){if(n!==v)location.reload();}).catch(function(){});},900);})();</script>'
                              % state["version"])
                    text = text.replace("</body>", script + "\n</body>", 1)
                data = text.encode("utf-8")
                mime = self.guess_type(str(target)) + "; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if not head_only:
                self.wfile.write(data)
            return True

        def do_GET(self):
            if not self.virtual():
                super().do_GET()

        def do_HEAD(self):
            if not self.virtual(True):
                super().do_HEAD()

        def log_message(self, fmt, *args):
            if urlsplit(self.path).path != "/__muroj_preview_version":
                super().log_message(fmt, *args)

    def watch():
        previous = _preview_snapshot()
        while not stop.wait(0.5):
            try:
                current = _preview_snapshot()
                if current == previous:
                    continue
                previous = current
                new_plan, _ = make_build_plan()
                state["plan"] = new_plan
                state["version"] += 1
                print("预览已更新。", flush=True)
            except (OSError, ValueError) as exc:
                print("预览更新失败，暂时保留上次成功的页面：%s" % exc, flush=True)

    with ThreadingHTTPServer(("127.0.0.1", options.port), PreviewHandler) as server:
        address = "http://127.0.0.1:%d/" % server.server_port
        print("预览地址：%s\n修改 Markdown、页面或样式后会自动刷新；Ctrl+C 结束。" % address, flush=True)
        print("预览不会改写生成文件；发布前仍需运行 python build.py。", flush=True)
        for error in check_site(plan, include_stale=False):
            print("  ! " + error, flush=True)
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        if not options.no_browser:
            webbrowser.open(address)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n预览已停止。")
        finally:
            stop.set()
            watcher.join(timeout=2)
    return 0


def cmd_new(title: str, slug_arg: str | None = None) -> int:
    today = dt.date.today().isoformat()
    slug = slugify(slug_arg or title)[:60]
    validate_slug(slug)
    if "\n" in title or "\r" in title:
        raise BuildError("文章标题应写在一行内")
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
    parsed = urlsplit(new_url)
    if (parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment
            or re.search(r'[\s<>"\\]', new_url)):
        print("地址要以 http:// 或 https:// 开头，例如：")
        print("  python build.py url https://yourname.github.io")
        print("  python build.py url https://yourname.github.io/my-blog")
        return 1

    old_url = SITE["url"].rstrip("/")
    plan = BuildPlan()

    # 1) 改 build.py 自己的 SITE["url"]
    me = Path(__file__).resolve()
    src = me.read_text(encoding="utf-8")
    new_src, n_cfg = re.subn(
        r'("url"\s*:\s*)"[^"]*"',
        lambda m: m.group(1) + json.dumps(new_url, ensure_ascii=False),
        src, count=1,
    )
    if n_cfg:
        plan.write(me, new_src)
    else:
        raise BuildError("没能在 build.py 里找到 SITE[\"url\"]，未修改任何文件")

    # 2) 替换静态页面里写死的 canonical / og:url / og:image / feed.xml 地址
    targets = ["index.html", "archive.html", "about.html", "tools.html", "404.html", "README.md", "README2.md"]
    changed = 0
    for name in targets:
        f = ROOT / name
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        if old_url and old_url in text:
            plan.write(f, text.replace(old_url, new_url))
            changed += 1
    # 配置、静态页与生成页一起提交；转换失败时旧网址仍然有效。
    SITE["url"] = new_url
    try:
        plan, _ = make_build_plan(plan)
        plan.commit()
    except BaseException:
        SITE["url"] = old_url
        raise
    print("已将全站网址更新为 %s（同步 %d 个静态文件）。" % (new_url, changed))
    return 0


def main() -> int:
    args = sys.argv[1:]
    try:
        if not args or (args[0].lower() == "build" and len(args) == 1):
            return cmd_build()
        cmd = args[0].lower()
        if cmd == "preview":
            return cmd_preview(args[1:])
        if cmd == "check" and len(args) == 1:
            return cmd_check()
        if cmd == "new" and 2 <= len(args) <= 3:
            return cmd_new(args[1], args[2] if len(args) == 3 else None)
        if cmd == "list" and len(args) == 1:
            return cmd_list()
        if cmd == "url" and len(args) == 2:
            return cmd_url(args[1])
        if cmd in ("-h", "--help", "help"):
            print(__doc__)
            return 0
        print("未知命令或参数不正确：%s\n" % " ".join(args))
        print(__doc__)
        return 1
    except (OSError, ValueError) as exc:
        print("失败：%s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
