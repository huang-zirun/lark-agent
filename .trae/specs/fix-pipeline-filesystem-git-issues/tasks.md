# Tasks

- [x] Task 1: 新增 `subprocess_utils.py` 统一 Git 执行封装和路径工具（RC1/RC2/RC3/RC6/RC8 基础设施）
  - [x] SubTask 1.1: 新建 `backend/app/shared/subprocess_utils.py`，实现 `run_git(args, cwd, timeout, input)` 函数，参考 Claude Code / Codex CLI 模式：自动注入 `GIT_TERMINAL_PROMPT=0`、`GIT_PAGER=cat`、`LC_ALL=C.UTF-8`、Git 身份隔离环境变量（`GIT_AUTHOR_NAME=devflow` 等），显式 `encoding="utf-8"` 和 `errors="replace"`，Windows 上自动去除 `\\?\` 长路径前缀
  - [x] SubTask 1.2: 实现 `normalize_absolute_path(p: Path) -> str` 函数，参考 Codex CLI 模式：`Path.resolve()` 转绝对路径，Windows 上去除 `\\?\` 前缀，统一驱动器号大写
  - [x] SubTask 1.3: 实现 `safe_join(root: str | Path, user_path: str) -> Path` 函数，参考 OpenCode `SafeJoin` 模式：解析后校验目标路径在 root 边界内，越界抛出 `ValueError`
  - [x] SubTask 1.4: 实现 `find_git() -> str` 函数，参考 Codex CLI 模式：`shutil.which("git")` 优先，Windows 上回退到 `Program Files\Git\bin\git.exe` 等常见路径，不可用时抛出 `RuntimeError`
  - [x] SubTask 1.5: 实现 `normalize_patch_content(content: str) -> str` 函数，参考 OpenCode 模式：去除 BOM、统一 `\r\n` 为 `\n`

- [x] Task 2: 将 Workspace 路径存储改为绝对路径（RC1 核心修复）
  - [x] SubTask 2.1: 在 `workspace_manager.py:register_repo` 中，将 `workspace_path` 和 `source_repo_path` 通过 `normalize_absolute_path()` 转换为绝对路径后再存储
  - [x] SubTask 2.2: 在 `workspace_manager.py:create_workspace_for_run` 中，同样将 `workspace_path` 和 `source_repo_path` 通过 `normalize_absolute_path()` 转换
  - [x] SubTask 2.3: 在 `artifact_store.py:_get_artifact_dir` 中，将 `settings.ARTIFACT_STORAGE_PATH` 通过 `normalize_absolute_path()` 转换为绝对路径
  - [x] SubTask 2.4: 在 `artifact_store.py:save_artifact_file` 中，确保返回的 `storage_uri` 为绝对路径
  - [x] SubTask 2.5: 在 `config.py:ensure_directories` 中，将所有路径通过 `normalize_absolute_path()` 转换为绝对路径后再创建目录

- [x] Task 3: 将所有 `subprocess.run(["git", ...])` 替换为 `run_git()`（RC2/RC3/RC5 修复）
  - [x] SubTask 3.1: 在 `workspace_manager.py` 中，将所有 `subprocess.run(["git", ...])` 调用替换为 `run_git()`，包括 `git clone`、`git rev-parse`、`git diff`、`git add`、`git commit`、`git reset` 等
  - [x] SubTask 3.2: 在 `patch_applier.py` 中，将所有 `subprocess.run(["git", ...])` 调用替换为 `run_git()`，包括 `git apply`、`git rev-parse`、`git diff` 等
  - [x] SubTask 3.3: 在 `command_runner.py` 中，为 `subprocess.run` 添加 `encoding="utf-8"` 和 `errors="replace"`，注入 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8` 环境变量

- [x] Task 4: 增强 Git 可用性预检和仓库验证（RC5/RC8 修复）
  - [x] SubTask 4.1: 修改 `_validate_git_repo` 函数，在检查 `.git` 目录存在后，额外调用 `run_git(["rev-parse", "--git-dir"], cwd=path)` 验证 Git 功能可用（参考 Claude Code / Codex CLI 模式）
  - [x] SubTask 4.2: 在 `register_repo` 开头调用 `find_git()` 验证 Git 可用性，不可用时抛出 `PrecheckError` 并包含安装指引
  - [x] SubTask 4.3: 在 `create_workspace_for_run` 开头同样调用 `find_git()` 验证

- [x] Task 5: 增强 `create_workspace_for_run` 预检和错误处理（RC4 修复）
  - [x] SubTask 5.1: 在 `create_workspace_for_run` 中，执行 `git clone` 前调用 `workspace_root.mkdir(parents=True, exist_ok=True)` 预创建父目录
  - [x] SubTask 5.2: 改进 `git clone` 的错误处理，在 `CalledProcessError` 中包含完整的 stderr 输出、源路径和目标路径信息

- [x] Task 6: 添加路径安全校验（RC6 修复）
  - [x] SubTask 6.1: 在 `workspace_manager.py:read_file_content` 中，使用 `safe_join(ws_path, file_path)` 替代直接拼接 `ws_path / file_path`
  - [x] SubTask 6.2: 在 `patch_applier.py:apply_patch` 中，当 `file_path` 不为 None 时，使用 `safe_join(ws_path, file_path)` 替代直接拼接

- [x] Task 7: 改进 Patch 应用策略（RC7 修复 + OpenCode 渐进策略）
  - [x] SubTask 7.1: 在 `patch_applier.py:apply_patch` 中，对 `patch_content` 调用 `normalize_patch_content()` 预处理（统一换行符、去除 BOM）
  - [x] SubTask 7.2: 在 `git apply` 前添加 `git apply --check` dry-run 验证步骤（参考 OpenCode 渐进策略）
  - [x] SubTask 7.3: 重构 patch 应用流程为：预处理 → `--check` dry-run → 正常 `git apply` → `--3way` → 返回详细错误信息

- [x] Task 8: 端到端验证——测试文件系统操作和 Git 仓库初始化
  - [x] SubTask 8.1: 编写测试脚本，验证注册中文路径 Git 仓库成功，且数据库中存储的路径为绝对路径（无 `\\?\` 前缀）
  - [x] SubTask 8.2: 验证 Pipeline 启动后 workspace 正确创建，`git clone` 成功
  - [x] SubTask 8.3: 验证 artifact 存储路径为绝对路径，大文件保存和读取正常
  - [x] SubTask 8.4: 验证 Git 不可用时，`register_repo` 返回明确的 `PrecheckError` 且包含安装指引
  - [x] SubTask 8.5: 验证从不同工作目录启动服务时，workspace 路径仍能正确解析
  - [x] SubTask 8.6: 验证 `safe_join` 阻止路径遍历攻击（如 `../../etc/passwd`）
  - [x] SubTask 8.7: 验证 patch 内容包含 CRLF 时，预处理后 `git apply` 成功
  - [x] SubTask 8.8: 验证 `run_git()` 自动注入的环境变量生效（`GIT_TERMINAL_PROMPT=0` 等）

# Task Dependencies

- [Task 2] depends on [Task 1]（路径工具函数先建立，路径绝对化才能正确引用）
- [Task 3] depends on [Task 1]（`run_git()` 先实现，才能替换所有 subprocess 调用）
- [Task 4] depends on [Task 1]（`find_git()` 和 `run_git()` 先实现）
- [Task 5] depends on [Task 1] + [Task 4]（预检需要 `find_git()` 和路径工具）
- [Task 6] depends on [Task 1]（`safe_join()` 先实现）
- [Task 7] depends on [Task 1] + [Task 3]（`normalize_patch_content()` 和 `run_git()` 先实现）
- [Task 8] depends on [Task 1-7]（验证需要所有修复完成）
