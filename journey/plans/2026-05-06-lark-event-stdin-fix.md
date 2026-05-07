# 修复 Lark 消息接收中断

## 目标

修复 `devflow start` 无法持续接收飞书消息的问题。根因是 `lark-cli event consume` 子进程继承了已关闭的 stdin，在 ready 前主动退出，且后台消费线程异常没有传回主线程。

## 实施步骤

1. 为 `lark-cli` 事件流新增回归测试：保持 stdin 打开、UTF-8 replace 解码、ready 前退出报错、Windows npm 全局真实布局解析原生 exe。
2. 为 `MessageBuffer` 和 `UserMessageQueue` 新增异常传播测试，避免后台线程失败时主流程静默结束。
3. 最小修改 `devflow/intake/lark_cli.py`、`devflow/message_buffer.py`、`devflow/message_queue.py`。
4. 运行指定单元测试和真实 bounded event consume 烟测。

## 验收

- `devflow start` 的事件消费进程不再因 stdin EOF 在 ready 前退出。
- ready 前失败会抛出带 stderr 诊断的 `LarkCliError`。
- 后台线程异常会传回调用方。
- 不改消息协议、路由、session 逻辑。
