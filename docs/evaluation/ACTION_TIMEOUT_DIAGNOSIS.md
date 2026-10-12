# Action MODEL_TIMEOUT 只读根因诊断

日期：2026-10-12（Asia/Shanghai）。目标文件写入前确认不存在。此次只读取既有文件、脱敏元数据和代码，不调用任何API、不生成Prompt、不跑测试或Live、不修改源码/配置/密钥/历史报告，不执行Git操作。唯一新增文件为本报告。

## 1. 先确认失败任务：现有验收报告混用了记录

**`docs/evaluation/FINAL_BLACKBOX_RELEASE_TEST.md` 存在任务关联错误，不能作为“Action配置120秒却45.01秒失败”的可靠证据。** 该报告由此前助手生成，错误应明确归于报告，不归于模型响应。本轮不覆盖旧报告，用以下原始观察记录纠正关系：

| 任务ID | 原始记录 | 可核实Action结果 |
| --- | --- | --- |
| f600f76c-86cb-4745-8157-c23543083443 | /tmp/sentinelai-blackbox-round2-observation.json；docs/BLACKBOX_FINAL_ACCEPTANCE_CONNECTED.md | failed，45.01秒，节点request_timeout_seconds=45，无报告 |
| 53c74ced-eccd-40a3-b7ef-837ebd12bd2b | /tmp/sentinelai-final-blackbox-observation.json；/tmp/sentinelai-final-blackbox-http.jsonl；docs/FINAL_BLACKBOX_ACCEPTANCE.md | 输出完成、waiting_approval，41.11秒，Action配置120秒，HTTP200、stop，完整报告已生成 |
| dd3528d1-da17-4114-9630-240bf607e122 | /tmp/sentinelai-rc-recovered-observation.json；docs/FINAL_BLACKBOX_RELEASE_TEST.md | Action blocked，未开始；失败阶段是Risk Reviewer，不是Action |

评估目录报告引用的是成功任务53c74ced，前三/Reviewer耗时、187.04秒总耗时和113677 tokens也来自这个成功任务，却把Action行替换成更早失败任务的45.01秒。因此其“无报告、Action失败、120秒下45秒失败”的结论与对应原始记录冲突。

下文只分析**实际失败任务f600f76c**，并将成功任务53c74ced作为对照。不能为了满足错误前提而猜测SDK覆盖120秒。

## 2. Action请求生命周期

全部已知时间换算为2026-10-12 Asia/Shanghai：

| 生命周期节点 | 可得时间或区间 | 证据与精度 |
| --- | --- | --- |
| Reviewer完成 | 03:16:20.204582 | 上游Agent.completed_at |
| Action进入执行器 | 03:16:20.204612 | Action.started_at |
| Action开始事件 | 03:16:20.204620 | event20 agent.started |
| Prompt生成完成 | 未单独计时；按代码先后应在开始后、首次进度事件之前 | 没有单独Prompt时间点，不能写为精确时间 |
| 逻辑请求进度 | 03:16:20.212244 | event21 agent.progress；表示准备提交，不是网络发送事件 |
| SDK调用开始 | 未单独保存；应晚于进度事件、处于此次Agent.run等待内 | 没有SDK hook开始时间，不能用progress替代 |
| HTTP请求发送 | 未保存绝对时间 | 旧运行记录只保留请求观察耗时44.999秒，没有绝对发送时间 |
| SDK返回成功 | 没有有效返回记录 | tokens=null、finish_reason=null；不能断言远端从未收到请求 |
| 异常产生 | 未保存原异常类/栈/产生时刻 | MODEL_TIMEOUT是安全归类，不是原异常类 |
| 上层捕获/更新Action失败 | 不晚于03:17:05.214656 | Action.completed_at是在上层异常处理写入；不是独立catch hook |
| Agent失败事件 | 03:17:05.214684 | event22 agent.failed |
| 任务失败事件 | 03:17:05.214723 | event23 task.failed |
| 最终任务结束时间 | 03:17:05.214738 | run.completed_at |

Action墙钟时间差45.010044秒，与elapsed_seconds=45.01一致。任务总耗时185.22秒，明显未达到报告记载的300秒总时限。只有一次逻辑请求，无成功HTTP状态、响应模型字段或输出可解析结果；没有证据说明这是Schema失败或输出截断。

## 3. 实际timeout来源及多层关系

### 当时失败任务的配置

- Action节点直接记录request_timeout_seconds=**45**。
- 同任务Reviewer为90秒，Action并未享有Reviewer独立超时。
- 后续重启前归档 `/tmp/sentinelai-before-final-restart.json` 同时保留该失败任务，公开配置timeout_seconds=45、max_retries=0、reviewer_timeout_seconds=90；当时没有action_timeout_seconds公开字段。
- `docs/BLACKBOX_FINAL_ACCEPTANCE_CONNECTED.md` 也明确记载普通Agent45秒、Research/Reviewer90秒、执行器和SDK重试均0。

因此失败使用的是**旧共享/普通阶段45秒配置**，不是当前新增的ACTION_TIMEOUT_SECONDS=120。不是已证实“SDK默认值覆盖显式120秒”。

### 目前磁盘代码的配置链（不等于旧进程快照）

1. `backend/app/config.py:43–48`：独立阶段环境值优先；若缺失则显式MODEL_TIMEOUT_SECONDS兼容回退；否则默认值。ACTION_TIMEOUT_SECONDS默认120。
2. `config.py:109–114`：timeout_for('action')选择action_timeout，旧构造方式缺该值才回退timeout。
3. `config.py:120–122`：共享OpenAI-compatible客户端初始化timeout=self.timeout（传统默认45）。
4. `engine.py:118–120、152–156`：Action取得阶段timeout，并传给CompletionObserver和asyncio.wait_for。
5. `output_validation.py:88–91`：Observer用extra_create_args.timeout覆盖单次create，包含Action，不仅Research/Reviewer。
6. 已安装AutoGen `_openai_client.py:_process_create_args` 允许timeout参数并用update覆盖create配置；再传给SDK chat.completions.create。
7. 已安装OpenAI SDK `_base_client.py:_build_request` 使用options.timeout（显式传入时优先），未传时才用self.timeout。HTTP客户端承担实际网络/响应等待；外层Agent.run截止覆盖SDK内部尝试和消息处理。
8. `engine.py:273` 的asyncio.timeout(config.task_timeout)另包围整个串行链路，默认300秒。

**当前代码确实存在多个超时层，但单次覆盖逻辑未发现Action漏传120秒。** 对旧失败只能确认45秒本地截止吻合；缺原始异常类型，无法区分SDK/HTTP45秒先抛出还是外层wait_for45秒先取消。不能使用当前版本路径反推旧进程也用了全部独立字段。

## 4. Retry判断

timeout在当前 `error_info` 中被标记retryable=true。该字段表示分类资格，不代表恢复开启或SDK已经恢复。

实际失败任务归档max_retries=0，原运行说明SDK重试0，节点attempts=1，没有retry_attempt/attempt_history/first_failure字段，事件序列也没有agent.retrying。**最有证据支持的原因是当时按一次受控黑盒验收关闭恢复，而不是timeout未匹配。** 不能把后来成功任务或当前进程的1次SDK/Schema策略套到更早失败任务上。

当前磁盘路径与旧版本另需区分：

- SDK启用时，engine.py:185–195将timeout/连接等标记recovery_owner=sdk，executor_retry_suppressed=true，防止两层重复传输恢复。
- SDK内部重试不一定产生agent.retrying UI事件；该UI状态对应执行器恢复。所以“未显示retrying”本身不等于“SDK没有重试”。
- SDK和wait_for都受单阶段截止约束，外层可能在SDK完成恢复前中断；总任务截止也可打断。不能因此承诺一次timeout一定会出现第二个请求。

上述说明当前设计，不是失败任务已证实走过这些分支。实际失败只确认一次逻辑尝试与旧受控恢复关闭；原HTTP尝试数和SDK内部日志未独立持久保存，按报告为一次，不能扩大为当前策略失效的证据。

## 5. Action与Reviewer/成功Action比较

| 项目 | 实际失败任务Reviewer | 实际失败任务Action | 后续成功任务Action |
| --- | --- | --- | --- |
| run_id | f600f76c | f600f76c | 53c74ced |
| 模型 | deepseek-flash，成功响应确认 | 请求配置deepseek-flash，无成功响应model | deepseek-flash，HTTP确认 |
| Base URL | 报告记载原DeepSeek条目、域名api.deepseek.com | 同一配置共享客户端；失败快照未保存完整Base URL | 同样条目/域名；所读成功快照未保留完整URL字段 |
| 单阶段截止 | 90秒 | **45秒** | **120秒** |
| 恢复策略 | 原受控运行关闭 | 原受控运行关闭 | SDK/执行器上限1，实际均未触发 |
| 输入上下文 | 前3阶段、38条证据 | 前4阶段、44条证据（input_summary记录） | 前4阶段、37条证据（最终目录后来增至41条） |
| Prompt测量 | 41045字符/56973 UTF-8字节 | **没有Action Prompt长度记录** | 没有Action Prompt长度记录；服务prompt_tokens=32635 |
| 服务输入/输出tokens | 15674 / 10536 | 未提供 | 32635 / 10700 |
| 本地输出限制 | 关闭 | 关闭 | 关闭 |
| 输出要求 | 审查decision、发现、证据/结论核对 | actions非空、负责人/期限/影响/引用/审批要求；保留Reviewer意见 | 同类Action输出契约，并非只回复短标记 |
| 耗时与结果 | 41.43s，HTTP200/stop | 45.01s，MODEL_TIMEOUT | 41.11s，HTTP200/stop，报告生成 |

读取保存组件而不重建Prompt：失败任务四个上游输出序列化UTF-8体积约2252、15445、17585、18626字节；成功任务对应3133、9156、17264、15557字节。它们不是实际Action请求字节总数，也不包括Schema/证据/指令/系统Prompt。

失败目录中有12个完全相同的supporting_excerpt重复（包括模型分析/假设，不全是原文件重复），成功最终目录中有7个；片段最长319字符。Action上下文在当前代码仍传全量历史/证据，内容可能跨claims、related_claim和假设重复；这是有据的负载方向，**不是已证明它超过上下文窗口或导致45秒超时**。成功请求自身也有较大输入，不能单凭大小断言因果。

## 6. 最可能原因排序（区分确认程度）

1. **已证实的报告错误：成功任务ID/配置/用量与旧失败Action行混用。** 应先纠正诊断前提，而不是调整模型或timeout。本轮只在此记录，未覆盖历史报告。
2. **实际旧失败的直接限制：本地Action45秒请求/Agent截止被达到。** 时间差与节点45值相符，任务未达总300秒；优先解释为配置当时仍是旧普通阶段值。SDK/HTTP或执行器谁先触发无法唯一定位。
3. **模型生成或网络/响应等待超过旧45秒。** 无有效响应和上游较长内容支持等待不足的可能性，具体是否长推理、服务排队、网络延迟未知。
4. **服务端取消、网络连接异常或本地分类把其他含Timeout名称异常归为超时。** 缺status、request-id、原异常类/原因链；只有可能，不能确认为远端故障。
5. **显式120秒被SDK默认45秒覆盖。** 当前代码逐次覆盖有效、真实失败节点为45，因此没有支持该假设的同任务证据。

## 7. 最小建议（本轮未执行）

- 首先将历史验收文档按任务ID重新核对，纠正混用的Action结果和总用量；需要单独授权修改旧报告，不能将它继续作为新功能阻塞的可靠证据。
- 若需要调查真正“显式120秒下提前失败”的新记录，只增加脱敏观测类别/绝对及单调时间：Agent进入、Prompt完成、SDK逻辑开始、HTTP每次发送/结束、异常类与原因类、有效请求timeout和retry次数，不保存正文或认证头。先用离线transport测试；真实调用仍须另行授权。
- 没有证据要求当前修改Schema、Prompt、模型、密钥或独立timeout。当前已验证的成功53c74ced说明该版本Action120秒路径至少完成过一次，不代表稳定成功率保证。
- 必要时评估Action历史输入冗余与输出规模，但不能在此只读轮自动删证据、增超时、重跑或取消审核。

最终诊断：**本轮指向的“Action配置120秒却45.01秒失败”由报告记录混用造成；能确认的旧Action失败实际配置45秒且关闭恢复。** SDK/HTTP/外层精确异常先后因记录不足不可恢复。只新增此报告后停止；源码、配置、密钥、服务和Git保持不变，模型API请求0次。
