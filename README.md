# MineAI Blog — 纯静态个人博客模板

零依赖、零构建步骤的个人博客模板，专为 **GitHub Pages** 免费托管设计。

## 特性

- 纯 HTML / CSS / JavaScript，无任何框架与构建工具
- 深色 / 浅色主题切换（记忆用户选择，跟随系统偏好）
- 响应式布局，适配手机与桌面
- 文章归档页 + 标签筛选
- 文章页阅读进度条、代码块一键复制
- 自定义 404 页面
- 已包含 `.nojekyll`，关闭 GitHub Pages 的 Jekyll 处理
- 每篇文章标题下方的「由AI生成」声明标签（深浅色主题均适配）

## 目录结构

```
├── index.html          # 首页
├── archive.html        # 归档（标签筛选）
├── about.html          # 关于页
├── 404.html            # 404 页面
├── posts/              # 文章目录
│   ├── github-pages-guide.html
│   ├── css-thinking.html
│   └── hello-world.html
├── css/style.css       # 全部样式（CSS 变量主题系统）
├── js/main.js          # 全部交互（< 100 行）
└── .nojekyll
```

## 部署到 GitHub Pages

1. 在 GitHub 新建公开仓库，命名为 `你的用户名.github.io`
2. 推送本目录代码：

```bash
git init
git add .
git commit -m "Initial blog template"
git branch -M main
git remote add origin https://github.com/你的用户名/你的用户名.github.io.git
git push -u origin main
```

3. 仓库 **Settings → Pages → Build and deployment** 选择 **Deploy from a branch**，分支 `main`、目录 `/(root)`，保存
4. 约 1 分钟后访问 `https://你的用户名.github.io`

> 使用普通项目仓库（如 `my-blog`）也可以，访问地址为 `https://你的用户名.github.io/my-blog/`。

## 写新文章

1. 在 `posts/` 下复制任意一篇现有文章，改名并修改内容
2. 直接把标题下方的 AI 声明标签一并复制过去（见下节）
3. 在 `index.html` 的「最新文章」和 `archive.html` 的列表中各加一条对应卡片/条目

## 「由AI生成」声明标签

出现在每篇文章标题的正下方（文章页、首页卡片、归档列表）。

**样式来源**：`css/style.css` 中的 `.ai-notice`，颜色由主题变量控制：

| 变量 | 浅色 | 深色 | 说明 |
| --- | --- | --- | --- |
| `--ai-text` | `#5b47c4` | `#a99cf0` | 文字颜色（紫色，与站点橙色 `--accent` 区分开） |
| `--ai-bg` | `rgba(91,71,196,.07)` | `rgba(169,156,240,.12)` | 胶囊底色 |
| `--ai-border` | `rgba(91,71,196,.22)` | `rgba(169,156,240,.28)` | 描边 |

字体：`var(--font-sans)` 系统无衬线栈；字号 `0.75rem`（12px）；字重 `500`；圆角胶囊 `999px`。实测渲染为 `95 × 27.4 px`，在 360 / 390 / 768 / 1280px 宽度下均无横向溢出。

**复用的 HTML 片段**（整段复制，勿改 class 名）：

```html
<span class="ai-notice" title="本文内容由 AI 生成，仅供参考">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l1.9 4.6L18.5 9.5l-4.6 1.9L12 16l-1.9-4.6L5.5 9.5l4.6-1.9L12 3z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9L19 15z"/></svg>
  <span>由AI生成</span>
</span>
```

**纯人工撰写的文章**：删掉这段 `<span class="ai-notice">…</span>` 即可，无需改 CSS。
**只想在文章页显示、不想在列表显示**：删除 `index.html` 与 `archive.html` 里的同名片段。
**改文案**：只改最内层 `<span>由AI生成</span>` 的文字，`title` 属性里的长说明也一并改。

## 本地预览

直接双击 `index.html`，或启动本地服务器：

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```
