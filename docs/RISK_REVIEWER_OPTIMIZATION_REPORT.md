# Risk Reviewer 最小优化报告

日期：2026-10-12（Asia/Shanghai）。写入前确认本文件不存在。此次只做实现与离线验证，真实 API 调用 **0 次**，未执行探针/Live，未修改真实 .env、密钥、模型或共享服务，未执行 Git 操作。

## 1. 修改文件

- `backend/app/reviewer_context.py`（新增）：Reviewer 输入的确定性字段投影，不调用模型做摘要，不截断证据。
- `backend/app/engine.py`：risk 阶段独立上下文和超时；记录上下文长度/证据数量，指标异常进入 review.metric_issues，并保留原审查门禁。
- `backend/app/evidence.py`：数值告警分类，新增可选结构化诊断输出；旧调用方式与中文摘要保持兼容。
- `backend/app/config.py`：新增 REVIEWER_TIMEOUT_SECONDS，90 秒默认值，1–120 秒有界；timeout_for 只为 risk 使用此配置。
- `backend/app/output_validation.py`：CompletionObserver 为 risk 传 SDK 的 extra_create_args.timeout，与外层超时一致；其他阶段继续用原客户端超时。
- `backend/.env.example`：只有示例值，添加 Reviewer 超时说明，没有真实凭据。
- `backend/tests/test_reviewer_optimization.py`（新增）：12 项离线覆盖。
- `scripts/deepseek.sh`：下一次验收的上下文比对识别 Reviewer 的预期投影，记录安全上下文统计/实际超时；本轮只做语法检查，没有执行桥接。
- `docs/MODEL_SETUP.md`：新增配置说明。
- 本报告：记录真实测试与边界。

没有修改 StageOutput/Claim 等业务输出 Schema，未引入新模型、框架或依赖，也未修改原有57项测试断言。

## 2. Reviewer 输入变化

Reviewer 原本接收全部证据（含重复 related_claim、内部document_id）、完整前序输出（含多个空数组）、Python指标、校验摘要与Schema。

新方案仍保留**全量证据覆盖**，仅移除不承担原始支持依据的重复元数据：

| 数据 | 改动 | 保留的审查依据 |
| --- | --- | --- |
| untrusted_evidence | 去掉 related_claim、document_id | 每个 evidence_id、source_file、source_location、完整 supporting_excerpt、kind、verification_status、supplier、risk_type、demo_data 均保留 |
| previous_outputs | 省略 None/空数组/空对象字段 | 所有非空 summary、claims、risks、metric_values、evidence_ids、验收条件、未解决问题、其他实际结果保留；Analyst结论不截断 |
| validation_findings | 完全相同摘要去重 | 不同风险/告警不删除；结构化 metric_issues 保留逐项记录 |
| metric_issues | 新增结构化分类 | 类型、指标键、声明值、目录值、期望证据ID、实际引用列表、阶段、claim序号及blocking标记 |
| JSON 编码 | 仅 risk 使用紧凑分隔符 | 内容相同，去掉格式空白，不剪裁内容 |

没有筛除未引用的原始证据，避免遗漏反例；没有压缩为模型生成摘要或删除风险项。C-* 冲突记录、H-* 模型假设、来源位置、原始片段和 Analyst 结论仍可见。JSON Schema 不变。Reviewer 提示说明告警含义和输入投影，不允许因unknown_metric就无依据批准。

本轮当前 Demo 离线样例对比（不是历史Live回放）：旧结构13177字符/14795 UTF-8字节，新结构11179字符/12731字节，**字节减少13.95%**；14条证据全部保留。这个比例不是在线token节省保证，真实模型输出不同、metric_issues较多时缩减比例会变化；历史Live完整输入未保存，不能报告它的具体节省。

runtime review_context_stats 记录字符/字节、证据数、上游阶段数和指标异常数，不记录完整输入或隐藏思考。excerpts_truncated=false 标明未裁剪证据片段。

## 3. 指标异常分类

保留 validate_references 返回 `list[str]` 的旧契约，增加可选 metric_issues 容器。数值摘要沿用“数值冲突…未匹配Python指标”并附分类码，原测试仍兼容。新增类型：

- **unknown_metric**：不存在所需 M-{metric} 目录项；不是已证明算术错误，expected_value=null。
- **missing_reference**：目录项存在，但当前claim没有引用其ID；即使值相等也不通过。
- **value_mismatch**：目录的数值与声明值不相等；不采用容差或别名绕过。
- **invalid_metric_evidence**：目录项存在但结构没有可比较value，继续阻断。

同一已知指标可同时缺引用且数值不一致，两个原因均保存。未知指标不误记为value_mismatch。没有新增/编造派生指标值，也没有补造或修改业务证据来取消警告。

原摘要、冲突证据和needs_evidence门禁继续存在。新增blocking结构化异常也明确纳入门禁，Reviewer输出pass不能覆盖已有未解决指标异常；Action在证据不足时继续needs_evidence。

## 4. Reviewer 独立超时

使用符合现有命名规范的 **REVIEWER_TIMEOUT_SECONDS**（对应本次要求的独立Reviewer配置），默认 **90 秒**，限于1–120秒。配置读取优先级沿用进程环境 → 根 .env → backend/.env，不覆盖已有值。只有示例文件新增变量，没有写入真实配置。

| 作用域 | 新配置 |
| --- | --- |
| Planner / Research / Analyst / Action | 继续使用 MODEL_TIMEOUT_SECONDS，默认45秒，未改全局配置 |
| Risk Reviewer 外层 Agent.run | 使用 REVIEWER_TIMEOUT_SECONDS，默认90秒 |
| Risk Reviewer SDK请求 | 用 extra_create_args.timeout 覆盖单次请求为相同值，不更改共享客户端默认45秒 |
| 任务总时间 | TASK_TIMEOUT_SECONDS继续默认300秒，包围整条链；Reviewer可能受剩余总时限更早取消 |
| 重试、输出限制、模型 | 本次不改变原策略；无无限超时或无限重跑 |

AutoGen 0.7.5客户端源码明确允许extra_create_args中的timeout，并覆盖共享create配置。离线真实AssistantAgent+Replay测试确认仅risk传入此值，其余四阶段不传；外层等待的时间序列也对应不同配置。SDK覆盖的在线效果本轮未调用模型验证。

## 5. 实际测试结果

完整命令：

```bash
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v
```

结果：**69/69通过，7.458秒，失败/错误/跳过均0**。包含原有57项及新增12项。原有数值、Reviewer不能覆盖错误引用、任务总超时、无效输出、有限预算失败测试仍通过。

新增覆盖：unknown_metric、missing_reference、value_mismatch、组合异常、合法值无异常；审查依据逐字段保留、不改变输入对象、不丢弃长或未引用原文；其他阶段上下文不变；配置默认/上下界/非法值回退；risk SDK和外层超时一致、其他Agent不变；Reviewer超时停止Action；指标异常不能被pass覆盖。

测试清理后复跑 `PYTHONPATH=backend:backend/tests .venv/bin/python -m unittest test_reviewer_optimization -v`：**12/12通过，0.100秒**。

frontend内 `npm run build`：**通过，1743 modules，1.38秒**。`sh -n scripts/deepseek.sh` 和脚本内Python编译均通过；脚本没有执行，因此没有真实API。

## 6. 下一次 Live 建议与限制

本轮到此停止。下一次在线尝试需另行授权，并只执行一次无重试的完整工作流，保留原模型/密钥、Schema和Reviewer，首个失败即停止；不要把本轮离线优化当作Live已经通过。

运行前核实公开配置中的 reviewer_timeout_seconds、其他阶段timeout和总任务时限，独立进程读取新代码即可，不必擅自重启共享服务。记录各阶段HTTP/model/finish reason、Reviewer安全输入统计及逐项metric_issues，不能保存敏感请求或密钥。

90秒是有限的Reviewer容错时间，并不保证服务响应在90秒内返回；总任务300秒仍可能触发。压缩只移除重复字段，保留所有来源以免丢审查依据，因此不是数量级降负载。派生指标/供应商与聚合口径本身仍需Python注册证据或明确引用范围；此次只分类与保留告警，**没有解决或掩盖业务证据缺口**。

最终：最小优化和离线验证通过；本轮真实API调用0次，完整Live未重跑；未修改凭据、跳过Reviewer或执行Git/部署。
