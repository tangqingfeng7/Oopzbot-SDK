# 贡献指南

欢迎提交 Issue、文档修改和代码改进。

## 开发环境

```bash
git clone https://github.com/tangqingfeng7/Oopzbot-SDK.git
cd Oopzbot-SDK
pip install -e ".[dev]"
pytest
```

## 提交文档修改

文档修改建议遵循：

1. 凭证全部使用环境变量，不要写真实 token。
2. 如果文档中的 API 名称和代码不一致，以代码为准并同步修正文档。

## 提交代码修改

建议先运行：

```bash
pytest
```

如果新增 service 或模型，请同步更新：

- `docs/reference/services.md`
- 对应 service 参考页
- 至少一个 `recipes/` 示例，如果是常见任务
