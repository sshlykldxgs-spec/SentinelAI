# SentinelAI 2.0 DeepSeek 最小接入与验收

日期：2026-10-12（Asia/Shanghai）

结论：**CC Switch 凭据复用完成，最小真实 Chat Completions 调用通过；完整 Live 工作流在 Planner 阶段失败，尚未通过端到端验收。** 失败后未再发起在线请求，未调整核心代码或输出限制。

## 1. 实际修改文件

- 新增 `scripts/deepseek.sh`：只读 CC Switch 的 Deepseek 服务，将配置注入独立子进程环境；支持 check/probe/workflow/serve。
- 新增本报告 `docs/DEEPSEEK_ACCEPTANCE.md`。
- 前端构建更新 `frontend/dist` 生成内容；未修改前端源码、后端业务代码、测试源码、依赖或原配置。
- 没有创建或覆盖 `.env`，没有保存凭据到源码、前端、文档、报告、Git 或日志。没有切换 CC Switch 服务、操作用户审批历史、提交 Git 或部署生产。

## 2. 配置是否完成

已核对 `docs/MODEL_SETUP.md`、`docs/TEST_RESULTS.md` 和 `backend/app/config.py`、`engine.py`。现有变量为 OPENAI_API_KEY、OPENAI_MODEL、OPENAI_BASE_URL、MODEL_TIMEOUT_SECONDS、MODEL_MAX_RETRIES、MODEL_MAX_OUTPUT_TOKENS、TASK_TIMEOUT_SECONDS、TASK_TOKEN_BUDGET。加载环境变量优先，其次根 `.env`、`backend/.env`，均不覆盖已有值。

CC Switch 中精确名称忽略大小写匹配到唯一 Deepseek 服务，凭据存在。服务域名 `api.deepseek.com`，配置模型 `deepseek-flash`。CC Switch 的服务条目标注 `responses`；项目仍使用 Chat Completions，本次最小请求已实际验证该服务与模型接受此协议。没有修改 CC Switch 的协议设置。

桥接脚本使用 SQLite 只读连接，不输出凭据。它会先加载项目配置，已有模型配置与 CC Switch 不一致时拒绝覆盖；当前没有冲突。凭据仅存在于桥接子进程内存及发送给目标模型服务的认证请求中，不落盘。

可重复使用的入口（命令本身不含凭据）：

```bash
# 仅检查，零模型调用
sh scripts/deepseek.sh check

# 显式单次最小真实调用，会消耗额度
sh scripts/deepseek.sh probe

# 显式一次完整 Live 尝试；本轮已失败，建议确认修复方案后再用
sh scripts/deepseek.sh workflow

# 可选：通过桥接启动独立本地后端；本次未执行
sh scripts/deepseek.sh serve --port 8001
```

该方式不是全局环境配置。原有 8000 后端没有重启，原界面不会自动获得此子进程凭据；普通 uvicorn 启动也不会读取 CC Switch。当前前端代理仍指向 8000。后续若要在原 UI 使用，需在确认内存数据保留方式后，通过桥接启动对应后端，或另行批准最小代理调整。

## 3. 最小真实调用：通过

实际命令：`sh scripts/deepseek.sh probe`，退出码 0。

| 项目 | 实测结果 |
| --- | --- |
| 实际运行模式 | live，真实 HTTPS Chat Completions 请求，非 Replay |
| 请求模型 | deepseek-flash |
| HTTP 状态 | 200 |
| 实际响应 model 字段 | deepseek-flash |
| 要求返回内容 | SENTINELAI_DEEPSEEK_OK |
| 返回内容验证 | 去掉首尾空白后精确匹配 |
| max_tokens | 32 |
| 超时 | 总请求配置 45 秒，连接 10 秒 |
| 自动重试 | 0 |
| 耗时 | 1.123 秒 |
| finish_reason | stop |
| prompt_tokens | 48 |
| completion_tokens | 29（其中 reasoning_tokens=18） |
| total_tokens | 77 |
| 缓存命中 tokens | 0 |

没有输出响应全文、API Key 或 Authorization 头。该结果验证凭据、网络、模型和 Chat Completions 最小协议可用，不代表五阶段结构化输出兼容性通过。

## 4. 完整 Live 工作流：未通过

实际命令：`sh scripts/deepseek.sh workflow`，退出码 1。
使用独立进程内的 suppliers.csv / brief.txt 演示资料，经现有 `run_workflow` / AutoGen AssistantAgent 路径执行。仅在该子进程将执行器重试设为 0，SDK 原本重试为 0；没有修改持久配置。未执行任何审批操作。

任务 ID：`75b7d238-41c5-49b5-942e-b765e8406715`。

| 阶段 | 状态 | 请求次数 | 阶段耗时 | 模型证据 |
| --- | --- | --- | --- | --- |
| Planner | failed | 1 | 12.38 秒 | 请求配置 deepseek-flash；实际响应 model 未捕获 |
| Research | queued，未执行 | 0 | 不适用 | 未调用 |
| Analyst | queued，未执行 | 0 | 不适用 | 未调用 |
| Risk Reviewer | queued，未执行 | 0 | 不适用 | 未调用 |
| Action | queued，未执行 | 0 | 不适用 | 未调用 |

总耗时 12.85 秒；状态 failed；mode 始终为 live；完整报告未生成。已有证据索引 14 条，Reviewer 状态 pending，没有形成审查结论或行动批准。

Planner 返回的 AutoGen 用量：prompt=3499、completion=1800、合计 5299。保守预留预算 12746 / 120000，尚未用尽。没有报告超时或上下文超限错误。此次错误为：

```json
{
  "code": "INVALID_OUTPUT",
  "message": "模型输出未通过结构或证据校验。",
  "retryable": true
}
```

Planner 输入上下文中有 14 条证据，反序列化的 previous_outputs 与传入对象一致（Planner 上游为空）。因在首阶段失败，**本次在线运行没有验证 Research→Analyst→Reviewer→Action 的前序结果传递、证据引用质量、风险审查与报告生成**。现有离线测试覆盖这些路径，但不能替代真实调用验收。

失败保持 live，未回退到 Demo，未伪造成功报告。

### 记录限制

本次工作流观察器挂在 `httpx.AsyncClient.send`；实际安装的 OpenAI SDK 使用 `httpx2`。因此工作流 `actual_http_calls` 记录为空，不能据此声称没有网络调用，也不能补写 HTTP 状态或实际响应模型。Planner 的返回用量与后续结构校验失败证明模型路径取得了响应，但不是响应 model 字段的验证。

原执行器把 JSON 解析错误、字段校验错误及阶段必填校验统一映射为 INVALID_OUTPUT，没有保留脱敏字段错误类型或 finish_reason。故当前无法精确断言失败根因。

## 5. 回归检查

没有修改或削弱原有测试断言。

| 命令 | 实际结果 |
| --- | --- |
| `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v` | Ran 31 tests in 7.284s；OK；退出码 0 |
| frontend 内 `npm run build` | 1743 modules transformed；built in 1.40s；退出码 0 |

测试进程未注入 CC Switch 凭据，没有额外真实模型调用。本轮没有运行会操作审批记录的浏览器冒烟。

## 6. 尚存问题与最小修复建议

1. **Planner 结构化输出失败。** completion_tokens 恰好等于当前 1800 输出上限，且最小调用显示该模型会产生 reasoning tokens，输出截断是合理怀疑，但尚未证实。不能把猜测写为已确认原因。
2. **在线诊断缺失。** 最小修复是仅调整验收观察器适配真实 SDK transport，采集 HTTP 状态、响应 model、finish_reason 和不含输入内容的校验错误类型/字段路径；不记录模型原始请求或密钥。下一次调用前需确认。
3. 若确认 finish_reason=length 或 JSON 被截断，再考虑仅在验收子进程适度增加 MODEL_MAX_OUTPUT_TOKENS，或在服务明确支持的前提下关闭推理；当前不修改模型调用参数、不扩大预算、不盲目重试。
4. 原 UI 后端尚未切换到桥接启动。为保护其内存资料与审批历史，本轮没有重启或更改代理；是否接入原 UI 应在工作流通过后另行确认。

本轮实际在线操作为一次最小请求与一次工作流尝试（Planner 一次模型请求，后续未执行）。最终门禁：最小接入通过，完整 Live 工作流不通过；已按要求在失败后停止在线调用并保留脱敏验收记录，等待确认最小诊断/参数修复方案。
