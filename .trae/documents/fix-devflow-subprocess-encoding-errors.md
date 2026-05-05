# 修复 devflow 两个运行时错误

## 问题分析

终端输出中存在 **两个独立的错误**，均发生在 `devflow start` 流程中：

---

### 错误 1：`UnicodeDecodeError: 'gbk' codec can't decode byte 0xae`

**位置**：`subprocess.py` → `_readerthread` → `buffer.append(fh.read())`

**根本原因**：
- [tools.py:147-154](file:///D:/lark/devflow/code/tools.py#L147-L154) 的 `powershell()` 方法调用 `subprocess.run()` 时使用了 `text=True`，但**没有显式指定 `encoding` 参数**。
- 在 Windows 中文环境下，`text=True` 默认使用系统编码 **GBK**（`locale.getpreferredencoding()` 返回 `gbk`）。
- PowerShell 输出中包含 GBK 无法解码的字节（如 `0xae`），导致解码失败。
- 当 `subprocess.run` 内部的 `_readerthread` 读取 stdout/stderr 时触发 `UnicodeDecodeError`，该异常导致 `completed.stdout` 和 `completed.stderr` 为 `None`。

**对比**：项目中其他地方已正确处理了此问题：
- [delivery/agent.py:218](file:///D:/lark/devflow/delivery/agent.py#L218)：`encoding="utf-8", errors="replace"`
- [intake/lark_cli.py:53](file:///D:/lark/devflow/intake/lark_cli.py#L53)：`encoding="utf-8"`

---

### 错误 2：`TypeError: 'NoneType' object is not subscriptable`

**位置**：[tools.py:158](file:///D:/lark/devflow/code/tools.py#L158) — `completed.stdout[-4000:]`

**根本原因**：
- 这是**错误 1 的连锁反应**。由于 `UnicodeDecodeError` 异常发生在 `subprocess.run` 内部的读取线程中，`completed.stdout` 和 `completed.stderr` 未能正常赋值，结果为 `None`。
- 代码直接对 `None` 执行切片操作 `[-4000:]`，触发 `TypeError`。

**同样的问题也存在于** [tools.py:210-218](file:///D:/lark/devflow/code/tools.py#L210-L218) 的 `capture_git_diff()` 函数，虽然该函数在当前报错路径中未被触发，但存在相同隐患。

---

## 修复方案

### 修改文件：`devflow/code/tools.py`

#### 修复点 1：`powershell()` 方法（第 147-160 行）

- 添加 `encoding="utf-8"` 和 `errors="replace"` 参数到 `subprocess.run()` 调用
- 添加 `None` 安全检查：当 `stdout`/`stderr` 为 `None` 时使用空字符串兜底

修改前：
```python
def powershell(self, command: str, timeout_seconds: int) -> dict[str, Any]:
    validate_powershell_command(command)
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=self.root,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "status": "success" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }
```

修改后：
```python
def powershell(self, command: str, timeout_seconds: int) -> dict[str, Any]:
    validate_powershell_command(command)
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        cwd=self.root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    return {
        "status": "success" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": (completed.stdout or "")[-4000:],
        "stderr": (completed.stderr or "")[-4000:],
    }
```

#### 修复点 2：`capture_git_diff()` 函数（第 210-218 行）

- 同样添加 `encoding="utf-8"` 和 `errors="replace"` 参数
- 添加 `None` 安全检查

修改前：
```python
def capture_git_diff(workspace_root: Path | str) -> str:
    root = Path(workspace_root).expanduser().resolve()
    if not (root / ".git").exists():
        return ""
    completed = subprocess.run(
        ["git", "diff", "--no-ext-diff"],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return completed.stdout if completed.returncode == 0 else ""
```

修改后：
```python
def capture_git_diff(workspace_root: Path | str) -> str:
    root = Path(workspace_root).expanduser().resolve()
    if not (root / ".git").exists():
        return ""
    completed = subprocess.run(
        ["git", "diff", "--no-ext-diff"],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=30,
        check=False,
    )
    return (completed.stdout or "") if completed.returncode == 0 else ""
```

---

## 修复要点总结

| 问题 | 根因 | 修复 |
|------|------|------|
| `UnicodeDecodeError: 'gbk'` | `subprocess.run` 在 Windows 中文环境下默认用 GBK 解码 | 添加 `encoding="utf-8", errors="replace"` |
| `TypeError: 'NoneType' not subscriptable` | 解码异常导致 `stdout` 为 `None` | 添加 `(completed.stdout or "")` 防御性检查 |

两处修改遵循项目中 [delivery/agent.py](file:///D:/lark/devflow/delivery/agent.py#L214-L223) 和 [intake/lark_cli.py](file:///D:/lark/devflow/intake/lark_cli.py#L48-L55) 已有的编码处理模式，保持一致性。
