# 参与贡献

欢迎提交 Issue 和 Pull Request。

## 开发流程

1. Fork 本仓库
2. 从 main 切出功能分支：`git checkout -b feature/xxx`
3. 编写代码和测试
4. 运行测试：`PYTHONPATH="" python -m pytest server/tests/ -v`
5. 提交 PR，描述变更内容

## 代码规范

- Python: PEP 8 + type hints
- Vue: Composition API + `<script setup>`
- PR 描述四段式：功能描述 / 实现思路 / 测试方式 / 为什么这么设计

## 运行项目

```bash
./setup.sh
source venv/bin/activate
uvicorn server.app.main:app --reload --port 8000
```
