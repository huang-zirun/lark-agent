# DevFlow 配置参数说明

将 `config.example.json` 复制为 `config.json`（已加入 `.gitignore`），然后按以下说明填写各参数。

---

## 1. `llm` — LLM 服务配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `provider` | string | `"ark"` | 是 | LLM 服务提供商标识 |
| `api_key` | string | `""` | 是 | API 认证密钥 |
| `model` | string | `""` | 是 | 模型名称或推理接入点 ID |
| `base_url` | string | `""` | 否 | 自定义 API 基础 URL |
| `temperature` | number | `0.2` | 否 | 生成温度，越低越确定 |
| `max_tokens` | number | `2000` | 否 | 单次响应最大 token 数 |
| `timeout_seconds` | number | `120` | 否 | HTTP 请求超时秒数 |
| `response_format_json` | boolean | `false` | 否 | 是否要求返回 JSON 格式 |

### `provider` — 服务提供商

决定请求的默认 base_url，可选值：

| 值 | 平台 | 内置 URL |
|---|---|---|
| `ark` | 火山方舟 | `https://ark.cn-beijing.volces.com/api/v3` |
| `bailian` | 阿里百炼 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `deepseek` | DeepSeek | `https://api.deepseek.com` |
| `longcat` | LongCat | `https://api.longcat.chat/openai` |
| `mimo` | MiMo | `https://api.xiaomimimo.com/v1` |
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `custom` | 自定义 | 无（必须填写 `base_url`） |

**覆盖优先级**：CLI 参数 `--provider` > 环境变量 `DEVFLOW_PROVIDER_OVERRIDE` > 配置文件

### `api_key` — 如何获取

- **火山方舟**：登录 [火山方舟控制台](https://console.volcengine.com/ark)，创建推理接入点后获取 API Key
- **DeepSeek**：登录 [DeepSeek 平台](https://platform.deepseek.com)，在 API Keys 页面创建
- **LongCat**：登录 [LongCat 开放平台](https://longcat.chat/platform/)，注册后在 API Keys 页面获取
- **OpenAI**：登录 [OpenAI 平台](https://platform.openai.com)，在 API Keys 页面创建
- **阿里百炼**：登录 [百炼控制台](https://bailian.console.aliyun.com)，获取 API Key

> ⚠️ 安全提醒：`api_key` 不会出现在错误日志中（自动替换为 `[REDACTED]`），但仍需注意不要提交到版本控制。

### `model` — 如何填写

| 平台 | 填写方式 | 示例 |
|---|---|---|
| 火山方舟 | 推理接入点 ID | `ep-202xxxxx-xxxxx` |
| DeepSeek | 模型名称 | `deepseek-chat` |
| LongCat | 模型名称 | `longcat-chat` |
| OpenAI | 模型名称 | `gpt-4o` |

### `base_url` — 何时需要

- `provider` 为 `custom` 时**必填**
- 其他 provider 通常留空即可（自动使用内置 URL）
- 如果填写了非空值，会**优先使用**该值，忽略 provider 对应的内置 URL

---

## 2. `lark` — 飞书应用配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `cli_version` | string | `"1.0.23"` | 是 | lark-cli 锁定版本号 |
| `app_id` | string | `""` | 是 | 飞书应用 App ID |
| `app_secret` | string | `""` | 是 | 飞书应用 App Secret |
| `test_doc` | string | `""` | 否 | 测试用飞书文档 token |
| `prd_folder_token` | string | `""` | 否 | PRD 文档存放文件夹 token |

### `cli_version` — 锁定版本

当前硬锁定为 `1.0.23`，**不可更改**。配置其他值会直接报错。系统启动时会校验本地安装的 lark-cli 版本是否匹配。

### `app_id` / `app_secret` — 如何获取

1. 登录 [飞书开放平台](https://open.feishu.cn)
2. 创建「企业自建应用」
3. 在应用的 **凭证与基础信息** 页面获取 `App ID` 和 `App Secret`

> ⚠️ `app_secret` 不会出现在错误日志中，但仍需注意保密。

### `test_doc` — 如何获取

1. 打开任意飞书文档
2. 从浏览器地址栏提取文档 token

URL 格式与 token 位置：

| URL 格式 | token 示例 |
|---|---|
| `https://xxx.feishu.cn/docx/DOCNXXXXXXX` | `DOCNXXXXXXX` |
| `https://xxx.feishu.cn/wiki/WIKIXXXXXXX` | `WIKIXXXXXXX` |

> 确保机器人应用有该文档的**读取权限**。

### `prd_folder_token` — 如何获取

1. 在飞书云空间中创建一个文件夹（如"PRD 文档"）
2. 从浏览器地址栏提取文件夹 token

URL 格式：`https://xxx.feishu.cn/drive/folder/FOLXXXXXXXX`，其中 `FOLXXXXXXXX` 即为 token。

> 确保机器人应用有该文件夹的**写入权限**。留空则文档创建在云空间根目录。

---

## 3. `workspace` — 工作区配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `root` | string | `""` | 是 | 工作区根目录绝对路径 |
| `default_repo` | string | `""` | 否 | 默认仓库路径 |

### `root` — 工作区根目录

所有项目创建和仓库访问的**安全边界**。新建项目会在该目录下创建子目录；已有仓库路径如果不是绝对路径，会相对于此目录解析。所有仓库路径必须位于 `root` 内部，否则会抛出安全错误。

**填写示例**：`D:\projects` 或 `/home/user/workspace`

### `default_repo` — 默认仓库

当用户在机器人消息中未指定仓库且未新建项目时，自动使用此路径。

**填写示例**：`D:\lark`。该路径必须位于 `workspace.root` 内（如果 `root` 已配置）。

---

## 4. `approval` — 飞书审批配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `enabled` | boolean | `false` | 否 | 是否启用飞书审批集成 |
| `definition_code` | string | `""` | 否 | 审批定义 code |
| `poll_interval_seconds` | number | `60` | 否 | 审批状态轮询间隔（秒） |

### `enabled` — 是否启用

启用后，方案评审和代码评审的检查点会自动创建飞书三方审批实例，用户可在飞书审批 App 中操作。未启用时，回退到 Bot 消息命令方式（`Approve/Reject <run_id>`）。

> 需要飞书应用有审批相关 API 权限。

### `definition_code` — 审批定义

通常**留空**即可，系统会自动创建三方审批定义。如需复用已有审批定义，可从飞书审批管理后台获取其 `approval_code` 填入。

### `poll_interval_seconds` — 轮询间隔

预留参数，当前版本中未直接使用。保持默认值即可。

---

## 5. `semantic` — 语义索引配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `enabled` | boolean | `true` | 否 | 是否启用 AST 语义索引 |
| `max_workers` | number | `4` | 否 | 并发解析最大线程数 |
| `parse_timeout_seconds` | number | `10` | 否 | 单文件解析超时（秒） |
| `max_symbols_per_file` | number | `500` | 否 | 单文件最大符号数 |
| `index_dir_name` | string | `".devflow-index"` | 否 | 索引存储目录名 |

### `enabled` — 是否启用

启用后，方案设计阶段会自动构建代码库的语义索引，提供符号搜索、引用追踪、调用链查询等能力。如果不需要（如纯前端项目或小型项目），可设为 `false` 以加快速度。

### `max_workers` — 并发线程数

根据机器 CPU 核心数调整，一般 2-8 即可。文件数少于 10 时不会启用并发。

### `parse_timeout_seconds` — 解析超时

单文件解析的超时时间。大型文件可能需要适当增加。

### `max_symbols_per_file` — 符号数上限

防止单个大文件消耗过多资源。

### `index_dir_name` — 索引目录

相对于工作区根目录，索引文件存储在 `{workspace_root}/{index_dir_name}/` 下，包含 `symbols.json`、`relations.json`、`file_meta.json`、`summary.json`。

> 建议将该目录加入 `.gitignore`。

---

## 6. `interaction` — 交互配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `default_chat_id` | string | `""` | 否 | 默认飞书群聊 ID |
| `max_queue_size` | number | `5` | 否 | 每用户消息队列最大容量 |
| `message_merge_window_seconds` | number | `5` | 否 | 消息合并窗口（秒） |
| `progress_notifications_enabled` | boolean | `true` | 否 | 是否启用阶段进度通知 |

### `default_chat_id` — 如何获取

1. 在飞书中打开目标群聊
2. 进入群设置，获取群 ID（格式为 `oc_xxxxxxx`）
3. 也可通过 lark-cli 的 API 查询

配置后，`devflow start` 启动时会向该群发送欢迎消息；未配置则在控制台打印指引。

### `max_queue_size` — 队列容量

队列满时新消息会被丢弃并通知用户。根据并发需求调整，一般 3-10 即可。

### `message_merge_window_seconds` — 合并窗口

在窗口期内收到的同一用户连续消息会合并为一条需求。如果用户经常分段发送长需求，可适当增大。

### `progress_notifications_enabled` — 进度通知

启用后，每个 Pipeline 阶段开始/完成/失败时会发送 Bot 消息通知，LLM 思考时也会发送"正在思考"提示。如果觉得通知过多，可设为 `false`。

---

## 7. `reference` — 参考文档配置

| 参数 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---|---|---|
| `enabled` | boolean | `true` | 否 | 是否启用参考文档注入 |
| `max_chars_per_stage` | number | `4000` | 否 | 每阶段注入参考文档最大总字符数 |
| `max_chars_per_document` | number | `2000` | 否 | 单个参考文档最大字符数 |

### `enabled` — 是否启用

启用后，Agent 在各阶段会自动注入行业标准的参考文档（如 EARS 语法、ADR 模板、NFR 检查清单等）到 prompt 中。参考文档存放在 `devflow/references/` 目录下的 `.md` 文件中。

### `max_chars_per_stage` — 阶段字符上限

每个 Pipeline 阶段注入参考文档的总字符数上限，超出部分按优先级截断。值越大注入越多，但占用更多 token 预算。根据 LLM 的上下文窗口大小调整。

### `max_chars_per_document` — 文档字符上限

单个参考文档的截断长度。如需更完整的参考内容，可适当增大。

---

## 配置加载流程

1. 将 `config.example.json` 复制为 `config.json`
2. 系统通过 `devflow/config.py` 中的 `load_config()` 读取并解析为不可变数据类
3. 各模块通过 `require_*` 参数声明必填字段（如 `require_llm_api_key`、`require_lark_credentials`）
4. `lark.cli_version` 硬锁定为 `1.0.23`，配置其他值会直接报错
5. `llm.provider` 支持运行时通过 `--provider` CLI 参数或 `DEVFLOW_PROVIDER_OVERRIDE` 环境变量覆盖
6. 所有敏感字段（`api_key`、`app_secret`）不会出现在错误信息中
