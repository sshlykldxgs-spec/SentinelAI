# 黑盒测试反馈最小修复报告

日期：2026-10-12（Asia/Shanghai）。本轮仅开发与离线验证，**真实模型 API 调用0次**。没有读取/修改真实密钥、替换模型、修改真实 .env、重启共享服务或执行任何 Git/部署操作。本文件新增前确认不存在，历史黑盒报告保留。

## 修改文件

- 新增 `backend/app/research_context.py`：复用现有不截断证据的字段投影，为 Research 去除重复元数据和历史空字段。
- `backend/app/config.py`、`backend/app/engine.py`：Research 独立超时、输入统计，以及失败后未执行阶段的 blocked 状态和事件。
- `backend/.env.example`、`docs/MODEL_SETUP.md`：新增 RESEARCH_TIMEOUT_SECONDS 示例与说明，未写入真实凭据。
- `scripts/deepseek.sh`：验收观察器识别 Research 的预期压缩投影，记录 Research 上下文统计；本轮未执行它。
- `frontend/src/main.jsx`：blocked/pending 展示、当前资料与当前任务指标分离、历史选择恢复资料关联、失败时显示专用报告页。
- `frontend/src/cockpit.jsx`、`frontend/src/cockpit.css`：失败报告、阻断事件、相关样式。
- 新增 `backend/tests/test_blackbox_fixes.py`、`frontend/tests/blackbox-fixes.mjs`；适配原有3个测试文件的下游状态/Research超时预期。没有删除测试、放松失败/无报告/Reviewer/证据校验断言。
- 本报告。构建和测试正常产生缓存/产物，未删除用户文件。

## P0 Research 稳定性

历史黑盒运行在Research单请求45秒处停止，但没有保存Research精确输入或响应，不能断言超时一定由重复上下文造成。当前路径确实传入全部证据含related_claim/document_id，及含空数组的Planner结构；这类冗余可安全移除。

Research现使用与Reviewer一致的确定性字段投影：

- 所有 evidence_id、source_file、source_location、supporting_excerpt、kind、verification_status、supplier、risk_type和demo_data保留，**不删掉未引用证据或长片段**。
- 去除证据related_claim、document_id，以及历史None/空数组/空对象；完整非空上游summary、claims、risks、验收条件等保留。
- 相同校验文本去重，结构化metric_issues保留。JSON紧凑编码，不使用模型摘要、片段截取或删除资料来降低负载。
- 原Schema、Research事实引用要求、Analyst指标要求和Reviewer门禁不变，不跳过Research，不回退Demo。

离线样例使用固定黑盒三文件与模拟Planner（非历史Live回放），输入从17323 UTF-8字节降为15600，减少**9.95%**，26条证据全部保留。这不是在线token节省或成功率保证。

新增 **RESEARCH_TIMEOUT_SECONDS**，默认90秒，范围1–120秒。与现有配置一样读取进程环境→根.env→backend/.env，不覆盖已设置值。只对Research SDK请求和外层Agent.run等待生效；Planner/Analyst/Action保持MODEL_TIMEOUT_SECONDS默认45秒，Reviewer保持90秒，任务总时限仍300秒。没有无限超时或增加全局超时；完整复杂链路仍可能超出总时间。

## P1 失败后阻断状态

后端在任一阶段失败时，保留已完成阶段，将所有pending/queued未执行阶段改为blocked，保存blocked_by、blocked_reason与blocked_at，并在task.failed前发送agent.blocked事件。初始化失败会将所有未执行阶段按task阻断；取消/中断路径也处理未执行阶段。

UI支持pending、running、completed、failed、blocked，并继续兼容queued与waiting_approval。Research失败后显示Analyst/Reviewer/Action已阻断，提示“等待Research Agent完成；当前任务已停止，需手动重新运行”，不继续显示排队。未执行节点不再暗示模型已经运行，详情明确未执行；失败节点footer显示“失败于”，不再显示“完成于”。

兼容性：原测试期待下游pending/queued的3处断言改为blocked并检查blocked_by，这是本次要求的行为变化，不是降低失败标准。原mode=live、task.failed、无报告、无自动继续及Reviewer参与校验保留。

## P2 指标来源与资料刷新

总览现在仅在资料选择与当前任务document_ids一致时显示该任务metrics；没有任务且仍选默认示例时，明确显示“示例数据预览·尚未分析”。上传新资料/改变选中来源导致来源不一致时立即清除旧指标和供应商行，显示“已选资料待分析·尚无当前指标”。

新任务创建后metrics尚未到达时不会退回bootstrap Demo值；事件推送带来的当前任务指标正常显示，并展示任务ID和真实状态。选择历史任务会恢复对应资料ID，防止历史结果与新文件选择混淆。没有在上传时伪造模型分析或自动计算未开始任务的报告。

## P3 失败报告页

有failed任务且没有报告时显示专用“分析未完成，报告未生成”页，包含失败阶段、错误类型/原因、已完成阶段、未执行阶段及下一步建议。可返回失败Agent详情或资料/问题，**不自动重跑**。Live重跑额度提示保留。正常未启动/运行中/成功报告路径不变，失败时没有下载不存在报告的按钮。

当前错误分类MODEL_TIMEOUT仍可能合并请求/任务超时，因此页面展示实际阶段请求截止时间和检查建议，没有宣称远端服务一定故障。没有伪造失败任务的完整报告。

## 验证结果

1. `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`：最终 **74/74通过，7.548秒**，失败/错误/跳过0。新增5项覆盖完整证据投影、独立Research有界超时、SDK/外层截止一致、Research失败下游blocked与事件顺序、初始化失败全部blocked。原有研究/审查、输出拒绝、预算和模式测试通过。
2. frontend中 `npm run build`：**通过，1743 modules，1.57秒**。
3. 新增UI冒烟 `node tests/blackbox-fixes.mjs`：1440px与390px均通过。上传后旧数据消失、当前新CSV指标与failed任务匹配、改变输入再清空、历史切换恢复来源、三节点blocked、失败报告字段/按钮、无失败报告下载、无整页横向溢出。
4. 原有 `tests/smoke.mjs` 在独立离线端口运行（仅在内存替换地址，不改原断言）：桌面/手机七页、Demo/Replay五阶段、报告下载、证据搜索、审批、Replay标识及SSE断网恢复全部通过。
5. UI失败测试使用明确的offline-ui-fixture模拟客户端，第二个阶段抛出模拟超时；成功回归只用Demo/Replay并禁止创建在线模型客户端。**不使用真实凭据、不调用DeepSeek，不能写成Live验收。** 共享服务与其历史未改动。

截图 `/tmp/sentinelai-fix-workflow-1440.png`、`/tmp/sentinelai-fix-report-390.png` 等已检查；只含模拟资料。测试实例和临时代理配置仅用于隔离验证，结束后关闭，不部署。

## 限制与下一步

本轮没有再次验证原黑盒三文件的真实Live成功率。90秒与无损压缩降低了一个明确的本地截止压力，但不保证网络/模型响应及时，任务总300秒仍可能先结束。保留全部证据的精简是小幅优化，不会凭空缩小业务问题。

下一次真实验收如另行授权，应使用同一固定黑盒资料、一次无重试任务，记录Research实际超时/输入统计、全部阶段终态与Reviewer意见；不因失败换资料或削弱校验。本轮按要求完成离线测试、构建、UI冒烟后停止。
