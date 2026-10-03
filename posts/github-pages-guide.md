---
title: 零成本上线：用 GitHub Pages 托管个人博客
date: 2026-10-02
tags: 部署, GitHub
summary: 从注册账号到推送代码、开启 Pages 服务，完整走通一次静态站点部署流程，并解释它为什么适合个人博客。
ai: true
---

个人博客最劝退的部分从来不是写作，而是运维：买服务器、配 Nginx、续费域名、担心被攻击。GitHub Pages 把这些问题一次性解决了——它是 GitHub 官方提供的**免费静态站点托管服务**，你只需要把 HTML 文件 push 到仓库，网站就上线了。

## 它为什么适合个人博客

- **完全免费**：没有服务器费用，自带 HTTPS 证书。
- **全球 CDN**：GitHub 的内容分发网络，访问速度有保障。
- **版本管理即发布**：git push 就是部署，回滚就是 git revert。
- **稳定性高**：背靠 GitHub 基础设施，比自己维护的小 VPS 可靠得多。

## 部署步骤

### 1. 创建仓库

在 GitHub 上新建一个公开仓库。如果想要 `https://用户名.github.io` 这样的短域名，仓库名必须命名为 `用户名.github.io`；普通项目仓库则会得到 `https://用户名.github.io/仓库名/` 的地址。

### 2. 推送代码

```bash
git init
git add .
git commit -m "Initial blog template"
git branch -M main
git remote add origin https://github.com/用户名/用户名.github.io.git
git push -u origin main
```

### 3. 开启 Pages

进入仓库的 **Settings → Pages**，在 "Build and deployment" 中选择 **Deploy from a branch**，分支选 `main`、目录选 `/(root)`，保存。大约一分钟后，访问 `https://用户名.github.io` 就能看到网站。

> 提示：本模板根目录包含一个 `.nojekyll` 空文件，用于关闭 GitHub Pages 默认的 Jekyll 构建流程，确保所有文件按原样发布。

## 需要注意的限制

GitHub Pages 只支持**静态内容**——没有服务端语言、没有数据库。评论、统计这类动态功能需要借助第三方服务（如 Giscus 评论系统）。此外官方建议站点体积不超过 1GB、每月带宽不超过 100GB，对个人博客而言绰绰有余。

## 小结

如果你的博客只是"文章 + 页面"，GitHub Pages 几乎是零成本方案里的最优解。把省下来的运维精力，花在写作本身上。
