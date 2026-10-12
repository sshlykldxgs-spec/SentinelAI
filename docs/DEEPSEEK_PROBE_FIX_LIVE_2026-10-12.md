# DeepSeek 探针最小修复与单次 Live 验证

日期：2026-10-12（Asia/Shanghai）。写入前确认新报告不存在，未覆盖历史报告。

## 修改与离线验证

仅修改 `scripts/deepseek.sh` 的 probe：按现有 ModelConfig.max_output_tokens 构造请求，正整数传 max_tokens，0/未设置解析为 None 时省略该参数；删除固定 32。成功条件仍为精确标记匹配，并新增明确拒绝 finish_reason=length（即使标记匹配）。没有改动 Agent、Schema、Reviewer、真实 .env、密钥或 CC Switch 设置。

新增 `backend/tests/test_deepseek_probe.py`：直接加载脚本里的实际 probe 函数，用模拟 HTTP 测试正整数、0/未设置、截断、错误标记、429、连接异常；每个场景确认最多一次 post，不放宽断言，不调用凭据桥接。

实际回归命令：`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`。结果 **57/57 通过，7.378 秒**，原有 50 项保留。`sh -n scripts/deepseek.sh` 通过。本轮未运行前端构建（前端未修改），不能写作本轮执行。

共享后端健康检查 HTTP 200，公开 token 上限和预算均为 null、模型未配置。脚本在独立新进程中读取当前文件及已有 CC Switch Deepseek 配置，**不需重启共享服务**；未重启、操作共享用户任务或审批历史。

## 实际生效配置

探针和工作流均显式使用 MODEL_MAX_OUTPUT_TOKENS=0、TASK_TOKEN_BUDGET=0、MODEL_MAX_RETRIES=0。SDK 重试 0。工作流不发送 max_tokens，任务无本地 token 预算。模型 deepseek-flash、域名 api.deepseek.com、密钥和 Base URL 保持原条目。请求超时 45 秒，总任务超时 300 秒未改变。服务方的上下文和默认输出限制仍然存在。

## 最小真实探针：通过

命令：`MODEL_MAX_OUTPUT_TOKENS=0 TASK_TOKEN_BUDGET=0 MODEL_MAX_RETRIES=0 sh scripts/deepseek.sh probe`。

HTTP 200，实际模型 deepseek-flash，SENTINELAI_DEEPSEEK_OK 精确匹配，finish_reason=stop，耗时 1.087 秒，输入 48、输出 32、合计 80 tokens（推理 21，包含在输出内），无重试，退出码 0。

输出刚好 32 tokens **不表示仍发送 max_tokens=32**；修复后的请求没有该参数，finish_reason 为 stop。

## 唯一一次完整工作流尝试：失败

探针通过后才执行：`MODEL_MAX_OUTPUT_TOKENS=0 TASK_TOKEN_BUDGET=0 MODEL_MAX_RETRIES=0 sh scripts/deepseek.sh workflow`。

任务 ID：`5de3f53e-0cdb-41bf-bc42-819ef6c8c23c`；总耗时 115.69 秒，退出码 1，mode=live，status=failed，完整报告未生成，审批操作 0。

| 阶段 | 执行状态 | HTTP | 响应模型 | finish_reason | 阶段耗时 | 输入/输出 tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Planner | completed，结构校验通过 | 200 | deepseek-flash | stop | 11.85 秒 | 3592 / 1814 |
| Research | completed，结构校验通过；存在数值审查发现 | 200 | deepseek-flash | stop | 34.17 秒 | 4044 / 6590 |
| Analyst | completed，结构校验通过；存在数值审查发现 | 200 | deepseek-flash | stop | 24.50 秒 | 10258 / 4945 |
| Risk Reviewer | failed，请求超时，未形成审核结果 | 未获得 | 未取得响应 model | 未获得 | 45.01 秒 | 未提供 |
| Action | queued，未执行 | 不适用 | 无调用 | 不适用 | 不适用 | 不适用 |

前三阶段网络耗时分别为 11.770、34.159、24.490 秒。Reviewer 网络观察器记录 45.000 秒后无 HTTP 状态，符合执行器 wait_for 的 45 秒截止；不能把缺少响应解释为 429/5xx 或断言远端服务故障。

工作流前三次已收到的用量总计 **31243 tokens**；加探针可观察用量 **31323 tokens**。Reviewer 超时请求的远端实际用量/计费未知，不能视为零。保守输入预留 129475、预算 limit=null，不是 token 预算终止。

## 上下文、证据及审核边界

各已开始阶段的 previous_outputs 与传入对象匹配：Research 接收 Planner，Analyst 接收 Planner/Research，Reviewer 接收前三阶段。证据数由 14 增至 29，包含模型假设/引用冲突记录。

数值校验发现 on_time_gap_pp、defect_gap_pp、spend、spend_share、on_time、defect、top3_spend、total_spend、top3_share 未匹配 Python 指标。部分是现有指标目录未定义的派生口径，部分可能使用供应商口径引用聚合指标；没有存储原始响应进行完整语义复核，所以**不能断言这些数值一定计算错误，也不能声称均有支持证据**。程序将它们记为审查发现并传递给 Reviewer，没有放宽证据校验。

Reviewer 未返回审查判断，review.decision=pending；此运行不能认定完整 Live 通过。结构校验完成与业务证据审核通过是不同条件。

## 失败根因与最小下一步

本次直接终止原因已证实为 **Risk Reviewer 请求超过本地 45 秒超时**，错误分类 MODEL_TIMEOUT。没有新的 length 截断：前三阶段均 stop，Reviewer 未取得 finish_reason。远端延迟的原因未知，不是已确认的服务方输出/上下文上限问题。

两个需要分开处理的后续项：

1. 经用户确认后，仅在下一次独立受控进程延长请求超时（现有配置支持至 120 秒），保持无重试与首错停止；不能保证远端按时完成。本轮未调整并重跑。
2. 在离线条件下检查数值口径：供应商事实应引用原记录，聚合 computed 指标引用 M-*；派生指标应由 Python 明确计算/建立证据后再使用。只针对已发现口径问题做最小修复，不放宽 Schema，不忽略 Reviewer。

## 调用次数与保护记录

真实模型请求总计 **5 次**：探针 1，Planner/Research/Analyst/Reviewer 各 1。首个阶段失败后停止，Action 0，无自动重试、并发或第二轮工作流。Reviewer 请求已发起但未收到成功响应，仍计一次实际请求。

只改探针脚本、新增离线测试和本报告。未修改凭据、真实配置、五 Agent 业务逻辑或输出校验；未初始化 Git、提交、推送、部署或删除用户资料。报告只包含安全元数据，未保存密钥、认证头或敏感请求/响应正文。

最终结论：**探针修复与真实连通性通过；三个 Agent 在线结构化执行完成；Reviewer 超时，完整五阶段 Live 未通过。**
