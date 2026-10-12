# 模型连接测试第二轮只读诊断

日期：2026-10-12（Asia/Shanghai）。仅查看现有文件与已安装 SDK 源码；没有启动服务、发起模型请求或修改配置、业务代码及 Git。

## 结论与证据边界

最新一次独立实例复验（09:18）中，浏览器收到本地 `POST /api/model/test` **HTTP 200**，页面显示应用层失败、模型 `deepseek-flash`、耗时 **1.955s**，提示“接口未返回正常结束的非空文本响应”。这一提示由当前代码的 `UNEXPECTED_RESPONSE` 分支返回；最新验收没有单独持久保存完整接口 JSON。本地 HTTP 200 **不是**上游模型 HTTP 状态。该分支只有在 Agent 返回后，最终消息不是非空字符串，或 SDK 观察到的结束原因不是 `stop` 时才会触发（`backend/app/main.py:390-394`）。本次没有 Live 任务或报告。

**最深可确认的根因是用户连接测试的应用层响应判定未满足，而非已证实的协议错误或网络故障。** 最新复验没有保存上游 HTTP 状态、原始 `finish_reason`、`choices` 数量或模型消息的字段存在性；接口也没有回传这些字段。不能把旧轮次的响应元数据用于断言此次上游也返回了 `200/stop`，更不能唯一确定是空正文、非 `stop` 还是消息转换。

现有 `/tmp/sentinelai-release-verification-http.jsonl` 与 `*-ui-complete.json` 修改时间均为 **08:30**，对应**此前**的精确 OK 校验失败：脱敏记录显示上游 HTTP 200、模型 `deepseek-flash`、`finish_reason=stop`、输入 36 / 输出 35 tokens，其中推理 33 tokens。该元数据文件只含状态、模型、用量和结束原因，**没有保存** `choices`、`output`、`content`、`text` 或回复正文；旧 UI 文件只含渲染后的失败提示。09:18 的新复验没有对应的上游结构快照。因此上述字段在**日志中缺失**，不能推论在实际响应中不存在。此次未读取或保存完整模型回复。

## 协议及解析路径

- 项目 `ModelConfig.client()` 构造 `OpenAIChatCompletionClient`（`backend/app/config.py:117-125`）。连接测试和五阶段 Live 共用此客户端；安装的 AutoGen SDK 在没有结构化 response format 时调用 `chat.completions.create(..., stream=False)`，而非 `responses.create`。连接测试没有传结构化输出类型；`scripts/deepseek.sh probe` 也是单独向 `/chat/completions` 发送请求。历史启动记录中的服务来源协议标记不代表该项目实际改走 Responses API。
- SDK 从 `result.choices[0].message.content` 生成 `CreateResult.content`；可选的 `message.reasoning_content` 放在单独的 `thought`，不会自动成为可见正文；`choice.finish_reason` 被规范化后由 `CompletionObserver` 保留。AutoGen `AssistantAgent` 再把字符串正文封装为最终 `TextMessage.content`。连接测试读取最后一条消息的 `content` 并要求非空且 `finish_reason == 'stop'`（`backend/app/main.py:388-394`）。当前解析**匹配 Chat Completions 的常规 `choices[].message.content` 路径**，没有证据证明模型实际改用顶层 `output`/`text` 或发生了协议不匹配。
- 两条路径的重要差别：连接测试强制 `max_output_tokens=64`、SDK 自动重试 0，发短任务；既有成功 Live 的工作流使用同一客户端，但本地输出上限为 `null`，用各阶段提示与独立阶段时限，并对最后一条消息运行结构化校验（`backend/app/engine.py:151-166`）。已有成功黑盒记录的五阶段分别得到上游 HTTP 200、`stop`、有效结构化输出，生成了报告；它们不是本次连接测试的响应样本。旧连接测试 35 个输出 tokens 中有 33 个推理 tokens，说明短测试的可见文本可能很少，但**不能据此确认** 09:18 的正文为空或 64-token 上限造成截断。

## 最小修复建议（本轮未实施）

先不要猜测响应字段或直接放宽成功条件。获得下一次受控诊断授权后，仅对**一次**连接请求记录不可逆的脱敏结构指标：上游状态、响应模型、`choices` 数量、原始及 SDK 规范化的 `finish_reason`，以及 `message.content`、`message.reasoning_content`、SDK `CreateResult.content`、Agent 最终消息的**类型、是否存在、字符数/是否仅空白**；如确实为 Responses 格式，再仅记录 `output`/`text` 的存在性和类型。不要记录原文、请求正文、Key 或认证头。随后针对**证实的条件**做局部修复：若 `stop` 但可见正文为空，检查连接测试独有的 64-token 上限与推理用量；若字段结构不同，再确认实际协议与 SDK 映射。保留独立严格 marker 探针、Live Schema 与失败门禁，不把单纯本地 HTTP 200 当作连接成功。
