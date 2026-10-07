# MurojBlog

> 孟然君的个人博客 —— 写些想法和日常。
> 纯静态、零依赖，托管在 GitHub Pages 上。

这里是孟然君博客的**源代码仓库**。站点本身只有 HTML / CSS / JavaScript，
没有框架、没有数据库、没有服务器；文章用 Markdown 写，一条命令生成网页。

访问地址：<https://mengranjun.github.io/> 

日后如果我有新点子，也会尝试优化提示词，让不同的AI把我的想象变为现实。

如果你对这个项目感兴趣，想省点麻烦的话，可以参考下面AI写的内容，或参考“README2.md”文件。

---

## 用处

创建这个博客目的很简单：这个项目用来作为Vibe Code的一次尝试。

作为Vibe Code的第四次实例，本项目会通过更完整的提示词让不同的AI让我的想法变成具体的实物。顺便锻炼我自己的AI能力和学习能力。

当前使用AI情况如下：
KimiK3 + DSH(*7) + K3 + GLM5.2

---

## 以下内容由AI生成
## 写一篇文章

```bash
# 1. 生成草稿（自动带日期和 front matter 模板）
python build.py new "我的第一篇笔记"

#    想要简短的英文网址，就在后面再加一个文件名
python build.py new "我的第一篇笔记" my-first-note

# 2. 用任意编辑器（VS Code / Typora / 记事本）打开 posts/ 下新出现的 .md，写正文

# 3. 生成网页
python build.py

# 4. 本地预览
python -m http.server 8080        # 打开 http://localhost:8080

# 5. 发布
git add . && git commit -m "new post" && git push
```

其他命令：

```bash
python build.py list                    # 列出所有文章
python build.py url https://你的地址     # 一次性改好全站网址（部署前跑一次）
```

> **工作原理**：`posts/*.md` 是唯一的内容来源。`build.py` 会
> ① 把每篇 `.md` 渲染成 `posts/<同名>.html`；
> ② 把首页卡片写进 `index.html` 的 `BUILD:POSTS` 标记之间；
> ③ 把归档列表、标签按钮、文章总数写进 `archive.html` 的对应标记之间；
> ④ 重新生成 `sitemap.xml` 与 `feed.xml`。
> **标记之外的 HTML 不会被改动**，所以首页文案、关于页，这些可以放心手改。

---

## 目录结构

```
├── build.py              # 构建脚本（只用 Python 标准库）
├── index.html            # 首页（卡片区由 build.py 填充）
├── archive.html          # 归档（热力图 / 列表 / 标签 / 计数由 build.py 填充）
├── about.html            # 关于页（手写，含姓名彩蛋）
├── 404.html              # 404 页（样式内联 + 像素小游戏）
├── feed.xml              # RSS 订阅（自动生成）
├── sitemap.xml           # 站点地图（自动生成）
├── og-image.png          # 社交平台分享卡片 1200×630
├── favicon.svg           # 站点图标（矢量）
├── favicon.ico           # 站点图标（兼容旧浏览器）
├── apple-touch-icon.png  # iOS 添加到主屏幕图标
├── posts/
│   ├── *.md              # ← 只需要写这些
│   └── *.html            # 由 build.py 生成，不要手改
├── tags/                 # 标签页（自动生成，含 index.html 总览）
├── css/style.css         # 全部样式（CSS 变量主题系统）
├── js/
│   ├── main.js           # 核心交互（主题、菜单、复制、筛选…）
│   ├── enhance.js        # 渐进增强效果（见下）
│   └── search-index.js   # 站内搜索数据（自动生成，勿手改）
└── .nojekyll
```

---

## 站内的各种交互

`js/enhance.js` 里每个效果都会先检查页面上有没有对应元素，没有就静默跳过。
全部尊重 `prefers-reduced-motion`，鼠标相关效果在触屏设备上自动关闭。

| 效果 | 触发方式 |
| --- | --- |
| **主题圆形扩散** | 点右上角主题按钮，新主题从按钮位置扩散铺满全屏（View Transitions） |
| **首页柔光跟随光标** | 鼠标在首页大标题区域移动，背景光晕带阻尼跟着走 |
| **卡片 3D 倾斜** | 鼠标划过首页文章卡片，卡片微微朝光标倾斜并有一道高光 |
| **命令面板** | `Ctrl` / `⌘ + K`，或按 `/`，或点页头放大镜；模糊搜索标题/标签/摘要/正文 |
| **文章目录** | 文章页自动生成；窗口 ≥1200px 时浮在左侧，滚动时高亮当前小节 |
| **打字机标题** | 打开首页时逐字敲出（结构先占位，所以不会上下跳） |
| **回到顶部** | 向下滚 420px 后右下角出现，圆环显示阅读进度 |
| **继续阅读** | 文章读到 8%~92% 后离开，再回来时底部提示「上次读到 N%」 |
| **卡片长大成文章** | 点首页卡片，卡片原地放大变形成文章标题（跨页面 View Transition） |
| **404 像素小游戏** | 打开任意的错误地址 |

> **继续阅读为什么是提示而不是自动跳转？** 自动把页面滚到中间会让人以为加载出错，
> 给一个可以点也可以忽略的小条更稳妥。提示 14 秒后自动消失。

> **卡片→文章的转场**需要浏览器支持 Cross-Document View Transitions
> （Chrome 126+ / Safari 18.2+）。不支持的浏览器就是普通跳转，没有副作用。

---

## 代码块

Markdown 里写围栏代码块就会自动得到：**行号 + 语法高亮 + 一键复制**。

支持的语法名：`bash` / `sh` / `js` / `javascript` / `json` / `python` / `py` /
`css` / `html` / `xml` / `yaml`。其他语言会退化成不带高亮的等宽代码块，照样能用。

高亮是 `build.py` 里一个几十行的极简实现（零依赖），只认注释、字符串、关键字、
数字和 CSS 自定义属性。**复制按钮会先剥掉行号**再写入剪贴板，粘出来是干净的代码。

---

## 标签页

`build.py` 会自动为每个标签生成 `tags/<标签名>.html`，以及一个 `tags/index.html` 总览页。
归档页里每篇文章下方的标签是可以点的，点进去就是该标签下的全部文章。

标签是从文章的 front matter 里自动收集的，不需要手工维护列表。

---

## 写作热力图

归档页顶部那张格子图是 `build.py` 按「年 × 月」统计出来的，
颜色深浅表示当月发文量，鼠标悬停能看到「2026 年 9 月 · 2 篇」。


---

## 文章格式

每篇 `.md` 开头是一段 front matter：

```markdown
---
title: 文章标题
date: 2026-10-02
tags: 随笔, AI
summary: 一句话摘要，显示在首页卡片与归档列表里。
ai: true
---

正文从这里开始。
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 是 | 文章标题 |
| `date` | 建议 | `YYYY-MM-DD`，决定排序；不写则用文件修改时间 |
| `tags` | 否 | 逗号分隔；第一个标签显示在首页卡片左上角，全部标签自动进入归档筛选栏 |
| `summary` | 否 | 摘要，用于卡片、归档列表、搜索描述与 RSS |
| `ai` | 否 | `true`/`false`，标题下是否显示「由AI生成」标签，默认 `true` |
| `minutes` | 否 | 手动指定「约 N 分钟读完」；不写则按字数自动估算 |
| `slug` | 否 | 自定义输出文件名 |

### 支持的 Markdown 语法

| 写法 | 效果 |
| --- | --- |
| `## 标题` / `### 标题` | 二级 / 三级标题（`#` 也当二级标题） |
| `**粗体**` `*斜体*` `` `行内代码` `` `~~删除线~~` | 行内样式 |
| `[文字](链接)` `![说明](图片)` | 链接与图片（图片自动加 `loading="lazy"`） |
| `- 项目` / `1. 项目` | 无序 / 有序列表，**缩进两格即可嵌套** |
| `> 引用` | 引用块 |
| ` ```语言 … ``` ` | 代码块，自动带「复制」按钮 |
| `\| 表格 \|` | 表格（表头下一行写 `\| --- \| --- \|`） |
| `---` | 分隔线 |
| `<br>`、`<span>` 等原生 HTML | 原样保留，可用来做特殊排版 |

段落里**换行不会变成空格**：中文之间自动直接相连，英文之间才补空格，
所以一行写多长、随时回车断句都不影响最终排版。

---

## 配色与品牌

主题色集中在 `css/style.css` 顶部的两个变量块，改那里就能整体换色。

| 变量 | 浅色 | 深色 | 用途 |
| --- | --- | --- | --- |
| `--bg` | `#f4f9fb` | `#0c1418` | 页面底色 |
| `--surface` | `#ffffff` | `#131e23` | 卡片 / 菜单 / 代码块 |
| `--accent` | `#0e7490` | `#38bdf8` | 链接、标签、标题左侧竖线 |
| `--grad-1/2/3` | `#0ea5e9` / `#06b6d4` / `#10b981` | 同左 | 品牌渐变（蓝 → 青 → 绿） |
| `--ai-text` | `#4338ca` | `#a5b4fc` | 「由AI生成」标签文字 |

`--brand-grad` 是上面三色的 135° 渐变，用在 LOGO、关于页头像、主按钮、
阅读进度条、首页标题高亮和关于页的英文名上。

**换 LOGO**：LOGO 就是一条描边路径，`M` 的写法是

```html
<svg viewBox="0 0 32 32"><path d="M9 23.2V8.8L16 18.2L23 8.8V23.2"
  fill="none" stroke="currentColor" stroke-width="4.2"
  stroke-linecap="round" stroke-linejoin="round"/></svg>
```

改 `d` 就能换字母。站点图标另有 `favicon.svg` / `favicon.ico` /
`apple-touch-icon.png` 三个文件，换图标时都要替换。

---

## 关于页的姓名彩蛋（支持多个名字）

关于页那个「孟然君」是可以玩的，而且**名字数量不限**。

**桌面端**

1. 鼠标移到「孟然君」上 → 上方拉出菜单，复选框亮起并一笔画出对勾
2. **滚动滚轮上/下** → 复选框在名字列表里上下滑动，显示的名字跟着滚入滚出
3. 鼠标移开后**菜单保持展开**（按 `Esc` 或点别处才收起）
4. 下方描述跟着一起替换

滚到列表两端时会**放行滚动事件**，页面正常滚动，不会把人「卡」在名字上。

**移动端**：点一下名字就切换到下一个（循环），菜单会自己收起。

**键盘**：`Tab` 聚焦后按 `↑` / `↓` 切换。

### 再加一个名字

只改 `about.html` 里两个地方，顺序一一对应即可：

```html
<!-- ① 菜单里加一行 -->
<span class="alias-list">
  <span class="alias-opt">孟然君</span>
  <span class="alias-opt">Muroj</span>
  <span class="alias-opt">新名字</span>     ← 加这里
</span>

<!-- ② 名字舞台里也加一行 -->
<span class="alias-stage" aria-hidden="true">
  <span class="alias-name">孟然君</span>
  <span class="alias-name">Muroj</span>
  <span class="alias-name">新名字</span>     ← 加这里
</span>
```

中文名自动用衬线体、纯英文名自动用无衬线粗体，**不用手动设置字体**。
名字再多也不会撑破布局：所有名字叠在同一格里，宽度取最宽的那个。

样式在 `css/style.css` 里搜索「姓名彩蛋」，逻辑在 `js/enhance.js` 里搜索 `aliasSwitcher`。
描述有两种写法（**替换**原段落 / **新增**一段），说明都写在 `about.html` 的注释里，
两段文字行数不同时容器高度会自动跟着当前显示的那一段走，不会留出空白。

---

## 部署到 GitHub Pages

1. 在 GitHub 新建**公开**仓库，命名为 `你的用户名.github.io`
   （想要 `https://用户名.github.io` 这样的短域名就必须这么命名）
2. 推送代码：

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/你的用户名/你的用户名.github.io.git
git push -u origin main
```

3. 仓库 **Settings → Pages → Build and deployment**，选 **Deploy from a branch**，
   分支 `main`、目录 `/(root)`，保存。约一分钟后访问 `https://你的用户名.github.io`

4. **把网址改对**（重要，只跑一次）：

```bash
python build.py url https://你的用户名.github.io
```

这条命令会自动帮你改好 `build.py` 里的配置、四个静态页里写死的
`canonical` / `og:url` / `og:image` 地址、以及 `sitemap.xml`、`feed.xml`，
然后重新构建一遍。改完记得 `git add . && git commit -m "set site url" && git push`。

> 用普通项目仓库（如 `my-blog`）也可以，此时网址是
> `https://你的用户名.github.io/my-blog`，那么第 4 步就写这个完整地址。

---

## 本地预览

直接双击 `index.html` 也能看，但推荐起一个本地服务器（路径和线上一致）：

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```

---

## 环境要求

只需要 **Python 3.8+**，不需要 `pip install` 任何东西 —— `build.py` 只用标准库。
Windows 下控制台编码会在脚本里自动切成 UTF-8，不会出现中文乱码。
