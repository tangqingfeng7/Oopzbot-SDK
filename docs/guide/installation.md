# 安装

本页只说明 SDK 安装。文档站点构建和开发环境说明见 [构建文档站点](../development/docs-site.md)。

## 环境要求

- Python `>= 3.10`

## 从 PyPI 安装

```bash
pip install oopz-sdk
```

## 从源码安装

```bash
git clone https://github.com/tangqingfeng7/Oopzbot-SDK.git
cd Oopzbot-SDK
pip install -e .
```

如果需要运行测试或参与开发，可以安装开发依赖：

```bash
pip install -e ".[dev]"
pytest
```

## 可选：语音推流依赖

`Voice Service` 当前使用 Playwright 浏览器后端。首次使用语音功能前需要安装 Chromium：

```bash
python -m playwright install chromium
```

Linux 服务器可能还需要安装浏览器系统依赖：

```bash
python -m playwright install-deps chromium
```

无图形界面服务器建议保持默认无头模式：

```python
OopzConfig(..., voice_browser_headless=True)
```

## 验证安装

```bash
python -c "import oopz_sdk; print(oopz_sdk.__version__)"
```

能正常输出版本号即可。
