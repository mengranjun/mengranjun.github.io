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
2. 在 `index.html` 的「最新文章」和 `archive.html` 的列表中各加一条对应卡片/条目

## 本地预览

直接双击 `index.html`，或启动本地服务器：

```bash
python -m http.server 8080
# 访问 http://localhost:8080
```
