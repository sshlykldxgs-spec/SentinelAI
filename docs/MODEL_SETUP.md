# 模型配置与在线验收

代码支持 AutoGen 0.7.5 的 OpenAI-compatible Chat Completions。没有接入其它协议，没有自动转换 Anthropic/Gemini 原生请求。兼容服务必须支持标准 messages/chat completions；JSON 由 schema 提示 + Pydantic 校验，不强制服务实现 JSON Schema mode。

默认配置来自进程环境变量、根目录 `.env` 或 `backend/.env`；环境变量优先，加载不覆盖已有设置。只提交 `backend/.env.example`，不要提交 `.env` 或真实密钥。评委不需要 CC Switch，也不需要在线演示链接；项目可从仓库在本地启动。

## 工作台模型配置入口

首页顶部「模型配置」和首次未配置提示直接进入设置表单。支持OpenAI Compatible、API Base URL、密码输入的API Key、Model Name和可选输出Token。缺少配置时，Live启动提示“请先完成模型配置”并跳转，不提交失败任务、不自动切换Demo。

UI保存仅在本机后端进程内存中临时覆盖模型/地址/凭据/输出上限，不修改环境变量、.env、超时、重试或审批策略。刷新可继续使用，密码框清空，服务不回传Key，浏览器不保存到localStorage/sessionStorage；后端重启后回到环境配置。更换Base URL必须重新输入Key，禁止自动把已有环境凭据转发到另一个地址。执行任务时禁止更改配置。该本机单用户流程不提供生产多租户、SSO或持久化保险库。

点击「测试连接」先保存该配置，再发一次最大64输出tokens的最小请求，SDK重试关闭；仅在返回非空文本且finish_reason=stop时视为连接成功，不要求精确匹配提示中的OK。连接结果只显示模型、耗时及不含回复正文的摘要。内部`sh scripts/deepseek.sh probe`仍独立使用严格标记。保存本身零模型调用。认证错误、网络、模型/路径不存在等按类别显示；404无法总是可靠区分模型名称与Base URL错误，不伪造更细判定。测试失败不隐式降级；连接成功不等于五阶段结构化工作流已验收。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| OPENAI_API_KEY | 空 | 仅服务端，缺失/已知占位值阻止 live |
| OPENAI_MODEL | gpt-4o-mini | 模型名称；DeepSeek 示例采用 `deepseek-chat`，以服务实际支持为准 |
| OPENAI_BASE_URL | https://api.openai.com/v1 | Chat Completions API 根地址；DeepSeek 示例采用 `https://api.deepseek.com/v1`，无账号/密码/查询参数 |
| MODEL_TIMEOUT_SECONDS | 45 | 兼容旧配置；显式设置时为尚未独立配置的阶段提供回退值，1–120 秒 |
| PLANNER_TIMEOUT_SECONDS | 60 | 仅 Planner 的 SDK 请求与 Agent.run 超时，1–120 秒 |
| RESEARCH_TIMEOUT_SECONDS | 120 | 仅 Research 的 SDK 请求与 Agent.run 超时，1–120 秒 |
| ANALYST_TIMEOUT_SECONDS | 90 | 仅 Analyst 的 SDK 请求与 Agent.run 超时，1–120 秒 |
| REVIEWER_TIMEOUT_SECONDS | 120 | 仅 Risk Reviewer 的 SDK 请求与 Agent.run 超时，1–120 秒 |
| ACTION_TIMEOUT_SECONDS | 120 | 仅 Action 的 SDK 请求与 Agent.run 超时，1–120 秒 |
| MODEL_MAX_RETRIES | 1 | 执行器最多一次结构化输出修正；SDK恢复关闭时也允许timeout/connection/429/502/503/504恢复 |
| MODEL_SDK_MAX_RETRIES | 跟随 MODEL_MAX_RETRIES | SDK传输层最多一次重试（0–1）；显式0关闭，未设置且MODEL_MAX_RETRIES=0时也关闭 |
| MODEL_MAX_OUTPUT_TOKENS | 0 | 0 表示不发送 max_tokens；正整数显式限制单次输出，不再钳制到 4096 |
| TASK_TIMEOUT_SECONDS | 300 | 任务总时间，5–600 秒 |
| TASK_TOKEN_BUDGET | 0 | 0 关闭本地任务 token 预算；正整数启用预算，不再钳制到 300000 |

未知服务可能不返回 token 用量，页面显示“未提供”。默认解除项目本地 token 限制；模型服务自身的默认输出上限、上下文窗口和账户限制仍有效，不能保证不截断。已有环境变量或真实 .env 若显式设置了正整数，会继续生效，不被程序覆盖；需要关闭时在自己的启动环境中将这两项设为 0。未设置输出上限时预算预留只估算输入，不能当作下一次完整请求的严格费用上限。仍保留超时、有限重试、失败终止及结构校验。连接配置完整不代表凭据已由服务验证。

各阶段独立配置优先；若未设置该阶段变量，显式旧 MODEL_TIMEOUT_SECONDS 次之；否则使用表中阶段默认值。任务总时限仍为300秒（覆盖所有阶段、恢复等待与请求），并不自动扩展到各阶段超时总和。

SDK重试已恢复，最多一次，遵循安装的OpenAI SDK传输策略（连接/超时、408/409/429/5xx及服务方显式重试指示），包括限流等待。SDK启用时，传输类异常返回执行器后不再继续同类重试；外层阶段超时仍可能在SDK完成恢复前中断请求。执行器只对JSON/Schema/阶段必填输出错误追加不含原始内容的修正要求，等待1秒后最多一次新模型调用，不放松校验。截断length、非文本/过滤或工具完成原因、认证、参数错误和业务needs_evidence不通过执行器重复调用追求成功。

默认SDK=1、执行器=1时，一个阶段最多2次逻辑调用，每次SDK最多2次底层请求，最坏**4次底层请求/阶段、20次/五阶段**；这是上限，不是每次都会调用20次。首次成功或失败不可恢复时更早停止，时间/预算门禁也可截断。关闭两层用MODEL_MAX_RETRIES=0和MODEL_SDK_MAX_RETRIES=0（如果后者未显式设置，也会跟随前者关闭）。仅开启一层的上限为2次/阶段。

恢复历史中的attempts记录执行器逻辑调用，**不是SDK内HTTP次数**；真实验收计数需要传输观察器。SDK内部退避不一定显示agent.retrying事件，界面恢复次数只表示执行器恢复。重试可能重复计费；Action只生成建议、不执行外部操作，最终有效结果仍进入人工审批。

## 评委使用自己的 DeepSeek 密钥

从仓库根目录执行 `cp backend/.env.example backend/.env`，只在本机将 `backend/.env` 的 `OPENAI_API_KEY` 占位符替换为自己的密钥；确认模型和地址与自己的服务一致。也可仅在启动后端的终端设置相同的环境变量，不建立 `.env`。此项目的客户端需要 OpenAI-compatible **Chat Completions**；CC Switch 条目的 `responses` 标注不应被当成项目已支持的协议。不要在 Git、报告、前端或截图中包含密钥。

完全离线的评委仍可选 Demo 或 Replay，且不会调用模型。未配置密钥时后端拒绝 `mode=live`，不会默默改为 Demo。

## 主动连接测试

在本机安全配置凭据后重启后端，打开「配置」页面；确认配置完整，再点击「测试模型连接（消耗额度）」。该操作建立短期本机审批会话，并显式执行一次极短在线请求。启动、健康检查、构建和离线测试不调用在线服务。

## 真实端到端验收

1. 用户安全配置正确凭据，重启后端（不要在聊天中粘贴密钥）。
2. 配置页主动测试连接；失败会显示认证/限流/服务/超时等分类。
3. 总览保留示例资料（明确标记为演示数据），选择 Live，点击启动。
4. 工作流确认模型 ID、五个真实 Agent 阶段、请求次数、时间、可获得用量及 SSE 事件。
5. 检查证据、风险审查、行动审批和报告的 live 标识；在线请求失败必须显示 failed，无 demo 回退。
6. 记录任务 ID、模式、模型、结果和可获得用量；不要记录凭据。

**本地既有 CC Switch Deepseek 配置已通过一次最小真实调用验证**：HTTP 200，响应模型 `deepseek-flash`，标记精确匹配。随后完整 Live 工作流在 Planner 输出结构校验处失败，后续四个 Agent 未执行；没有完整 Live 报告。详见 [DEEPSEEK_ACCEPTANCE.md](DEEPSEEK_ACCEPTANCE.md)。评委自行配置的 `deepseek-chat` 和各自凭据仍需独立验证。Replay 和 mocked 测试不等于真实模型验收；不得宣称完整 Live 工作流已经通过。
