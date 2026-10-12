# SentinelAI Release Candidate 最终黑盒验收

日期：2026-10-12（Asia/Shanghai）。本轮通过当前5173工作台执行一次新Live任务；没有修改源码、Prompt、模型、密钥、`.env`、Git或部署。

## 总体结论

**NEEDS FIX：本轮没有达到完整Release Candidate成功标准。**

Planner、Research、Analyst、Risk Reviewer完成，Action在本次最终任务中失败于 **MODEL_TIMEOUT**，没有生成最终报告，因此不能标记完整Live成功。任务保持Live，没有Demo/Replay fallback；没有自动重跑或第二次提交。

## 环境与实际配置

- 共享后端按用户授权重启后，加载最新代码和现有DeepSeek配置。
- 配置显示模型`deepseek-flash`、服务`api.deepseek.com`。
- 独立阶段超时：Planner 60s、Research 120s、Analyst 90s、Risk Reviewer 120s、Action 120s。
- SDK/执行器恢复上限为1；本次各阶段attempts=1，没有retrying事件。
- 本地输出token上限和任务token预算关闭；任务总上限300秒。
- 原共享任务与文件元数据在重启前保存了脱敏观察，未把原始上传字节写入备份。

## 评委操作流程

1. 打开`http://127.0.0.1:5173/`，确认Live可选、当前模型为deepseek-flash。
2. 取消默认Demo文件；上传固定公开背景及明确标注为模拟的三份资料：
   - `blackbox_case_2026-10-12/suppliers_simulated.csv`
   - `business_brief.txt`
   - `public_source_note.txt`
3. 填写红海航运扰动下未来30天供应风险问题，选择Live，启动一次。
4. 通过工作流页查看五阶段、证据和失败状态；没有修改状态、切换模式或使用旧任务结果。

上传后旧Demo指标被清除，显示当前资料待分析；任务来源为`suppliers_simulated.csv`。本轮使用公开历史背景和虚构供应商数据，不涉及内部机密。

## 阶段结果

本次任务ID：`53c74ced-eccd-40a3-b7ef-837ebd12bd2b`。后台总耗时约187.04秒；UI从启动到终态约187.24秒。

| Agent | 状态 | 请求次数 | 阶段耗时 | 结果 |
|---|---|---:|---:|---|
| Planner | completed | 1 | 6.63s | finish_reason=stop |
| Research | completed | 1 | 53.96s | finish_reason=stop |
| Analyst | completed | 1 | 37.93s | finish_reason=stop |
| Risk Reviewer | completed | 1 | 47.21s | finish_reason=stop；needs_evidence |
| Action | failed | 1 | 45.01s | MODEL_TIMEOUT |

四个成功请求均返回HTTP 200和模型`deepseek-flash`；Action请求没有取得有效HTTP状态或finish reason。实际请求合计5次，均为首次逻辑尝试；没有retrying，Action没有报告输出。

可见失败详情：

- 失败阶段：Action Agent
- 类型：MODEL_TIMEOUT
- 已完成：Planner、Research、Analyst、Risk Reviewer
- 未执行：无（Action已开始但没有完成）
- 建议：检查Action请求截止时间与输入规模后，再手动决定是否重跑

下游没有可阻断阶段，因此本轮没有展示blocked节点。报告页展示专用失败报告，不显示“先运行一次分析”的普通空态，也没有下载不存在的Markdown。

## Reviewer与审批

Reviewer实际完成独立审查，评审结论为`needs_evidence`，指出库存/到货承诺/日消耗/报价/备用认证等证据缺口，并保持模拟宏观资料的external_unverified边界。10项Action建议未能生成本轮最终状态，因为Action超时；没有审批操作、采购、合同或外部行动。

## 实际模型请求统计

本轮实时观察到5个工作流请求：Planner、Research、Analyst、Risk、Action各1个。可获得总用量：输入70885、输出42792、合计113677 tokens；这些是服务响应usage，不包含未响应Action的未知远端消耗。没有探针、并发、自动重试或第二个Live任务。

## 用户体验评价

通过项：

- 首页可见模型和Live状态；配置入口可访问。
- 上传新资料后旧Demo指标清除，当前任务来源明确。
- Research在120秒独立截止内完成，之前的45秒阻塞消失。
- 工作流能区分完成、失败和Action当前状态；Report页能解释失败阶段、错误、已完成和未执行信息。
- 证据中心、报告和待审批入口可用；本轮没有生成报告，所以只验证到失败状态。
- 通过当前模拟UI桌面/手机检查，页面无JS错误和整页横向溢出。

待改进：

- Action仍在45秒默认阶段截止内失败；本次原因被安全分类为超时，无法仅凭浏览器判断远端响应慢、SDK取消还是连接层异常。
- 由于Action是最后阶段，本轮没有blocked下游可观察；此前离线测试已覆盖Research失败后的blocked展示，但不是本轮Live结果。
- Reviewer意见为needs_evidence是业务审查结果，不是程序错误；应继续要求人工补充证据，不能改成通过。

## 判定

**NEEDS FIX。** 本轮Live执行到最后阶段，但未满足“Action完成 + 最终报告生成”。基础模型调用、前三个分析阶段和Reviewer在线审查均有实测证据；完整Live报告交付没有通过。没有自动修复、换模型、调参数、重跑或修改代码。

本轮到此停止。共享后端和前端保持运行，未执行Git操作或部署。
