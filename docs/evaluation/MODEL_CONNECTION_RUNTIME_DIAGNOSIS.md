# 模型连接测试运行时脱敏诊断

日期：2026-10-12（Asia/Shanghai）。本轮只为定位连接测试条件增加脱敏诊断。未修改成功判定、模型、协议、Agent、Prompt、Schema、Live、timeout/retry 或 Git；未保存认证信息、请求正文、模型原文或用户输入。

## 诊断范围

- 仅在 `POST /api/model/test` 使用的独立客户端挂载响应观察钩子；其他 Live 请求和内部严格 marker 探针不受影响。
- 接口响应新增 `diagnostic`：上游 HTTP 状态、**白名单**顶层字段名及其他字段数量、`choices` 数量、首个 choice 的白名单字段名及其他字段数量、枚举化的原始 `finish_reason`、`message`/`content` 是否存在、字符串 `content` 长度、解析后文本是否为空，以及 SDK 规范化的完成原因。未知字段名及未知结束原因不回显。该对象不包含响应正文或请求内容。
- 成功条件依旧是最后一条 Agent 消息为非空字符串且 SDK `finish_reason == 'stop'`；请求输出上限64、SDK重试0等既有测试参数均未改变。`diagnostic` 同时随成功、失败或捕获的异常响应返回供受控诊断，不写文件日志。

## 实际验证

- 后端离线测试：`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -q`，**102/102 通过**。包括实际 SDK MockTransport 的钩子验证、失败分支与未知字段脱敏验证；未连接真实模型。
- 新建独立18000实例加载当前代码，原8000服务不变。通过5173页面进入模型配置，复用现有 `deepseek-flash` 和原Base URL/进程凭据，点击一次「测试连接」。只有**1次**页面测试接口请求，没有运行 Live、探针或第二次真实连接请求。操作后独立实例已停止。

| 观察字段 | 本次脱敏值 |
| --- | --- |
| 本地接口 / 上游 HTTP | 200 / 200 |
| 本地接口 `ok` | `true` |
| 响应模型 | `deepseek-flash` |
| 顶层字段名 | `choices`, `created`, `id`, `model`, `object`, `system_fingerprint`, `usage`；其他字段数 0 |
| `choices` | 1 项 |
| 首个 choice 字段名 | `finish_reason`, `index`, `logprobs`, `message`；其他字段数 0 |
| 原始 / SDK结束原因 | `stop` / `stop` |
| `message` / `content` | 均存在 |
| `content` 字符长度 | 2；未保存文本本身 |
| Agent解析后文本为空 | 否 |
| API Key输入框 | 请求后为空 |

## 结论和边界

本次单次连接测试正常完成，**09:18那次 `ok=false` 未复现**；没有同一时刻的旧请求底层结构记录，因此不能反推此前具体失败原因，也不能由本次成功声称 Final Release Verification 或五阶段 Live 已通过。没有为追求旧错误重试、修改判定或放宽校验。到此停止，不自动修复。
