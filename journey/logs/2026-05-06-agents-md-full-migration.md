# AGENTS.md 完整迁移到 Journey 系统

## 迁移内容

将 `d:\lark\AGENTS.md` 的完整内容迁移到 `journey/design.md`，确保项目规范统一存储在 journey 目录下。

## 迁移详情

### 1. Working Rules（已存在，保持不变）
- Use `uv` for Python
- Use PowerShell
- PowerShell Limitation（不支持 `&&`）
- Use Standard Git Commit
- Clean Up Temporary Scripts

### 2. Journey Memory（新增）
- Use `journey/` as the shared project memory across agent sessions
- Read `journey/design.md` first at the start of each session
- Use `journey/logs/` for chronological process notes
- Use `journey/research/` for research notes
- Update `journey/design.md` whenever the effective understanding changes
- Plan files: `journey/plans/YYYY-MM-DD-{title}.md`
- Log files: `journey/logs/YYYY-MM-DD-{title}.md`

## 文件变更

- `journey/design.md` - 添加 Journey Memory 部分

## 后续建议

原始的 `d:\lark\AGENTS.md` 文件可以保留作为参考，但后续更新应优先修改 `journey/design.md`。根据 Journey Memory 的规范：

> Read `journey/design.md` first at the start of each session. It is the canonical snapshot of the project.

这意味着 `journey/design.md` 现在是项目规范的权威来源。
