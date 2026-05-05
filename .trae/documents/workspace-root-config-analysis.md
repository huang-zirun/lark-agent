# DevFlow workspace.root 配置问题分析

## 问题现象

从截图可以看到，用户通过飞书机器人向 DevFlow 发送消息：
> 创建一个贪吃蛇小游戏 html 网页单机游戏 界面是春天的感觉 美丽花花

DevFlow 回复：
> 仓库路径必须位于 workspace.root 内: D:\lark\workspaces。请只回复一行继续：仓库: D:\path\to\repo 或 新项目: snake-game。

## 问题根因

DevFlow 的 `workspace.root` 机制是一个**安全边界**，用于限制代码生成 agent 可以读写的文件范围。

### 代码逻辑（workspace.py）

```python
def _resolve_new_project(project_name: str, config: WorkspaceConfig) -> dict[str, Any]:
    cleaned = _safe_project_name(project_name)
    if not config.root:
        raise WorkspaceError("新建项目需要先配置 workspace.root。")
    root = Path(config.root).expanduser().resolve()
    project_path = (root / cleaned).resolve()
    _ensure_inside_root(project_path, root)   # <-- 强制限制在 root 内
    ...

def _resolve_existing_path(repo_path: str, config: WorkspaceConfig) -> dict[str, Any]:
    ...
    if config.root:
        _ensure_inside_root(resolved, Path(config.root).expanduser().resolve())  # <-- 强制限制在 root 内
    ...

def _ensure_inside_root(path: Path, root: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise WorkspaceError(f"仓库路径必须位于 workspace.root 内：{root}。") from exc
```

### 关键规则（design.md 已明确）

> - When `workspace.root` is configured, explicit repo paths and `workspace.default_repo` must both resolve inside that root; otherwise solution design blocks with the exact root-boundary reason.
> - 如果配置了 `workspace.root`，默认仓库也必须位于该目录内

## 当前配置推断

从错误信息 `D:\lark\workspaces` 可以推断，当前 `config.json` 中的配置大概是：

```json
{
  "workspace": {
    "root": "D:\\lark\\workspaces",
    "default_repo": ""
  }
}
```

而用户发送的消息中没有包含 `仓库：...` 或 `新项目：...` 的上下文，导致 DevFlow 尝试使用默认逻辑时，发现没有可用的工作区路径，最终触发了阻塞。

实际上，从日志 `2026-05-03-workspace-blocked-guidance.md` 也证实了这一点：
> `workspace.default_repo = D:\lark` was outside `workspace.root = D:\lark\workspaces`

这说明之前已经发生过类似的配置不匹配问题。

## 解决方案

### 方案一：修改 workspace.root 指向 D:\lark（推荐，如果项目放在 D:\lark 下）

```json
{
  "workspace": {
    "root": "D:\\lark",
    "default_repo": ""
  }
}
```

这样：
- `新项目：snake-game` 会创建到 `D:\lark\snake-game`
- 如果以后指定 `仓库：D:\lark\some-project` 也能通过边界检查

### 方案二：保持 workspace.root 为 D:\lark\workspaces，但把项目移入该目录

```json
{
  "workspace": {
    "root": "D:\\lark\\workspaces",
    "default_repo": "D:\\lark\\workspaces\\snake-game"
  }
}
```

然后在飞书中回复：
```
新项目：snake-game
```

或预先创建好目录后回复：
```
仓库：D:\lark\workspaces\snake-game
```

### 方案三：清空 workspace.root（不推荐，会降低安全性）

```json
{
  "workspace": {
    "root": "",
    "default_repo": ""
  }
}
```

这样 DevFlow 不会对路径做限制，但代码生成 agent 可以读写任意路径，存在安全风险。

## 建议配置

根据用户的实际工作目录 `D:\lark`，**推荐方案一**：

```json
{
  "llm": {
    "provider": "ark",
    "api_key": "你的API密钥",
    "model": "你的模型ID",
    "base_url": "",
    "temperature": 0.2,
    "max_tokens": 2000,
    "timeout_seconds": 120,
    "response_format_json": false
  },
  "lark": {
    "cli_version": "1.0.23",
    "app_id": "你的AppID",
    "app_secret": "你的AppSecret",
    "test_doc": "",
    "prd_folder_token": ""
  },
  "workspace": {
    "root": "D:\\lark",
    "default_repo": ""
  },
  "approval": {
    "enabled": false,
    "definition_code": "",
    "poll_interval_seconds": 60
  }
}
```

## 后续操作

修改 `config.json` 后，用户在飞书中只需回复：
```
新项目：snake-game
```

DevFlow 就会：
1. 在 `D:\lark\snake-game` 创建新项目目录
2. 初始化 Git
3. 继续执行技术方案设计和评审卡片推送
