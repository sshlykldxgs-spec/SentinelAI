# SentinelAI Release Candidate 最终黑盒验收

日期：2026-10-12（Asia/Shanghai）。本报告写入前确认不存在。本轮仅通过当前 5173 工作台执行一次新 Live 任务；没有修改源码、Prompt、模型、密钥、`.env`、Git 或部署。

## 总体结论

**NEEDS FIX：本轮没有达到 Release Candidate 的完整成功标准。**

原因：Planner、Research、Analyst 已完成，Risk Reviewer 在本次重启后的独立 120 秒策略下仍以 `MODEL_TIMEOUT` 失败，Action 被阻断，最终报告未生成。Live 模式保持不变，没有 Demo/Replay fallback，也没有自动重试或第二次提交。

## 环境与用户流程

- 当前服务已按授权重启，加载最新代码和现有 DeepSeek 配置。
- UI 公开显示：模型 `deepseek-flash`，服务 `api.deepseek.com`；阶段超时为 Planner 60s、Research 120s、Analyst 90s、Risk Reviewer 120s、Action 120s；SDK/执行器恢复上限为1；本地 token 上限和预算关闭。
- 测试入口：`http://127.0.0.1:5173/`。
- 通过首页流程：取消预选 Demo 文件 → 上传 `suppliers_simulated.csv`、`business_brief.txt`、`public_source_note.txt` → 填写红海航运供应风险问题 → 选择 Live → 点击启动 → 查看工作流和失败报告。
- 仅提交了一个新 Live 任务；没有使用旧任务结果、Demo、Replay 或内部 API。

## 五阶段结果

任务 ID：`dd3528d1-da17-4114-9630-240bf607e122`。前端最终读取到的终态为 failed，总耗时 140.59 秒。

| Agent | 状态 | 尝试次数 | 阶段耗时 | 错误 |
| --- | --- | ---: | ---: | --- |
| Planner | completed | 1 | 8.75s | 无 |
| Research | completed | 1 | 55.34s | 无 |
| Analyst | completed | 1 | 33.14s | 无 |
| Risk Reviewer | failed | 1 | 42.93s | MODEL_TIMEOUT |
| Action | blocked | 0 | 不适用 | 等待 Risk Reviewer 完成 |

界面确认 Risk Reviewer 与前三个阶段的工作流状态；Action 显示 blocked，没有继续显示 queued。失败报告页显示：失败阶段 Risk Reviewer、错误类型 MODEL_TIMEOUT、已完成 Planner/Research/Analyst、未执行 Action，以及建议检查 120 秒请求截止时间和输入规模。

## API 请求与重试

- 实际工作流逻辑请求：4 次（Planner、Research、Analyst、Risk Reviewer各1次）；Action未请求。
- SDK可能拥有内部传输重试上限1，但本次观察记录未能为当前任务取得独立底层HTTP日志；不能将逻辑尝试数当作确切底层请求数。
- 任务中没有 `agent.retrying` 事件，未观察到恢复重试。
- 前三阶段没有可见的失败历史；Risk Reviewer 首次请求失败后立即终止，Action未执行。
- 本轮没有单独探针或第二次工作流请求。

## 用户体验与输出

- 首页可看到模型状态与当前 Live 标签，上传资料后旧 Demo 指标被清空，并显示新资料待分析。
- 工作流能显示前三个完成、Risk Reviewer失败、Action阻断。
- 失败报告页正常展示失败阶段、错误类型、已完成和未执行阶段；没有提供不存在的 Markdown 下载。
- 没有最终报告，因而不能验收完整报告内容、Action建议下载或审批项。此前成功运行的报告不作为本次任务结果。
- 本轮资料全部为公开背景摘要和明确标记的模拟数据；不涉及真实企业机密。

## Release Candidate 判定

| 条件 | 结果 |
| --- | --- |
| 五阶段全部完成 | 未满足 |
| Live 模式执行 | 满足，未fallback |
| 最终报告生成 | 未满足 |
| Research 独立超时生效 | 已由前序黑盒/配置验证确认；本任务Research完成 |
| Risk Reviewer独立超时策略 | 已加载，但本任务仍在42.93s失败，未达到120s；具体远端/SDK原因未知 |
| 下游 blocked 状态 | 满足，Action正确blocked |
| Git操作 | 未执行 |

## 最小下一步

先诊断 Risk Reviewer 在请求等待阶段于42.93秒失败但报告分类为MODEL_TIMEOUT的具体来源：SDK内部超时、连接中断、服务端取消或观察器错误。保留当前失败记录，不自动重跑；后续如要修复，先做离线 transport/timeout 模拟，再单独授权一次真实 Live。不要把延长超时、重试或已有前三阶段成功当作完整流程通过。

本轮到此停止。没有修改代码、密钥、配置或 Git；没有部署或提交。
