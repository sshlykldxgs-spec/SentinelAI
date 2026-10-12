# SentinelAI 超时策略与一次失败恢复

日期：2026-10-12（Asia/Shanghai）。目标文件写入前确认不存在。本轮仅稳定性实现和离线验证，**真实 API 调用0次**，未读取或修改真实密钥、模型、Base URL、真实.env、用户数据或审批历史。没有执行Git、发布或部署，也没有重启现有DeepSeek共享服务。

## 独立超时与兼容

| Agent | 独立环境变量 | 未设置旧全局值时的默认 |
| --- | --- | --- |
| Planner | PLANNER_TIMEOUT_SECONDS | 60秒 |
| Research | RESEARCH_TIMEOUT_SECONDS | 120秒 |
| Analyst | ANALYST_TIMEOUT_SECONDS | 90秒 |
| Risk Reviewer | REVIEWER_TIMEOUT_SECONDS | 120秒 |
| Action | ACTION_TIMEOUT_SECONDS | 120秒 |

均有1–120秒边界，SDK单请求与外层Agent.run等待使用相同阶段值，不是只延长外层而让SDK提前结束。SDK自动重试继续为0。

配置加载仍为进程环境→根.env→backend/.env，不覆盖已有变量。**独立阶段配置优先；未设置阶段变量时，显式旧MODEL_TIMEOUT_SECONDS作为兼容回退；均未设置才使用上表默认。** 已有90秒Research/Reviewer等显式配置保持有效，不强行覆写。旧ModelConfig构造方式也能回退timeout字段。

MODEL_MAX_RETRIES默认1，允许0关闭恢复，值超过1也钳制为1；执行器再次限制最大一次，防止手动构造配置绕过。TASK_TIMEOUT_SECONDS仍默认300秒，不擅自延长；整个任务截止包含阶段执行及恢复间隔，可能提前终止尚未用完阶段超时的请求。无无限timeout。

## 恢复规则与状态

仅以下失败允许第一次恢复：

- 单请求timeout；连接异常。
- HTTP 502、503、504。

401/403认证、400等请求参数/条件错误、429限流、500/501/其他5xx、JSON/Schema/截断校验错误、业务审查拒绝均**不自动重试**。原有“无效JSON及任意5xx也重试”的行为已移除；Reviewer needs_evidence不是网络错误，不重新调用Reviewer来追求pass。

首次失败先保存脱敏分类和尝试记录，发送agent.attempt_failed，再进入retrying并发送agent.retrying，等待1秒后只进行一次新请求。第二次仍失败则结束任务并blocked下游，不第三次请求、不切Demo。新AssistantAgent执行同一阶段同一输入，避免残留失败消息污染；不改变Schema或添加放宽校验的提示。

每阶段保留：attempts、retry_attempt、max_retries、first_failure、attempt_history。每次记录开始/结束、模型、耗时、可获得用量、finish_reason和脱敏错误。未知用量保留null；超时请求的远端计费不能当作0。事件和记录不保留原始认证头、密钥、请求正文或隐藏思考。

阶段retrying期间任务保持running，因此SSE和任务并发计数继续有效。UI显示“恢复重试(1/1)”，成功后恢复completed（Action可因审批保持waiting_approval），最终失败failed。首次失败原因在终态后仍显示，不用成功覆盖失败历史。

## Action保护

Action没有执行外部操作的模型工具。恢复只重新生成建议。审批项只在最终有效结构化输出后创建一次，仍requires_approval=true；needs_evidence继续禁止批准，audit不被自动填写。Action第二次失败时没有审批或完整报告。retry_attempt明确标记且first_failure保留。

默认启用恢复时五阶段最多10次模型请求（每阶段首请求+1恢复），不是无限请求。任务总截止、token预算（如果用户显式启用）及失败门禁可更早终止。恢复可能重复消耗模型额度；未收到响应的旧请求不保证远端已取消。已有probe和无重试验收脚本仍保持显式无重试，不自动改变此前“一次请求验收”承诺。

## 修改文件

- backend/app/config.py：阶段配置、兼容回退、恢复上限和严格错误白名单。
- backend/app/engine.py：仅一次恢复、1秒间隔、attempt_history/first_failure、retrying事件与全部阶段SDK超时覆盖。
- backend/.env.example、docs/MODEL_SETUP.md：独立默认值及恢复策略说明，只有占位凭据。
- frontend/src/main.jsx、frontend/src/cockpit.jsx、frontend/src/cockpit.css：retrying状态、事件和首次失败/尝试历史展示。
- scripts/deepseek.sh：只增加安全尝试历史观察字段及retrying阶段识别，脚本未执行真实请求。
- backend/tests/test_stability.py（新增）、frontend/tests/stability-ui.mjs（新增）。
- backend/tests/test_v2.py、test_blackbox_fixes.py、test_reviewer_optimization.py：适配本次明确更改的超时默认与“不重试Schema/429/500”预期；原失败、阻断、无报告、Reviewer和证据断言保留，未删除测试。
- 本报告。未修改业务输出Schema、指标校验规则、模型或凭据。

## 实测验证

`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`：**86/86通过，18.066秒，失败/错误/跳过0**。原74项及新增12项覆盖：timeout恢复成功、两次失败无第三次、连接/502/503/504恢复、认证/参数/429/其他5xx禁止恢复、真实解析器非法JSON/Schema/length禁止恢复、Reviewer业务拒绝不重试、Action恢复保留审批、Action第二次失败无报告、关闭恢复、总任务截止中断恢复间隔、配置兼容与独立默认。

frontend中 `npm run build`：**通过，1743 modules，1.42秒**。

`node tests/stability-ui.mjs`：1440px/390px模拟界面均通过retrying(1/1)及completed/failed终态、首次失败原因持续保留、无整页横向溢出、无JS错误。所有/api响应均由浏览器模拟，不连接后端模型。临时Vite无API代理；没有Live成功结果可据此报告。

`sh -n scripts/deepseek.sh`：通过。没有执行probe、workflow或读取CC Switch。所有新增错误测试使用明确offline-fixture，无真实API Key。

## 运行限制与下一步

已有共享后端是此前启动的无重试进程，本轮未重启，也未把历史任务清空。**源码/示例的新默认不会自动注入旧进程**；要启用新策略，应在另行授权的合适时机保留所需资料并重新启动，明确选择MODEL_MAX_RETRIES=1。现有显式MODEL_MAX_RETRIES=0继续禁止恢复，不应误认为已启用。

本轮按要求停止，不进行真实稳定性压测或Live验收。之后如获授权，使用同一固定黑盒资料、一个任务，核对五阶段实际配置及最大两次尝试，保留Reviewer结果与人工审批。不能把离线恢复成功当作真实DeepSeek稳定性已通过，也不能因为等待更久就忽略业务证据不足。
