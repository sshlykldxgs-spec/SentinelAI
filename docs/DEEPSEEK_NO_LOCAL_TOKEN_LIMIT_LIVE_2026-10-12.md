# SentinelAI：关闭本地 token 上限后的验证

日期：2026-10-12（Asia/Shanghai）。目标文件写入前确认不存在。没有覆盖此前报告，没有重启共享服务、改动真实密钥、代码或持久配置，也没有 Git 初始化、提交、推送或部署。

## 总体结果

**配置与离线回归通过；最小真实测试 HTTP 200，但标记校验因探针自身输出上限截断而未通过。按先探针后工作流的要求，完整 Live 未执行。**

真实模型 API 请求次数 **1**，无重试、无并发、无第二次探测。五个 Agent 均未开始在线执行，未生成任何完整 Live 决策报告。

## 实际配置与最新代码

- 进程在项目配置加载前未设置 MODEL_MAX_OUTPUT_TOKENS、TASK_TOKEN_BUDGET、MODEL_TIMEOUT_SECONDS、MODEL_MAX_RETRIES、TASK_TIMEOUT_SECONDS。
- 根目录 `.env`、`backend/.env` 均不存在。加载优先级是进程环境变量 → 根 `.env` → backend `.env`，不覆盖已有变量。
- `token_limit` 对 0/未设置返回 None；客户端在 max_output_tokens=None 时不发送 max_tokens；执行器在 token_budget=None 时不执行 token 预算拦截。正整数配置仍可生效。
- 新独立进程读取最新代码。共享 8000 后端健康检查 HTTP 200，公开配置 max_output_tokens=null、token_budget=null，尚未配置模型；该共享服务未重启。
- 本轮复用唯一授权的 CC Switch Deepseek 服务，配置完整，无配置冲突。模型 deepseek-flash，服务域名 api.deepseek.com，协议为项目已有 OpenAI-compatible Chat Completions。凭据仅在独立子进程内存中使用，没有保存或回显。
- 受控命令显式设置 MODEL_MAX_OUTPUT_TOKENS=0、TASK_TOKEN_BUDGET=0、MODEL_MAX_RETRIES=0；SDK 自动重试为 0。请求超时 45 秒，总任务时限 300 秒仍有效。Schema/Reviewer 校验不变。
- 候选文件/构建产物已知凭据比对扫描 48 个文件，没有确认的个人凭据命中。

检查到的源码截取操作用于输入证据覆盖范围、错误描述摘要和敏感值脱敏，不裁剪模型最终回答。其他提前终止条件（超时、配置错误、结构/证据校验失败）仍保留。

## 离线回归

实际命令：`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`。

实际结果：**50/50 通过，7.331 秒，失败 0、跳过 0，退出码 0。** 测试确认 0/未设置关闭限制、客户端不发送 max_tokens、显式有限值传递、无限预算 Replay 保留 Reviewer/用量记录、截断或非法输出明确失败。测试不使用真实模型请求。本轮未重新构建前端（未修改代码）；上一轮构建通过不能记作本轮执行。

## 最小真实测试

实际命令：

```bash
MODEL_MAX_OUTPUT_TOKENS=0 TASK_TOKEN_BUDGET=0 MODEL_MAX_RETRIES=0 sh scripts/deepseek.sh probe
```

该命令配置环境的两项 token 限制为关闭，但 **probe 实现独立固定 max_tokens=32**，不使用工作流客户端的 max_output_tokens。此差异在调用前已从源码核对，保留原最小探针以满足复用现有测试要求，本轮没有修改探针。

| 字段 | 实际值 |
| --- | --- |
| HTTP 状态 | 200 |
| 实际响应模型 | deepseek-flash |
| 耗时 | 0.914 秒 |
| finish_reason | length |
| 标记精确匹配 | 否 |
| prompt_tokens | 48 |
| completion_tokens | 32 |
| reasoning_tokens | 22（包含在 completion 内） |
| total_tokens | 80 |
| 调用次数 / 重试 | 1 / 0 |
| 命令退出码 | 1 |

已证实：服务接受请求并返回 HTTP 200，最小响应达到探针主动指定的 32 tokens 上限并截断，未通过标记验收。不是本次认证、连接、429、5xx 或 JSON Schema 工作流解析失败。未采集未经脱敏的响应正文，不输出认证头。

这个截断不能作为“服务商默认输出上限仍为 32”或“工作流还发送 max_tokens”的证据；32 来自探针代码。也不能断言取消工作流 max_tokens 后五阶段会通过，服务方默认输出和上下文限制仍有效。

## 五阶段状态

| 阶段 | 状态 | API 请求数 | HTTP / finish reason / tokens |
| --- | --- | --- | --- |
| Planner | 未执行 | 0 | 不适用 |
| Research | 未执行 | 0 | 不适用 |
| Analyst | 未执行 | 0 | 不适用 |
| Risk Reviewer | 未执行 | 0 | 不适用 |
| Action | 未执行 | 0 | 不适用 |

最小测试未通过，因此没有继续调用 workflow；没有伪造结果、忽略标记匹配、转 Demo/Replay、跳过 Reviewer 或操作审批记录。完整 Live 工作流状态仍为未通过验收，本轮未执行。

## 最小下一步

当前已证实阻塞是最小探针的独立 32-token 上限。建议经授权后仅修正 probe 的输出参数，使其也遵循 MODEL_MAX_OUTPUT_TOKENS=0 的省略语义，或给探针明确足够的有限值；保留精确标记验收及无重试。不能仅看到 HTTP 200 就将探针标为通过。

之后才能按用户既定顺序进行一次新探针，成功后一次五阶段独立工作流。此次没有修改代码或自动再次请求。解除项目主动 max_tokens 参数仍无法解除服务商的默认输出上限、上下文窗口或账户限制。
