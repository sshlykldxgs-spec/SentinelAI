# 第二轮黑盒评委验收：授权接入 DeepSeek 后

日期：2026-10-12（Asia/Shanghai）。新报告写入前确认不存在。保留 `BLACKBOX_FINAL_ACCEPTANCE.md` 中未接入时的阻塞结果，本报告记录用户明确授权接入后的新UI尝试，不覆盖历史。

## 结论

**本次不能标记 BLACKBOX ACCEPTED。** 陌生用户在已配置的工作台完成资料上传、启动Live，并获得Planner、Research、Analyst、Risk Reviewer有效阶段输出，但Action超过45秒请求截止，最终报告未生成。Research独立90秒、数据来源与失败报告页修复有效；完整分析交付仍存在Action超时阻塞。

本次只运行一个新任务，无额外探针、无自动重试、无并发、无失败后再次调用。模型、Base URL、密钥、业务代码和超时值未修改。没有Git操作。

## 接入与保护

用户授权“可以接入”后，只读核对原8000服务：没有任务记录，也没有用户上传文件。原服务尚未加载模型。停止原无模型服务并在同一8000端口通过现有CC Switch只读桥接加载Deepseek；现有5173前端代理未修改，普通页面直接使用新后端。

凭据只在后端进程内存使用，不写.env、不回显或导出。原条目模型deepseek-flash、服务域名api.deepseek.com。普通Agent45秒，Research90秒、Reviewer90秒，总任务300秒；本地token上限/预算关闭。为保持一次请求规则，启动环境的MODEL_MAX_RETRIES=0，SDK重试0，不是绕过超时或输出验证。没有更换模型、密钥或使用隐藏参数重跑。

此次服务接入是用户明确授权的前置操作，之后全部任务交互来自浏览器UI；没有开发API创建任务或手动改状态。被动响应观察器只记录HTTP、模型、finish_reason、用量和耗时，不改模型输出。后端保持运行，以供用户使用；重启会丢失内存记录和进程内配置，需要用既有安全启动方式重新加载。

## 案例和操作路径

沿用第一轮**固定输入资料**，未因失败修改案例：虚构欧洲设备企业在历史红海航运扰动下的30天采购决策。公开来源为IMF 2024-03-07文章：

<https://www.imf.org/en/blogs/articles/2024/03/07/red-sea-attacks-disrupt-global-trade>

资料包含正常供应商、交付/质量异常、未知库存/备用数、订单/报价/认证缺口。所有供应商和数值均标注模拟，宏观来源只提供背景，不证明供应商延误原因。

文件：`blackbox_case_2026-10-12/suppliers_simulated.csv`、`business_brief.txt`、`public_source_note.txt`。复用输入不是复用旧任务结果。

UI操作：打开 `http://127.0.0.1:5173/` → 确认Live可选 → 取消默认Demo文件 → 上传三文件 → 填写与第一轮相同业务问题 → 选择Live → 点击启动一次 → 等待终态 → 查看各Agent → 返回总览核对来源 → 查看失败报告页。没有选择旧任务、Replay或Demo替代Live。

## 技术结果

运行ID：`f600f76c-86cb-4745-8157-c23543083443`；mode=live，模型deepseek-flash，后台总耗时185.22秒，浏览器到终态185.551秒。真实模型请求**5次**，每阶段一次；最后请求未收到成功响应也计为已发起一次。报告未生成，下载未执行。

| Agent | 状态 | 请求耗时 | 阶段耗时 | HTTP | finish_reason | 输入/输出tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Planner | completed | 12.065s | 12.16s | 200 | stop | 5864 / 2219 |
| Research | completed，进入Analyst | 62.148s | 62.16s | 200 | stop | 4683 / 14859 |
| Analyst | completed | 24.286s | 24.30s | 200 | stop | 16122 / 6792 |
| Risk Reviewer | completed，needs_evidence | 41.422s | 41.43s | 200 | stop | 15674 / 10536 |
| Action | failed，MODEL_TIMEOUT | 44.999s | 45.01s | 未取得 | 未取得 | 未提供 |

前四个响应model字段均为deepseek-flash；Action请求配置仍为同一模型，但无响应字段可确认。可观察token合计76749（输入42343、输出34406），Action远端用量/计费未知，不当作零。没有新length截断证据，Action也没有HTTP状态，不能断言服务端5xx、限流或上下文超限。

### 阶段质量观察

- Planner理解模拟属性、公开背景与供应商证据的区别，要求空白值保持未知、质量/交付分别核查、行动需人工批准。
- Research提取Beacon Drives交付+质量异常、Elm Power质量问题和Dune Sensors库存未知；62.16秒完成，确实超出旧45秒但在现有90秒内。
- Analyst计算6家、月采购额715000 USD、简单平均准时率91.7%、缺陷率1.88%，明确不是订单/样本加权平均；未虚构趋势或停产日期。
- Reviewer完成独立检查，指出到货承诺、订单、日消耗、报价、认证及违约条款缺失，判定needs_evidence。结构化metric_issues为0不等于无业务风险；审查发现11条。
- Action未取得有效输出，行动合理性与最终报告可读性无法验收。

Research输入统计14178字符/17662 UTF-8字节、26条证据、1个上游阶段，完整片段保留。Reviewer输入41045字符/56973字节、38条证据、3个上游阶段、无截断。没有自动把needs_evidence改为pass，业务审查未批准不等同程序超时。

## P0–P3实测覆盖

| 项目 | 本次结论 |
| --- | --- |
| P0 Research独立超时 | 通过本次运行：节点记录request_timeout=90，62.16秒完成并进入Analyst；不表示所有资料都保证90秒内完成 |
| P1 blocked | 本次未触发下游阻断：失败的是最后Action，无后续节点可观察。UI显示四completed、一failed，不继续排队；原离线blocked冒烟记录保留，不冒充本次验证 |
| P2上传与当前来源 | 通过：新上传后supplier-row数量0，显示“已选资料待分析·尚无当前指标”；运行后来源suppliers_simulated.csv、当前任务ID f600f76c、状态failed，显示新供应商而非旧Demo |
| P2报告引用 | 未验证：最终报告未生成；阶段结论体现输入内容，不等于报告引用已验收 |
| P3失败报告 | 通过：显示Action Agent、MODEL_TIMEOUT、四个已完成阶段、未执行阶段“无”、45秒截止与手动处理建议；没有普通“先运行一次分析”空态 |

页面无JS异常，没有整页崩溃。截图：`/tmp/sentinelai-blackbox-round2-ready.png`、`/tmp/sentinelai-blackbox-round2-workflow.png`、`/tmp/sentinelai-blackbox-round2-report.png`；只含公开/模拟资料。脱敏浏览器观察记录为 `/tmp/sentinelai-blackbox-round2-observation.json`，未保存认证头或隐藏推理。

## 用户体验与最小建议

相比第一轮，新资料指标来源更清晰，Research不再卡在45秒，失败报告也可说明发生阶段及已完成范围。但一位评委仍需等待约3分钟后收到“Action超时”、无法下载最终分析；**完整报告交付没有通过**。

已证实直接终止原因是Action本地单请求45秒截止；远端慢的原因未知。Reviewer needs_evidence是合理的资料缺口判断，不是本次程序失败的原因，也不能为了成功删掉审核意见。

最小下一步只能建议：离线检查Action输入是否重复扩张以及生成内容长度；如需独立Action有限超时/精简，应另行授权并测试，不能此轮自动修改或重跑。保持同一固定案例再验收，避免通过删资料或选完美结果获得成功。

此次仅授权接入服务、执行一个UI任务，并新增本报告；业务源码、真实配置文件、密钥和输入资料未修改。没有Git初始化、提交推送、部署或清理历史。已有 `BLACKBOX_FINAL_ACCEPTANCE.md` 的未配置阻塞记录仍保留。

最终：**NOT ACCEPTED（Action超时，报告未生成）**。到此停止，DeepSeek工作台保留可用状态，无自动重试。
