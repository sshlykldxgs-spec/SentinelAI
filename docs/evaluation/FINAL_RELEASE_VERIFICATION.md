# SentinelAI Final Release Verification

日期：2026-10-12（Asia/Shanghai）。本轮通过当前5173工作台执行配置入口和单次连接测试；未启动Live任务，因连接测试未通过而按停止规则结束。未修改业务代码、Prompt、Schema、模型、timeout/retry、密钥、`.env`或Git。

## 1. 测试环境

- 工作台：`http://127.0.0.1:5173/`。
- 后端：重启后当前代码实例，监听127.0.0.1:8000；配置来源为环境/现有进程配置，bootstrap不返回API Key。
- 模型：deepseek-flash，服务域名api.deepseek.com。
- 阶段配置：Planner 60s、Research 120s、Analyst 90s、Risk Reviewer 120s、Action 120s；SDK/执行器恢复上限1；本地token上限/预算关闭。
- 输入计划：`blackbox_case_2026-10-12/`中的CSV、业务说明和公开来源摘要，全部为公开/模拟资料。

## 2. 模型配置体验

首页入口「模型配置」可见；未配置时显示“Live模式需要配置您自己的模型API。Demo模式无需配置”。进入配置页可看到OpenAI Compatible、API Base URL、API Key密码框、Model Name和最大输出Token。

未配置Live启动被前端拦截并跳转设置，未创建任务。无效Base URL被前端/后端拒绝，未发起模型测试。密码框为password类型；本次输入后由UI清空，没有写入浏览器存储或返回前端配置响应。

随后通过UI保存现有DeepSeek配置并点击“测试连接”。保存仅保存在后端当前进程内存，不写`.env`。连接测试发起一次真实请求，服务返回响应，但未通过系统要求的精确OK标记，UI显示：

> 接口返回了响应，但最小标记校验未通过；请核对模型或接口兼容性。

页面同时显示模型`deepseek-flash`和耗时约1.028s。没有API Key、Authorization Header或原始响应写入报告。

## 3. Live运行结果

由于最小连接测试未通过，本轮没有启动真实Live任务。没有上传新案例资料到本轮任务，没有调用五阶段模型执行器，也没有使用Demo/Replay冒充Live。

| Agent | 状态 |
|---|---|
| Planner | 未执行 |
| Research | 未执行 |
| Analyst | 未执行 |
| Risk Reviewer | 未执行 |
| Action | 未执行 |

- 真实API请求次数：**1次**，仅为连接测试。
- 五阶段API请求次数：0次。
- 最终报告：未生成。
- 审批：未执行。
- Fallback：未发生。
- Git：未操作。

当前运行内存中出现1个已有任务记录，但本轮没有创建新任务；不将该历史记录视为本轮Live结果。连接失败后没有自动重试或再次调用。

## 4. 安全与错误处理

- 未配置时Live不会提交任务。
- 无效Base URL在模型测试前被拒绝。
- 连接请求返回HTTP响应但标记校验失败，UI显示失败，没有伪造成功或切换Demo。
- API Key输入采用password，提交后清空；配置只写进程内存。
- 没有发现页面错误；没有输出或保存密钥。

本轮失败分类是**最小连接测试响应校验失败**，不是五阶段Agent失败，也没有证据表明认证、网络或模型不存在。由于不保留原始响应，不能进一步判断模型返回了额外文本还是其他内容。

## 5. Release Candidate判定

**NEEDS REVIEW，不满足 FINAL RELEASE VERIFIED。**

通过：配置入口、未配置Live保护、密码输入保护、无效地址拒绝、配置保存边界、错误可见。

未通过或未执行：连接测试精确标记、完整五阶段Live、最终报告、审批流程和无fallback全流程。

## 6. 下一步建议

确认模型连接测试的最小响应契约是否与当前DeepSeek服务实际返回格式一致；需要用户授权后，针对连接测试响应做脱敏诊断或调整测试提示/解析规则。不要直接启动五阶段、重复请求、改密钥、放宽Schema或把非精确响应标成成功。

本轮到此停止。没有修改代码、模型、密钥、`.env`、timeout/retry或Git。

---

## 2026-10-12 独立实例复验（09:18 Asia/Shanghai）

**结论：NOT VERIFIED。连接测试失败，按停止条件未启动 Live；不能标记 FINAL RELEASE VERIFIED。** 上文是历史验收记录，不是本次复验结果。

- 在独立 `127.0.0.1:18000` 后端加载当前源码；原有 8000/5173 服务未重启。通过 5173 工作台页面、仅将浏览器的 API 请求转发到独立后端进行操作。模型保持 `deepseek-flash`、服务域名 `api.deepseek.com`，输出上限未设；阶段超时保持 60/120/90/120/120 秒，执行器与 SDK 配置恢复上限均为 1。未更换模型、Base URL、凭据或这些参数。页面测试会保存现有同值配置到独立实例内存，因此复验后配置来源显示 `process_memory`，不代表模型参数被改动。
- 以页面进入「模型配置」，模型、服务地址与现有配置一致，API Key 输入框为空；点击「测试连接」。诊断中一次页面等待超过 80 秒，没有取得测试接口响应，不能确认该次是否到达上游；随后一次浏览器路由诊断明确拦截了测试请求，未让它进入模型接口。最终一次放行的页面连接测试收到本地 `POST /api/model/test` HTTP 200、`ok=false`；UI 显示“接口未返回正常结束的非空文本响应；请核对模型或接口兼容性。”，模型为 `deepseek-flash`，接口报告耗时 1.955 秒，API Key 输入框已清空。放行的页面操作只观察到一次测试接口请求；本轮没有可靠的上游 HTTP 请求总计数，不能把本地 200 写成模型服务的 HTTP 200。
- **失败分类：用户连接测试的正常文本/完成条件未满足。** 接口不回传或保存模型原文与底层 `finish_reason`，故无法从这次脱敏结果进一步区分空文本、异常结束或客户端消息转换。未重复放行连接测试以追查原因，也未修改代码或参数。
- 停止前独立实例 `run_count=0`。Planner、Research、Analyst、Risk Reviewer、Action **均未执行**；无阶段耗时、阶段请求或 retry 记录；未生成最终报告，也无 Demo/Replay fallback。既有历史 Live 成功记录不能代替本次完整流程。
- 本次仅更新此验收记录，未修改业务代码、Prompt、Schema、timeout/retry、模型或密钥，未执行 Git 写操作。开始时曾执行一次只读 `git status --short` 核对工作区；无提交、暂存或其他 Git 变更。

---

## 2026-10-12 Final Attempt（独立实例，Asia/Shanghai）

**FINAL RELEASE VERIFIED：本次连接测试通过，公开案例的唯一一次新 Live 任务完成五阶段并生成最终报告。** 这是本次技术执行链与报告生成的验收结论，不覆盖上文历史失败，也不表示 Reviewer 的业务意见已通过或行动已获批准。

### 配置与连接

- 在 `127.0.0.1:18000` 启动独立后端加载当前源码；原有 8000/5173 服务未重启。评委视角从 5173 工作台进入模型配置页，页面 API 请求指向独立后端；填写/确认已有同值配置，沿用进程内原凭据，没有更换 API Key、模型或 Base URL。页面保存只改变独立实例内存中的配置来源标识。模型 `deepseek-flash`，服务域名 `api.deepseek.com`；本地输出上限和任务预算均未设置。阶段时限依次为 60/120/90/120/120 秒，执行器与 SDK 恢复上限各 1，值均未调整。
- 页面仅发起一次连接测试：本地接口 HTTP 200、`ok=true`、上游 HTTP 200，`choices` 为 1 项、原始与解析后的 `finish_reason` 均为 `stop`，`message.content` 存在、字符长度 2、解析后非空；接口耗时 **0.76 秒**。API Key 输入框保持空白，未保存回复原文。
- 首次浏览器脚本在上传文件的转发环节超时；只读核查显示当时独立实例**没有收到上传、没有创建任务**。沿用已通过的连接结果，在同一实例通过浏览器原生转发上传三份公开/模拟资料，**没有重发连接测试**。此观察环节故障不计作模型或任务失败。

### 单次 Live 运行

任务 `051451dc-1226-4e06-a34d-8ce1da31ab66`；新建任务请求 1 次，`mode=live`，仅使用 `suppliers_simulated.csv`、`business_brief.txt` 和 `public_source_note.txt`，不使用预选 Demo 资料。总耗时 **242.61 秒**；五阶段均取得真实 `deepseek-flash` 的 HTTP 200/`stop` 响应。运行中曾中断聊天观察，恢复后继续查询的是**同一任务**，没有新建或重跑任务。

| 阶段 | 最终状态 | 阶段耗时 | 上游请求 | 执行器恢复 |
| --- | --- | ---: | ---: | --- |
| Planner | completed | 10.94s | 1 | 0 |
| Research | completed | 51.30s | 1 | 0 |
| Analyst | completed | 33.92s | 1 | 0 |
| Risk Reviewer | completed | 96.65s | 2 | 1 次，首次 `INVALID_OUTPUT / invalid_json` |
| Action | 输出完成，waiting_approval | 49.81s | 1 | 0 |

Reviewer 第一次上游请求 HTTP 200/`stop`，但正文未通过现有 JSON 校验；等待约 1 秒后，既有执行器进行一次修正请求并通过。没有第三次 Reviewer 请求，未放宽 Schema，也没有把首次失败称为网络故障。各阶段记录的 `attempts` 为 1/1/1/2/1，`retry_attempt` 为 0/0/0/1/0；`agent.retrying` 事件 1 条。被动上游观察共记录 **7 次模型请求：连接 1、Live 6**；Live 各请求依次为 Planner、Research、Analyst、Reviewer 两次、Action。未观察到额外 SDK HTTP 恢复请求。可观察到的 Live 响应用量为输入 106083、输出 51191、合计 **157274 tokens**；连接响应另计 69 tokens，不作为 Live 用量。

### 报告、门禁与边界

- 最终 `status=waiting_approval`，`run.report` 存在且报告页预览可见；报告接口 HTTP 200，可取得本次 **164532 字节** Markdown。浏览器自动化中的一次下载 `saveAs` 被取消，因此不将“浏览器下载成功”列为本次通过项；已从相同报告接口将副本保存到本地受限权限的 `/tmp/sentinelai-final-attempt-051451dc-report.md`。报告生成和接口可用已分别确认。
- Reviewer 业务判断 `needs_evidence`，7 项建议均为 `needs_evidence`，批准按钮 7/7 禁用，审批审计条目 0；未执行批准、采购或其他外部行动。**无 Demo/Replay fallback**，无任务失败或自动新建第二个任务。此结论只代表五阶段技术链与最终报告交付成功，不代表业务证据已充分。
- 本轮没有修改业务代码、模型、Prompt、Schema、timeout/retry、API Key 或 Git；没有保存认证头、请求正文或模型原始响应到观察记录。历史失败与本次成功保留为不同轮次。验收结束后停止，不继续发起请求或自动修复。
