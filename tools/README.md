# tools/ — 小工具集合的内置工具目录

这个目录用来放**集成进博客项目**的小工具（区别于只跳转到外部网站的「external」工具）。

## 怎么加一个内置工具

### 第 1 步：在这里建子目录

```
tools/
└── markdown-preview/        ← 工具 id 作为目录名
    ├── index.html           ← 工具入口（必须叫 index.html）
    ├── main.js              ← 该工具自己的脚本（可选，自由组织）
    └── style.css            ← 该工具自己的样式（可选）
```

> 子目录名建议用全小写英文 + 连字符，和 `js/tools-data.js` 里的 `id` 字段保持一致。

### 第 2 步：在 `js/tools-data.js` 里登记一条

在 `window.MUROJ_TOOLS` 数组里加：

```js
{
  id: "markdown-preview",          // 和子目录名一致
  title: "Markdown 预览",
  desc: "本地即时预览 Markdown，不上传、不联网。",
  icon: "📝",                      // emoji 或 <svg>...</svg> 字符串
  tags: ["开发", "写作"],
  type: "native",                  // ← 关键：用 native 而不是 external
  url: "tools/markdown-preview/"   ← 相对路径，指向子目录
}
```

保存后刷新 `tools.html`，卡片就会出现，点击直接在本标签页打开该工具。

## 三种工具类型对照

| `type` | 含义 | 行为 | `url` |
|---|---|---|---|
| `external` | 外部网站 | 新标签页打开 | 完整 https 地址 |
| `native` | 项目内置工具 | 当前标签页跳转 | 相对路径 `tools/<id>/` |
| `planned` | 计划中、尚未实现 | 卡片置灰，显示「敬请期待」 | 留空 |

## 风格建议

内置工具如果想沿用博客的 Paper & Ink 风格，可以直接引用站点样式：

```html
<link rel="stylesheet" href="../css/style.css">
```

并复用 CSS 变量（`--accent`、`--surface`、`--text`、`--bg` 等），这样深浅色主题自动跟随。不想沿用也完全没问题——每个子目录是独立的小页面，自由发挥。

## 当前状态

| id | 类型 | 状态 |
|---|---|---|
| `muroj-markdown` | planned | 计划中（Markdown 预览） |

> 列表里只放已登记但 `type: planned` 或 `native` 的条目；纯 `external` 的不在这里建目录。
