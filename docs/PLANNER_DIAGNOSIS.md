# Planner 失败诊断与最小修复

日期：2026-10-12。只使用既有脱敏记录、已安装 SDK 源码和离线模拟。本轮真实模型调用次数为 0，没有修改密钥、模型名称、超时或输出预算，没有初始化 Git、提交、推送或操作用户审批历史。

## 原在线失败能确认到什么程度

已有记录确认 Planner 调用一次，返回用量 prompt=3499 / completion=1800，之后错误分类 INVALID_OUTPUT，mode=live、任务 failed、报告为空，后续 Agent 未运行。没有保存原始文本、具体校验错误或 finish_reason，故**不能唯一确定原在线失败属于 JSON 语法、字段类型、必填条件或截断中的哪一类**。

completion 恰好等于输出上限 1800，加上基础调用显示该模型会计入推理 tokens，是截断的间接证据，不能当成截断已确认。此次未增加 token 上限、未禁用推理、未再请求在线模型。

## 已复现问题与证据

| 类别 | 只读诊断 / 离线证据 | 判断 |
| --- | --- | --- |
| 非纯 JSON | 旧代码直接 `StageOutput.model_validate_json(raw)`；一个完整合法 JSON 加单一代码围栏会产生 json_invalid | 已复现兼容性问题，但不证明原响应含围栏 |
| Prompt/Schema 不一致 | 旧 Planner Schema 只要求 summary，acceptance_conditions 默认空；执行器另要求非空 | 已确认契约表达缺口；模型合法遵守 Schema 仍可在执行器失败 |
| 类型/字段错误 | 模拟 summary 数值或 conditions 字符串会产生 string_type/list_type | 校验正常，应拒绝，不放宽 |
| 截断 | 模拟未闭合 JSON 会产生 json_invalid；原记录没有 finish_reason | 可能但未确认，必须明确检测，不修补尾括号 |
| AutoGen 文本处理 | 已安装 AgentChat 0.7.5 在无工具/无 StructuredMessage 配置时最后生成 TextMessage；字符串内容用于解析符合该路径 | 未发现此文本路径自身错误；原客户端把非文本强制 str 缺少类型诊断 |
| 响应观察缺失 | 旧脚本观察 httpx，而安装的 OpenAI SDK 使用 httpx2；AgentChat TextMessage 不保留完整模型响应 finish_reason | 已确认诊断盲区，不是证明没有在线请求 |

## 最小改动文件

- `backend/app/output_validation.py`：单一完整 JSON 围栏解包、整段 JSON 解析、重复字段/非有限数字/非对象拒绝、原 Schema 校验、非空 Planner 条件检查。新增安全 OutputValidationError 和 CompletionObserver，后者只记录枚举化 finish_reason，不保留 content/thought 或请求。
- `backend/app/engine.py`：Planner 专属 Schema 强制至少一条验收条件；说明当前角色范围、避免生成下游内容；使用解析 helper，保持原 Research/Analyst/Reviewer/Action 校验。记录响应完成原因，不从 token 数猜测截断。
- `backend/app/workflow.py`：Planner Prompt 明确给出 summary/非空 acceptance_conditions，避免复制 Schema。
- `backend/app/config.py`：保留顶层 INVALID_OUTPUT 分类和有限重试策略，新增安全 reason/schema_issues；仅记录已知字段路径与错误类型，未知字段名遮蔽，绝不返回 Pydantic 输入/原始异常文本。
- `scripts/deepseek.sh`：验收观察器适配安装 SDK 的 httpx2/httpx transport，并输出阶段安全完成元数据。本轮只编译/语法检查，没有执行脚本或验证新的在线观察路径。
- `backend/tests/test_output_validation.py`：新增 12 个离线测试。原有 31 项断言未修改或削弱。
- 本报告和 `docs/TEST_RESULTS.md`：记录真实回归结果。

不会从带说明的回答中搜索 JSON 片段，不接受多个对象或多个围栏，不自动补齐截断，不伪造验收条件，不跳过 Reviewer。finish_reason=length 即使文本看似完整也拒绝。Demo/Replay/live 模式和审批边界不变。

## 实际回归结果

- `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`：**43/43 通过，7.432 秒**，原有 31 项全部通过。
- frontend 中 `npm run build`：**通过，1743 modules，1.39 秒**。
- `sh -n scripts/deepseek.sh` 与脚本内 Python compile：通过，没有执行在线请求。
- 纯 JSON / 完整单一围栏合法输出通过；缺字段、错误类型、未知字段、空条件、重复字段、非有限值、非文本、说明文字、多个对象和截断输出均明确拒绝。
- 实际 AssistantAgent + Replay 消息路径中，合法围栏 Planner 继续五阶段、Reviewer 执行并传递 human_review 至 Action，报告生成且任务 waiting_approval；这是离线模拟，不是在线 Live 成功。
- 模拟 finish_reason=length：Planner failed，下游 queued，保持 mode=live，task.failed，无报告。非法 JSON 的错误记录不含模拟输入内容。

## 一次受控真实验收的条件与预算

已具备**发起一次受控尝试所需的离线回归及诊断条件**，不代表能保证在线成功。原失败的精确原因仍未证实。新 HTTP 观察路径尚未在线验证，需在下一次尝试中确认。

建议先确认安全配置仍有效，再在独立进程使用 Demo 资料执行一次完整 Live，关闭应用与 SDK 自动重试，不改持久配置，不修改审批历史。预计依次调用 Planner、Research、Analyst、Risk Reviewer、Action，**最多 5 次请求，首次失败即停止**；不得循环重跑或自动增大参数。

当前单次输出上限 1800 tokens，五次最多 9000 输出 tokens；输入还包含每阶段证据及前序结果，总量受 120000 的保守预留预算约束，时间总上限 300 秒。兼容服务的推理 token 计入方式及价格需依据当时账户定价，不能仅凭旧 77-token 探针报价。货币成本未确认。若原问题是截断，当前上限可能再次不足，但下一次可以记录 length 原因；不要事先声称本修复已经解决截断。

执行前仍需用户确认该一次性在线尝试与可能额度消耗；本轮只建议，**未调用**。

## Git 初始化前检查

`git rev-parse --is-inside-work-tree`：退出码 128，目录仍不是 Git 仓库。本轮没有初始化或发布。

初始化前应重新扫描最终源码、`.env`、日志、构建/source map、缓存和报告；只能报告路径与风险类型，不能打印敏感值。确认示例为占位符，私有配置由 `.gitignore` 排除；初始化后由仓库所有者审查实际暂存区及 staged diff，忽略规则不能清除已跟踪历史。需要真实验收后仍检查日志/报告不含密钥和原始请求，再决定提交。不可把最小真实调用成功、离线 43 项通过或 Git 建立中的任何一项当作完整在线链路已通过。

最终状态：**基础模型最小调用已在此前通过；完整 DeepSeek 在线工作流仍未通过、此次未重跑；Git 仓库未创建。**
