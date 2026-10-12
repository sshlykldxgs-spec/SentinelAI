# SentinelAI 最终黑盒稳定性验收：重试策略版本

日期：2026-10-12（Asia/Shanghai）。本报告写入前确认不存在；不覆盖历史失败记录。

## 总体结论

**BLACKBOX ACCEPTED：本轮通过5173工作台上传资料、创建新Live任务、完成五阶段、查看及下载真实报告、查看人工审批事项。** mode=live，无Demo/Replay fallback。

**业务批准未通过：Reviewer判断needs_evidence。** 10项行动均需补资料，批准按钮全部禁用，未操作审批、采购或任何外部动作。业务资料缺口是正常审查结果，不是程序执行失败。

本次真实模型请求5次，全部首请求成功；**重试实际触发0次**。不能将策略加载或正常流程成功当作timeout/SDK/Schema恢复已在本轮实测。

## 服务与策略实际加载

用户明确授权重启以加载最新代码。重启前通过浏览器观察公开bootstrap数据：旧服务有1个终态任务、5份文件元数据，没有正在执行任务；将可见任务/证据/文件元数据保留到本地 `/tmp/sentinelai-before-final-restart.json`。上传原始文件仍在固定案例目录；该归档不是全部后端私有内存或跨重启持久化恢复。

停止旧后端后在同一8000端口读取最新源码并复用现有CC Switch Deepseek条目。5173前端与代理没有更改。没有改模型、密钥、Base URL、真实.env或业务代码，没有设置特殊验收参数；新进程直接使用当前配置默认值。

页面被动收到的公开model_config与服务器启动信息一致：

| 配置 | 实际生效值 |
| --- | --- |
| 模型/服务域名 | deepseek-flash / api.deepseek.com |
| Planner timeout | 60秒 |
| Research timeout | 120秒 |
| Analyst timeout | 90秒 |
| Reviewer timeout | 120秒 |
| Action timeout | 120秒 |
| SDK最多重试 | 1 |
| 执行器Schema最多修正 | 1 |
| 本地输出上限/任务token预算 | null / null（关闭） |
| 总任务时限 | 300秒 |

SDK/Schema策略由最新代码加载；HTTP计数来自只保存响应元数据的被动transport观察器，没有保存密钥、认证头、完整请求或隐藏思考，也没有修改响应。SDK恢复发生在逻辑请求内，执行器attempts不是底层HTTP次数。本轮观察器明确记录了实际5次HTTP请求。

## 案例与UI步骤

案例仍是固定的模拟欧洲工业设备企业2024-02红海航运扰动采购决策。公开背景为IMF 2024-03-07历史文章：

<https://www.imf.org/en/blogs/articles/2024/03/07/red-sea-attacks-disrupt-global-trade>

输入文件与前两轮相同，未为成功删除或修改缺失项：

- `blackbox_case_2026-10-12/suppliers_simulated.csv`
- `blackbox_case_2026-10-12/business_brief.txt`
- `blackbox_case_2026-10-12/public_source_note.txt`

供应商、金额及指标明确为SIMULATED。存在交付异常、质量异常、库存/备用认证未知及订单分母/加急报价缺失；宏观资料不证明单个供应商延误原因。

操作：打开5173 → 取消预选Demo文件 → 上传3文件 → 填写与之前相同的问题 → 选择Live → 点击启动一次 → 等待终态 → 逐个查看Agent → 报告页预览并下载 → 查看待审批 → 返回总览核对来源。

没有使用开发接口创建任务、修改任务状态、选择旧结果、运行Demo/Replay或额外模型探针。浏览器正常产生应用请求和SSE；被动观察器记录这些已经由UI收到的数据，未伪造结果。

## 运行结果与请求计数

任务ID：`53c74ced-eccd-40a3-b7ef-837ebd12bd2b`。后端总耗时 **187.04秒**，点击启动到浏览器收到终态 **187.238秒**（不包含后续长报告截图/下载操作）。最终status=waiting_approval，完整报告已生成。

| Agent | 状态 | 逻辑尝试/HTTP请求 | retry原因 | 请求耗时 | 阶段耗时 | HTTP/模型/finish_reason |
| --- | --- | --- | --- | --- | --- | --- |
| Planner | completed | 1 / 1 | 无 | 6.536s | 6.63s | 200 / deepseek-flash / stop |
| Research | completed | 1 / 1 | 无 | 53.949s | 53.96s | 200 / deepseek-flash / stop |
| Analyst | completed | 1 / 1 | 无 | 37.921s | 37.93s | 200 / deepseek-flash / stop |
| Risk Reviewer | completed | 1 / 1 | 无 | 47.196s | 47.21s | 200 / deepseek-flash / stop |
| Action | 输出完成，waiting_approval | 1 / 1 | 无 | 41.090s | 41.11s | 200 / deepseek-flash / stop |

本地时区开始/结束：Planner 03:52:37.062–03:52:43.688；Research 03:52:43.688–03:53:37.645；Analyst 03:53:37.645–03:54:15.574；Reviewer 03:54:15.574–03:55:02.780；Action 03:55:02.780–03:55:43.884。均为2026-10-12 Asia/Shanghai。

各阶段输入/输出tokens：5878/1119、5074/11514、13756/8783、13542/10676、32635/10700。总输入70885、总输出42792，**合计113677 tokens**，以服务响应usage为依据。没有超时请求的未知用量。

### retry统计与验证边界

- SDK额外HTTP恢复：0；执行器Schema/其它恢复：0；agent.retrying事件：0。
- 每个Agent.retry_attempt=0，first_failure=null；每个attempt_history只有一条成功逻辑尝试。
- 本轮Research/Action为running→completed或waiting_approval，没有出现running→retrying→completed；**不能证明实际恢复路径已在线通过**。
- 本轮没有第一次Schema错误及第二次修正结果，Schema恢复仍只有已有离线测试证据。
- 新代码包含retrying状态展示，此前离线桌面/手机模拟通过；本次因无恢复事件没有再次显示它。禁止为验收人为制造模型失败或伪造恢复。

## 报告与审批

浏览器下载的真实报告：`blackbox_case_2026-10-12/final_retry_live_report_download.md`。文件写入前确认不存在，下载内容与本轮UI运行report相同，明确标记Live、deepseek-flash和模拟资料。脱敏导出后扫描：已知个人凭据及常见可信凭据格式命中0。

UI最终报告预览包含风险排序、证据对应、Reviewer意见和行动方案；Markdown下载可用。来源仅为三份新上传文件及模型假设，不夹带旧Demo资料。总览显示“当前任务·53c74ced·waiting_approval”，正确引用suppliers_simulated.csv；新上传前旧指标已清除。

Reviewer输入34548字符/48722字节、33条证据、3个上游阶段，原始片段未截断，结构化metric_issues=0。完整报告最终显示41条证据，不能将0异常理解为全部业务事实已核实。

Reviewer判定needs_evidence，报告指出库存、到货承诺、消耗速度、备用认证及加急报价缺失，并发现业务说明与CSV对路线/东亚来源数量不一致。测试没有为消除这项警告修正资料。报告建议要求补充/人工复核，体现业务风险判断而非软件错误。

Action有效结构化输出产生10项建议，全部requires_approval=true、status=needs_evidence、audit为空。审批页实测10个批准按钮全部disabled，资料不足不会被自动批准。未点击批准/驳回/补资料，不测试真实审批写入；本轮确认的是审批门禁显示和建议未执行。

## 首次使用体验

- 模型加载后Live可选，上传→启动路径清晰；无需开发接口操作任务。
- 新资料待分析及当前指标来源清楚，旧Demo不再误导为新结果。
- Research53.96秒超过旧45秒但在现有120秒内完成；Reviewer47.21秒、Action41.11秒也正常完成，无失败页。
- 完整报告和10项审批均可查看；needs_evidence提示保留，不将用户资料缺口视作技术失败。
- 报告很长（下载约125KB），全页截图渲染耗时明显，评委需要滚动筛查；本次未改动UI。不能由一次成功推算稳定成功率。

截图与安全观察产物：`/tmp/sentinelai-final-blackbox-ready.png`、`workflow.png`、`report-viewport.png`、`approvals-viewport.png`（后3项文件名前缀均为sentinelai-final-blackbox-）；脱敏SSE观察与HTTP元数据在对应/tmp文件中。没有认证信息或隐藏推理日志。

## 停止与限制

本轮按授权完成后端重启，未修改应用代码、密钥、模型、Base URL、.env、超时或重试参数，未初始化Git、提交推送或部署。只新增本报告和通过UI下载的业务报告，以及必要本地观察文件。服务保持5173/8000运行，当前任务留在内存中；再重启会清空，旧记录已本地归档但不提供完整跨进程恢复。

到此停止，不再真实请求、不执行恢复压测或第二次Live。**完整Live黑盒用户路径通过；业务建议待补证据；真实失败恢复仍未触发，不得列为已在线验证。**
