# Pipeline 文件系统操作与 Git 仓库初始化问题系统性修复 Spec

## Why

Pipeline 在执行过程中出现两个关键问题：1) 无法在本地文件系统中创建指定文件夹；2) 未能成功初始化 Git 仓库。这两个问题不是孤立的 bug，而是由 Windows 路径处理缺陷、相对路径与绝对路径不一致、subprocess 编码缺失、Git 命令集成方式不当等多个系统性问题叠加导致。需要从根因层面修复，拒绝 ad-hoc patch。

## 业界最佳实践参考

本 spec 的修复方案参考了以下三个业界标杆项目的代码模式：

| 项目 | 核心启示 |
|------|---------|
| **Claude Code** (anthropics/claude-code) | 内部始终使用绝对路径，展示时转相对路径；`execFile` + 参数数组不经 shell；环境变量 `GIT_TERMINAL_PROMPT=0` / `GIT_PAGER=cat` / `LC_ALL=C` 控制 Git 行为；Buffer 延迟解码 + UTF-8 优先 + GBK fallback |
| **OpenCode** (sst/opencode) | Git 操作统一封装为 `GitService`；Git 身份隔离（`GIT_AUTHOR_NAME` 等环境变量）；Patch 应用渐进策略（`--check` → 正常 → `--3way` → `--reject`）；路径安全校验 `SafeJoin` 防遍历 |
| **Codex CLI** (openai/codex) | 所有文件写入通过 `apply-patch` 统一入口；路径边界检查 `isPathInside()`；Windows 长路径前缀 `\\?\` 去除；`shutil.which("git")` 发现 Git 可执行文件 |

## 根因分析

### RC1: Workspace 路径存储使用相对路径，运行时解析不一致（CRITICAL）

- **位置**: `workspace_manager.py:35-36`, `workspace_manager.py:72`
- **症状**: Workspace 创建后，数据库中存储的 `workspace_path` 为相对路径（如 `data\workspaces\ws_xxx`），后续读取该路径时，解析依赖于当前工作目录（CWD）。如果 CWD 发生变化（如从不同目录启动 uvicorn），路径将无法找到
- **根因**: `workspace_root = Path(settings.WORKSPACE_ROOT_PATH)` 使用默认值 `"./data/workspaces"`，这是一个相对路径。`workspace_path = workspace_root / f"ws_{generate_id()[:12]}"` 生成的也是相对路径。`str(workspace_path)` 被存入数据库时没有转换为绝对路径
- **业界对比**: Claude Code 的核心原则是"内部始终使用绝对路径，仅在用户交互时展示相对路径"。Codex CLI 在入口处通过 `path.resolve()` 立即将所有路径转为绝对路径，后续不再依赖 CWD
- **影响**:
  1. 从 `d:\进阶指南\lark-agent\backend` 启动时，workspace 路径为 `data\workspaces\ws_xxx`，可正常工作
  2. 从 `d:\进阶指南\lark-agent` 启动时，同一相对路径指向不同位置
  3. 后台任务（`run_pipeline_stages`）使用独立 session，CWD 可能与 API 请求不同
  4. `patch_applier.py`、`command_runner.py`、`workspace_manager.py` 中的 `get_diff`、`snapshot_workspace` 等函数依赖 `workspace_path`，路径错误时全部失败

**代码证据**:
```python
# workspace_manager.py:32-36
workspace_root = Path(settings.WORKSPACE_ROOT_PATH)  # 相对路径 "./data/workspaces"
workspace_root.mkdir(parents=True, exist_ok=True)
workspace_path = workspace_root / f"ws_{generate_id()[:12]}"
# str(workspace_path) = "data\workspaces\ws_xxx" — 相对路径！

# workspace_manager.py:55-56
workspace = Workspace(
    workspace_path=str(workspace_path),  # 存储相对路径到数据库
)
```

### RC2: Git clone 命令在 Windows 上处理含中文/空格路径失败（CRITICAL）

- **位置**: `workspace_manager.py:38-44`, `workspace_manager.py:75-81`
- **症状**: 当 `source_repo_path` 包含中文字符（如 `d:\进阶指南\lark-agent`）或空格时，`subprocess.run(["git", "clone", str(source_path), str(workspace_path)])` 可能失败
- **根因**:
  1. `subprocess.run` 在 Windows 上使用列表参数时，参数传递给 `CreateProcess` API，路径中的非 ASCII 字符可能被错误编码
  2. 未设置 `encoding` 和 `errors` 参数，默认使用系统编码（Windows 中文版为 GBK），与 Python 内部 UTF-8 字符串不一致
  3. `source_path = Path(source_repo_path).resolve()` 虽然转换为绝对路径，但 `resolve()` 在 Windows 上可能返回长路径前缀（`\\?\`），Git 命令不支持
- **业界对比**: Codex CLI 显式处理 Windows 长路径前缀，去除 `\\?\` 前缀后再传递给 Git 命令。Claude Code 使用 `windowsHide: true` 和 `shell: false` 避免编码问题
- **影响**: 注册中文路径的 Git 仓库时，clone 操作失败，抛出 `ExecutionError: Git clone failed`

**代码证据**:
```python
# workspace_manager.py:38-44
subprocess.run(
    ["git", "clone", str(source_path), str(workspace_path)],
    capture_output=True,
    text=True,       # 使用系统默认编码
    check=True,
    timeout=120,
    # 缺少 encoding="utf-8" 和 errors="replace"
)
```

### RC3: 所有 Git/subprocess 调用缺少统一封装和环境变量控制（CRITICAL）

- **位置**: `workspace_manager.py`, `patch_applier.py`, `command_runner.py`
- **症状**: Git 命令在特定环境下挂起、输出乱码或行为不一致
- **根因**:
  1. 所有 `subprocess.run(["git", ...])` 调用散落在 3 个文件中，无统一封装
  2. 未设置 `GIT_TERMINAL_PROMPT=0`，Git 可能弹出认证提示导致进程挂起（Claude Code 的核心实践）
  3. 未设置 `GIT_PAGER=cat`，Git diff 等命令可能调用 less/more 导致阻塞
  4. 未设置 `LC_ALL=C.UTF-8`，Git 输出编码不可控
  5. 未设置 Git 身份隔离环境变量（`GIT_AUTHOR_NAME` 等），可能污染用户全局配置（OpenCode 的核心实践）
- **业界对比**: 三个项目均采用统一封装模式——Claude Code 封装 `git()` 函数，OpenCode 封装 `GitService`，Codex CLI 封装 `run_git()`。封装层统一处理编码、环境变量、超时、错误
- **影响**: Git 操作行为不可预测，尤其在 CI/CD 或后台任务环境中

### RC4: `create_workspace_for_run` 不预创建目标目录且不验证 Git 可用性（HIGH）

- **位置**: `workspace_manager.py:66-103`
- **症状**: Pipeline 启动时创建运行 workspace 失败，但错误信息不明确
- **根因**:
  1. 与 `register_repo` 不同，`create_workspace_for_run` 不调用 `workspace_root.mkdir(parents=True, exist_ok=True)` 预创建父目录
  2. 不验证 `git` 命令是否可用（`register_repo` 通过 `_validate_git_repo` 间接验证，但 `create_workspace_for_run` 不做任何预检）
  3. `git clone` 的错误输出被截断（`e.stderr`），丢失关键诊断信息
- **影响**: Pipeline 启动时如果 workspace 创建失败，整个 pipeline 卡在 running 状态

### RC5: `_validate_git_repo` 仅检查 `.git` 目录存在，不验证 Git 功能可用性（HIGH）

- **位置**: `workspace_manager.py:17-23`
- **症状**: 路径包含 `.git` 目录但 Git 不可用时，注册成功但后续操作全部失败
- **根因**: `_validate_git_repo` 只检查 `Path(path) / ".git"` 是否存在，不执行 `git rev-parse` 验证 Git 功能
- **业界对比**: Claude Code 使用 `git rev-parse --git-dir` 验证；Codex CLI 使用 `git rev-parse --git-dir` + `isGitRepo()` 函数；OpenCode 使用 `GitService.IsRepo()` 封装
- **影响**: 在无 Git 环境的机器上注册仓库不会报错，但 pipeline 执行时所有 Git 操作失败

### RC6: 路径拼接缺少安全校验，存在路径遍历风险（MEDIUM）

- **位置**: `workspace_manager.py:269`, `patch_applier.py:18-19`
- **症状**: 用户提供的 `file_path` 参数可能包含 `../../` 等路径遍历序列
- **根因**: `read_file_content` 中 `target = ws_path / file_path` 直接拼接，未校验目标路径是否在 workspace 边界内。`patch_applier.py` 中 `target_file = ws_path / file_path` 同样无校验
- **业界对比**: Claude Code 使用 `isWithinWorkspace()` 检查；OpenCode 使用 `SafeJoin()` + 前缀校验；Codex CLI 使用 `isPathInside()` + `path.resolve()` 后前缀比较
- **影响**: 恶意构造的文件路径可能读取或写入 workspace 外的文件

### RC7: Patch 内容未预处理换行符，Windows CRLF 导致 `git apply` 失败（MEDIUM）

- **位置**: `patch_applier.py:25-32`
- **症状**: LLM 生成的 patch 在 Windows 上应用失败
- **根因**: LLM 输出的 patch 内容可能包含 `\r\n`（CRLF）换行符，而 `git apply` 期望统一的 `\n`（LF）换行符。当前代码未对 patch 内容做换行符预处理
- **业界对比**: OpenCode 在 patch 应用前统一换行符：`patch = patch.replace("\r\n", "\n")`
- **影响**: Windows 环境下 patch 应用成功率降低

### RC8: Git 可执行文件硬编码为 `"git"`，未做跨平台发现（MEDIUM）

- **位置**: 所有 `subprocess.run(["git", ...])` 调用
- **症状**: Git 未安装或不在 PATH 时，错误信息不友好
- **根因**: 硬编码 `"git"` 字符串，未使用 `shutil.which("git")` 发现可执行文件路径
- **业界对比**: Codex CLI 使用 `exec.LookPath("git")` + Windows 常见安装路径回退（`C:\Program Files\Git\bin\git.exe` 等）
- **影响**: Git 未安装时无法给出明确安装指引

## What Changes

- 新增 `backend/app/shared/subprocess_utils.py`：统一 Git 命令执行封装和路径工具函数
- 新增 `run_git()` 函数：统一处理编码、环境变量（`GIT_TERMINAL_PROMPT=0` / `GIT_PAGER=cat` / `LC_ALL=C.UTF-8`）、Git 身份隔离、Windows 长路径前缀
- 新增 `normalize_absolute_path()` 函数：将路径规范化为绝对路径，处理 Windows `\\?\` 前缀和驱动器号大小写
- 新增 `safe_join()` 函数：防止路径遍历攻击
- 新增 `find_git()` 函数：跨平台发现 Git 可执行文件
- 将 `workspace_manager.py` 中所有路径存储改为绝对路径
- 将所有 `subprocess.run(["git", ...])` 调用替换为 `run_git()`
- 在 `command_runner.py` 中添加编码处理和环境变量
- 在 `patch_applier.py` 中添加 patch 换行符预处理
- 增强 `_validate_git_repo` 验证 Git 功能可用性
- 在 `create_workspace_for_run` 中添加目录预创建和 Git 可用性预检

## Impact

- Affected specs: Workspace 管理, Artifact 存储, Git 操作, 测试执行
- Affected code:
  - `backend/app/shared/subprocess_utils.py` — **新增**：统一 Git 执行封装和路径工具
  - `backend/app/core/workspace/workspace_manager.py` — 路径绝对化、Git 命令统一封装、安全校验
  - `backend/app/core/workspace/command_runner.py` — 编码处理、环境变量
  - `backend/app/core/workspace/patch_applier.py` — 编码处理、换行符预处理、安全校验
  - `backend/app/core/artifact/artifact_store.py` — 路径绝对化
  - `backend/app/shared/config.py` — 路径默认值绝对化

## ADDED Requirements

### Requirement: 统一 Git 命令执行封装

参考 Claude Code / OpenCode / Codex CLI 的统一封装模式，所有 Git 命令 SHALL 通过 `run_git()` 函数执行。

#### Scenario: Git 命令执行环境隔离
- **WHEN** 任何代码需要执行 Git 命令
- **THEN** 通过 `run_git(args, cwd, timeout)` 统一调用
- **AND** 自动注入环境变量：`GIT_TERMINAL_PROMPT=0`、`GIT_PAGER=cat`、`LC_ALL=C.UTF-8`
- **AND** 自动注入 Git 身份隔离：`GIT_AUTHOR_NAME=devflow`、`GIT_AUTHOR_EMAIL=devflow@bot`、`GIT_COMMITTER_NAME=devflow`、`GIT_COMMITTER_EMAIL=devflow@bot`
- **AND** 显式指定 `encoding="utf-8"` 和 `errors="replace"`

#### Scenario: Git 命令在 Windows 中文路径下执行
- **WHEN** `cwd` 参数包含中文字符
- **THEN** `run_git` 自动去除 Windows 长路径前缀 `\\?\`
- **AND** Git 命令成功执行

### Requirement: 路径工具函数

参考 Codex CLI 的 `normalizePath` 和 OpenCode 的 `SafeJoin`，新增路径工具函数。

#### Scenario: 路径规范化
- **WHEN** 调用 `normalize_absolute_path(Path("./data/workspaces"))`
- **THEN** 返回绝对路径字符串（如 `D:\进阶指南\lark-agent\backend\data\workspaces`）
- **AND** Windows 上去除 `\\?\` 长路径前缀
- **AND** Windows 上统一驱动器号为大写

#### Scenario: 路径安全校验
- **WHEN** 调用 `safe_join(workspace_root, "../../etc/passwd")`
- **THEN** 抛出 `ValueError`，提示路径越界
- **AND** 阻止路径遍历攻击

#### Scenario: Git 可执行文件发现
- **WHEN** 调用 `find_git()`
- **THEN** 返回 Git 可执行文件的绝对路径
- **AND** 如果 Git 不在 PATH 中，检查 Windows 常见安装路径
- **AND** 如果 Git 不可用，抛出 `RuntimeError`

### Requirement: Workspace 路径绝对化

所有存储到数据库的文件系统路径 SHALL 为绝对路径。

#### Scenario: 创建 Workspace 时存储绝对路径
- **WHEN** `register_repo` 或 `create_workspace_for_run` 创建 Workspace 记录
- **THEN** `workspace_path` 和 `source_repo_path` 均通过 `normalize_absolute_path()` 转换为绝对路径后存储
- **AND** 绝对路径不包含 Windows 长路径前缀 `\\?\`

#### Scenario: Artifact 存储路径绝对化
- **WHEN** `artifact_store.py` 保存大文件到文件系统
- **THEN** `storage_uri` 为绝对路径
- **AND** `_get_artifact_dir` 返回绝对路径

### Requirement: Subprocess 编码统一为 UTF-8

所有 `subprocess.run` 调用 SHALL 显式指定 `encoding="utf-8"` 和 `errors="replace"`。

#### Scenario: Git clone 中文路径仓库
- **WHEN** 源仓库路径包含中文字符（如 `d:\进阶指南\lark-agent`）
- **THEN** `git clone` 命令成功执行
- **AND** 错误输出正确解码为 UTF-8

#### Scenario: 测试命令执行
- **WHEN** `command_runner.py` 执行测试命令
- **THEN** stdout 和 stderr 正确解码为 UTF-8
- **AND** 非 UTF-8 字符被替换而非抛出异常
- **AND** 子进程环境包含 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8`

### Requirement: Git 可用性预检

在执行任何 Git 操作前 SHALL 验证 Git 命令可用。

#### Scenario: 注册仓库时 Git 不可用
- **WHEN** 用户尝试注册仓库但系统未安装 Git
- **THEN** 返回 `PrecheckError`，明确提示 "Git is not installed or not in PATH"
- **AND** 错误信息包含安装指引

#### Scenario: Pipeline 启动时 Git 不可用
- **WHEN** Pipeline 需要创建 workspace 但 Git 不可用
- **THEN** Pipeline 创建失败，返回明确错误信息

### Requirement: Workspace 创建预检增强

`create_workspace_for_run` SHALL 在执行 `git clone` 前预创建目标父目录并验证 Git 可用性。

#### Scenario: Workspace 父目录不存在
- **WHEN** `WORKSPACE_ROOT_PATH` 对应的目录不存在
- **THEN** 自动创建该目录（`mkdir(parents=True, exist_ok=True)`）
- **AND** 继续执行 `git clone`

#### Scenario: Git clone 失败
- **WHEN** `git clone` 执行失败
- **THEN** 错误信息包含完整的 stderr 输出
- **AND** 错误信息包含源路径和目标路径

### Requirement: Patch 内容预处理

参考 OpenCode 的换行符统一策略，patch 内容 SHALL 在应用前预处理。

#### Scenario: Patch 包含 CRLF 换行符
- **WHEN** LLM 生成的 patch 内容包含 `\r\n` 换行符
- **THEN** 预处理将 `\r\n` 替换为 `\n`
- **AND** 去除 BOM 标记
- **AND** 预处理后再传递给 `git apply`

### Requirement: 路径安全校验

参考 Claude Code / OpenCode / Codex CLI 的路径边界检查，所有用户提供的文件路径 SHALL 经过安全校验。

#### Scenario: 文件读取路径校验
- **WHEN** `read_file_content(workspace_path, file_path)` 被调用
- **THEN** 校验 `file_path` 解析后的绝对路径在 `workspace_path` 边界内
- **AND** 路径越界时抛出 `ValueError`

#### Scenario: Patch 应用路径校验
- **WHEN** `apply_patch(workspace_path, patch_content, file_path)` 被调用且 `file_path` 不为 None
- **THEN** 校验 `file_path` 解析后的绝对路径在 `workspace_path` 边界内
- **AND** 路径越界时抛出 `ValueError`

### Requirement: 配置路径默认值绝对化

`config.py` 中的路径默认值 SHALL 在运行时解析为绝对路径。

#### Scenario: 使用默认路径配置
- **WHEN** 未设置环境变量，使用默认的 `./data/workspaces` 等路径
- **THEN** 路径在 `ensure_directories` 中被解析为相对于项目根目录的绝对路径
- **AND** 后续所有路径操作基于绝对路径

## MODIFIED Requirements

### Requirement: Workspace 生命周期管理

原要求中 Workspace 路径使用相对路径存储，现修改为：
- 创建 Workspace 时，所有路径通过 `normalize_absolute_path()` 转换为绝对路径后存储
- 读取 Workspace 路径时，直接使用存储的绝对路径，不再依赖 CWD
- 所有 Git 操作通过 `run_git()` 统一封装执行

### Requirement: Git 仓库验证

原要求中仅检查 `.git` 目录存在，现修改为：
- 检查 `.git` 目录存在
- 额外执行 `git rev-parse --git-dir` 验证 Git 功能可用（参考 Claude Code / Codex CLI 模式）
- 验证 Git 命令本身可用（通过 `find_git()` 发现 Git 可执行文件）

### Requirement: Patch 应用策略

原要求中 patch 应用仅尝试 `git apply` → `git apply --3way`，现修改为渐进策略（参考 OpenCode 模式）：
1. 预处理 patch 内容（统一换行符、去除 BOM）
2. 尝试 `git apply --check` dry-run 验证
3. 尝试 `git apply` 正常应用
4. 尝试 `git apply --3way` 三方合并
5. 全部失败则返回详细错误信息

## REMOVED Requirements

无。
