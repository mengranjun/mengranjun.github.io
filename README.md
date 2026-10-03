# MineAI Blog — 纯静态个人博客

零依赖、零构建工具的个人博客，专为 **GitHub Pages** 免费托管设计。
写文章只需要写 Markdown，其余交给 `build.py`。

## 特性

- 纯 HTML / CSS / JavaScript，运行时零框架、零 CDN 依赖
- **用 Markdown 写文章**，一条命令生成全部 HTML
- 首页卡片、归档列表、标签筛选、文章计数全部自动生成
- 深色 / 浅色主题切换（记忆选择、跟随系统、无首屏闪白）
- 蓝 → 青 → 绿渐变品牌色，配套的圆角描边风 LOGO 与站点图标
- 文章页阅读进度条、代码块一键复制、滚动渐入
- 自动生成 `sitemap.xml`、`feed.xml`（RSS 订阅）、Open Graph 分享卡片
- 响应式布局，无障碍属性（`aria-*`）齐备
- 已包含 `.nojekyll`，关闭 GitHub Pages 的 Jekyll 处理

## 快速开始：写一篇文章

```bash
# 1. 生成一篇 Markdown 草稿（会自动带上日期与 front matter 模板）
python build.py new "我的第一篇技术笔记"

#    想要简短的英文网址，就在后面再加一个文件名
python build.py new "我的第一篇技术笔记" my-first-note
#    → posts/my-first-note.md  →  网址 /posts/my-first-note.html

# 2. 用任意编辑器（VS Code / Typora / 记事本）打开 posts/ 下新出现的 .md，写正文

# 3. 生成 HTML
python build.py

# 4. 本地预览
python -m http.server 8080     # 然后打开 http://localhost:8080

# 5. 发布
git add . && git commit -m "new post" && git push
```

> 不指定文件名时，`.md` 的文件名就是标题本身（中文也没问题，GitHub Pages 支持中文网址，只是复制出来会变成百分号编码）。

其他命令：

```bash
python build.py list     # 列出所有文章
python build.py          # 只构建（等同于 python build.py build）
```

> **工作原理**：`posts/*.md` 是唯一的内容来源。`build.py` 会
> ①把每篇 `.md` 渲染成 `posts/<同名>.html`；
> ②把首页卡片写进 `index.html` 的 `BUILD:POSTS` 标记之间；
> ③把归档列表、标签按钮、文章总数写进 `archive.html` 的对应标记之间；
> ④重新生成 `sitemap.xml` 与 `feed.xml`。
> **标记之外的 HTML 不会被改动**，你可以放心手改首页文案、关于页等。

## 目录结构

```
├── build.py              # 构建脚本（Python 标准库，无需 pip install）
├── index.html            # 首页（卡片区由 build.py 填充）
├── archive.html          # 归档（列表/标签/计数由 build.py 填充）
├── about.html            # 关于页（手写）
├── 404.html              # 404 页（样式内联，任意深度的错误地址都能正常显示）
├── feed.xml              # RSS 订阅（自动生成）
├── sitemap.xml           # 站点地图（自动生成）
├── og-image.png          # 社交平台分享卡片 1200×630
├── favicon.svg           # 站点图标（矢量，任意缩放）
├── favicon.ico           # 站点图标（16/32/48/64 位图，兼容旧浏览器）
├── apple-touch-icon.png  # iOS 添加到主屏幕图标 180×180
├── posts/
│   ├── *.md              # ← 你只需要写这些文件
│   └── *.html            # 由 build.py 生成，不要手改
├── css/style.css         # 全部样式（CSS 变量主题系统）
├── js/main.js            # 全部交互
└── .nojekyll
```

## 文章格式

每篇 `.md` 开头是一段 front matter：

```markdown
---
title: 文章标题
date: 2026-10-02
tags: 部署, GitHub
summary: 一句话摘要，显示在首页卡片与归档列表里。
ai: true
---

正文从这里开始。
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 是 | 文章标题 |
| `date` | 建议 | `YYYY-MM-DD`，决定排序与归档顺序；不写则用文件修改时间 |
| `tags` | 否 | 逗号分隔；第一个标签显示在首页卡片左上角，全部标签自动进入归档筛选栏 |
| `summary` | 否 | 摘要，用于卡片、归档列表、`meta description` 与 RSS |
| `ai` | 否 | `true`/`false`，是否在标题下显示「由AI生成」标签，默认 `true` |
| `minutes` | 否 | 手动指定「约 N 分钟读完」；不写则按字数自动估算 |
| `slug` | 否 | 自定义输出文件名；不写则用 `.md` 的文件名 |

### 支持的 Markdown 语法

| 写法 | 效果 |
| --- | --- |
| `## 标题` / `### 标题` | 二级 / 三级标题（`#` 也当二级标题，文章大标题由 front matter 决定） |
| `**粗体**`、`*斜体*`、`` `行内代码` ``、`~~删除线~~` | 行内样式 |
| `[文字](链接)`、`![说明](图片)` | 链接与图片（图片自动加 `loading="lazy"`） |
| `- 项目` / `1. 项目` | 无序 / 有序列表，**缩进两格即可嵌套** |
| `> 引用` | 引用块 |
| ` ```语言 … ``` ` | 代码块，自动带「复制」按钮 |
| `\| 表格 \|` | 表格（表头下一行写 `\| --- \| --- \|`） |
| `---` | 分隔线 |
| `<br>`、`<span>` 等原生 HTML | 原样保留，可用来做特殊排版 |

段落里**换行不会变成空格**：中文之间自动直接相连，英文之间才补空格，所以一行写很长、随时回车断句都不会影响排版。

## 配色与品牌

主题色定义在 `css/style.css` 顶部，改那两个变量块即可整体换色。

| 变量 | 浅色 | 深色 | 用途 |
| --- | --- | --- | --- |
| `--bg` | `#f4f9fb` | `#0c1418` | 页面底色 |
| `--surface` | `#ffffff` | `#131e23` | 卡片 / 代码块外的面板 |
| `--accent` | `#0e7490` | `#38bdf8` | 链接、标签、标题左侧竖线 |
| `--grad-1/2/3` | `#0ea5e9` / `#06b6d4` / `#10b981` | 同左 | 品牌渐变（蓝 → 青 → 绿） |
| `--ai-text` | `#4338ca` | `#a5b4fc` | 「由AI生成」标签文字 |

`--brand-grad` 是 `--grad-1 → --grad-2 → --grad-3` 的 135° 渐变，用在 LOGO、关于页头像、主按钮、阅读进度条和首页标题高亮上。

**换 LOGO**：LOGO 由一条描边路径定义，`M` 的写法是

```html
<svg viewBox="0 0 32 32"><path d="M9 23.2V8.8L16 18.2L23 8.8V23.2"
  fill="none" stroke="currentColor" stroke-width="4.2"
  stroke-linecap="round" stroke-linejoin="round"/></svg>
```

改 `d` 就能换字母。站点图标另存于 `favicon.svg` / `favicon.ico` / `apple-touch-icon.png`，换图标时三个都要替换。

## 部署到 GitHub Pages

1. 在 GitHub 新建公开仓库，命名为 `你的用户名.github.io`（想要 `https://用户名.github.io` 这样的短域名）
2. 推送代码：

```bash
git init
git add .
git commit -m "Initial blog"
git branch -M main
git remote add origin https://github.com/你的用户名/你的用户名.github.io.git
git push -u origin main
```

3. 仓库 **Settings → Pages → Build and deployment** 选 **Deploy from a branch**，分支 `main`、目录 `/(root)`

> **部署前记得改两处地址**：
> 1. `build.py` 里的 `SITE["url"]` —— 改成你的真实地址，否则 `sitemap.xml`、`feed.xml` 和分享卡片的链接会是占位值；
> 2. 各 HTML 里的 `og:url` / `canonical` —— 它们是静态写死的，`index.html`、`archive.html`、`about.html`、`404.html` 各一处。
> 改完重新运行 `python build.py`。

## 本地预览

直接双击 `index.html`，或启动本地服务器（推荐，路径与线上一致）：

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```

## 环境要求

只需要 **Python 3.8+**，不需要 `pip install` 任何东西 —— `build.py` 只用标准库。
Windows 上双击运行也可以，控制台编码已在脚本内自动切成 UTF-8。
