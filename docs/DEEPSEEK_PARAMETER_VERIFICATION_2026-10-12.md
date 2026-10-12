# DeepSeek 参数调整后的单次 Live 验证

日期：2026-10-12（Asia/Shanghai）。用户授权调整参数；写入前确认目标报告不存在。仅本次独立子进程使用环境变量覆盖输出/超时，未修改真实 .env、CC Switch、密钥、源码或持久配置。

## 调整与执行范围

现有模型仍为 deepseek-flash，服务域名 api.deepseek.com，使用现有 CC Switch Deepseek 只读桥接和项目 Live 执行器。

单阶段输出上限 1800 → 4096 tokens（现有配置层允许的最大值）；请求超时 45 → 90 秒。总任务时限仍为 300 秒，token 预留预算仍为 120000。应用与 SDK 自动重试均为 0，首个失败后停止下游。没有更换模型、密钥、放宽 Schema、跳过 Reviewer或再做连接探针。

实际执行：

```bash
MODEL_MAX_OUTPUT_TOKENS=4096 MODEL_TIMEOUT_SECONDS=90 sh scripts/deepseek.sh workflow
```

退出码 1。只有一次工作流尝试，真实 API 请求共 **2 次**，无重试、无并发、无额外连接探针。审批操作 0，未操作现有用户运行/审批历史。运行 ID：`7fd824ca-f9ed-4b24-b25b-058a23b75bd1`。

## 阶段结果

| 阶段 | 状态 | HTTP | 响应模型 | finish_reason | 阶段耗时 | 输入 / 输出 tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Planner | completed，结构校验通过 | 200 | deepseek-flash | stop | 7.46 秒 | 3575 / 1270 |
| Research | failed，输出截断 | 200 | deepseek-flash | length | 20.26 秒 | 4160 / 4096 |
| Analyst | queued，未执行 | 不适用 | 无调用 | 不适用 | 不适用 | 不适用 |
| Risk Reviewer | queued，未执行 | 不适用 | 无调用 | 不适用 | 不适用 | 不适用 |
| Action | queued，未执行 | 不适用 | 无调用 | 不适用 | 不适用 | 不适用 |

Planner 网络请求耗时 7.385 秒，输出中 reasoning_tokens=619；Research 网络请求耗时 20.256 秒，输出中 reasoning_tokens=4096。总输入 tokens=7735，总输出 tokens=5366，总观察用量 **13101**；推理用量属于输出用量，不再次加到总量。

任务总耗时 27.89 秒，最终 failed，mode=live，报告未生成，Reviewer pending。保守预留 33242 / 120000，未触发预算或超时。

## 可核实证据与失败分类

- Planner 成功完成结构化输出校验，非伪造计划。
- Research 输入包含 14 条证据及前序 Planner 结果；反序列化 previous_outputs 与实际传入对象一致，确认此在线阶段的前序传递正确。
- Research 响应 completion_tokens=4096、reasoning_tokens=4096、finish_reason=length，**已证实是模型输出截断，整个输出配额被推理用量占用**，没有形成可完成验证的结果。
- 后端错误为 INVALID_OUTPUT / truncated_response，retryable 字段只是分类提示，本次没有重试；保持 Live 失败，不补齐 JSON、不转 Demo。
- 不是本次认证、网络、服务 5xx/限流或执行器超时错误。无法断言解除截断后所有下游 Schema、证据与审查都能通过，因为后续阶段未执行。

## 最终判断与最小下一步

**Planner 在线阶段通过；完整五阶段 Live 仍失败。** 提高到当前配置允许的 4096 上限没有解决 Research 推理用量耗尽问题，不建议无证据继续增大配额或循环重跑。

下一步最小行动是先只读核实服务/模型是否支持关闭推理或限制推理预算（例如可用的 thinking 控制参数），再提出与该接口兼容的最小客户端配置方案。该能力未在本轮验证；不能擅自发送猜测参数，也不能换模型或减弱 Schema。采用该方案并重新请求仍需用户授权。

本轮没有改动源码、凭据或持久配置，只新增此脱敏报告；没有初始化 Git、提交、推送或部署，没有删除用户资料。离线 43 项回归和构建的上一轮通过记录仍保留，本轮未重新执行，不能写作本轮新增测试结果。
