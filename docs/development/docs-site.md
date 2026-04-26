# 构建文档站点

项目使用 MkDocs Material 构建文档站点。

## 安装文档依赖

```bash
pip install mkdocs mkdocs-material pymdown-extensions
```

## 本地预览

在项目根目录运行：

```bash
mkdocs serve
```

默认访问：

```text
http://127.0.0.1:8000
```

## 构建静态文件

```bash
mkdocs build
```

生成内容默认位于 `site/`，可以部署到 GitHub Pages、Nginx、Cloudflare Pages 或任意静态站点服务。

## 文档维护建议

- `guide/` 放学习路径和基础概念。
- `recipes/` 放完整可运行任务示例。
- `reference/` 放 API 参考，不要写太多入门解释。
- `adapters/` 放 OneBot、NoneBot2 等协议适配说明。
- 示例代码尽量完整，避免只写孤立的一行 API 调用。
