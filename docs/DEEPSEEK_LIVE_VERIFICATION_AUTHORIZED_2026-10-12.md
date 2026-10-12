# SentinelAI：授权复用 CC Switch 的受控 Live 验证

日期：2026-10-12（Asia/Shanghai）。写入前确认本报告不存在，未覆盖此前报告。用户明确允许读取 CC Switch 后，仅使用现有桥接脚本读取唯一的 Deepseek 服务。没有读取其他服务凭据、改写配置或保存密钥。

## 总体结论

**现有 DeepSeek 配置可用，最小连通性测试成功；完整 Live 工作流失败，已在 Planner 截断处停止。** 本轮真实模型请求总计 **2 次**：最小请求 1 次，工作流 Planner 请求 1 次。无并发、无自动重试、无失败后再次调用。

## 配置来源与执行方式

- 来源：本机 CC Switch 中名为 Deepseek 的现有服务，脚本只读该条目；凭据存在、配置加载成功，没有与已有项目模型配置冲突。
- 请求及响应模型：`deepseek-flash`。
- 服务域名：`api.deepseek.com`；客户端按现有条目配置的 Base URL 调用 `/chat/completions`，没有改变该地址。
- CC Switch 条目的协议标注为 responses，但项目实际执行 OpenAI-compatible Chat Completions；本次响应 HTTP 200 确认此请求路径可用。
- 凭据仅在子进程内存中通过已有 OPENAI_API_KEY 等变量传给后端客户端，未写到 .env、代码、前端、日志、文档或报告。
- 工作流使用现有 AutoGen 0.7.5 AssistantAgent 和固定串行执行器，mode=live。应用重试仅在受控子进程设为 0，SDK 本身重试为 0；未改变持久配置。当前单次输出上限 1800，请求超时 45 秒，总任务上限 300 秒，保守 token 预留 120000。

## 最小连通性测试

实际命令：`sh scripts/deepseek.sh probe`，退出码 0。

| 字段 | 实际结果 |
| --- | --- |
| HTTP 状态 | 200 |
| 实际响应模型 | deepseek-flash |
| 结果验证 | SENTINELAI_DEEPSEEK_OK 精确匹配 |
| 耗时 | 1.080 秒 |
| finish_reason | stop |
| tokens | prompt 48 / completion 31 / total 79 |
| 推理 tokens | 20（包含在 completion 内） |
| 模型请求次数 / 重试 | 1 / 0 |

仅记录非敏感响应元数据及标记是否匹配，没有保留完整请求、响应文本或认证头。

## 完整工作流实际执行结果

实际命令：`sh scripts/deepseek.sh workflow`，退出码 1。

任务 ID：`99986c5b-361b-44f2-8d99-3173a704b941`。输入为项目内明确标记的 suppliers.csv 与 brief.txt 演示资料。任务总耗时 12.86 秒，状态 failed，模式保持 live，完整报告未生成。

| 阶段 | 状态 | 模型请求次数 | 阶段耗时 | HTTP | finish_reason | 实际响应模型 |
| --- | --- | --- | --- | --- | --- | --- |
| Planner | 失败，输出截断 | 1 | 12.67 秒 | 200 | length | deepseek-flash |
| Research | queued，未执行 | 0 | 不适用 | 不适用 | 不适用 | 无调用 |
| Analyst | queued，未执行 | 0 | 不适用 | 不适用 | 不适用 | 无调用 |
| Risk Reviewer | queued，未执行 | 0 | 不适用 | 不适用 | 不适用 | 无调用 |
| Action | queued，未执行 | 0 | 不适用 | 不适用 | 不适用 | 无调用 |

Planner 网络请求耗时 12.585 秒；prompt_tokens=3593、completion_tokens=1800、total_tokens=5393。其中 reasoning_tokens=1735，包含在 completion_tokens 内，非推理部分仅剩 65 tokens。

执行器错误（不含原始响应内容）：

```json
{
  "code": "INVALID_OUTPUT",
  "reason": "truncated_response",
  "retryable": true,
  "schema_issues": []
}
```

retryable 是错误分类元数据，**本次没有执行重试**。Planner 只执行一次。后端检测 length 后拒绝将响应认定为有效结果，task.failed；未补齐 JSON、伪造计划、跳过 Reviewer、生成成功报告或切换 Demo。

本次证据索引建立 14 条；Planner 输入 previous_outputs 与传入对象一致（首阶段上游为空）。由于 Planner 截断，后续阶段数据传递、Reviewer 在线审查及在线报告生成均未验证。审批操作数为 0，没有操作现有用户审批历史。

## 最有证据支持的根因

**已证实：模型响应达到当前 1800 输出 token 限制，finish_reason=length，推理占用了其中 1735 tokens，最终输出被截断。** 这是当前模型推理量与输出上限不匹配的问题，不是本次认证错误、模型不存在、网络中断、限流、5xx 或静默降级。

本轮已经捕获真实 HTTP 状态、模型与完成原因，比历史 INVALID_OUTPUT 记录更明确。但不能由本次结果倒推出此前那次响应的所有细节，也不能排除解除截断后还会出现其他 Schema 或 Reviewer 问题。本次没有检查截断文本内容，不将 Schema 完整性猜测当作已确认。

## 修改范围与必要下一步

只新增本脱敏报告；没有修改代码、密钥、Base URL、模型、.env、持久配置或用户数据，没有初始化 Git、提交、推送、部署。没有重新运行模型、离线测试或构建：本轮目标是一次真实验证，不是自动修复循环。

建议下一步先由用户选择并授权一个最小参数方案：保持现有密钥/模型，在独立验收进程中适度增加 MODEL_MAX_OUTPUT_TOKENS；或者在服务明确支持且验证过的前提下减少推理输出。不要仅为通过而放宽 Schema 或跳过 Reviewer。即使增加输出，仍可能不足或触发超时，须保持每阶段一次、首错停止，不能保证完整工作流成功。

最终状态：**基础模型连通性本轮通过；完整五阶段 Live 本轮失败；Git 未创建。**
