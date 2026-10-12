# SentinelAI 2.0 最终提交前验收

验收日期：2026-10-12（Asia/Shanghai）
项目：`/Users/pengxuezhi/Documents/chuanhua/`
范围：只验收。没有修改业务代码、测试源码、核心架构、配置或密钥，没有删除用户数据。本报告是本轮唯一新增的项目文件；生产构建更新了生成目录，测试产生临时截图及缓存。

## 已验证通过

### 文档与接入方式

已阅读 `docs/MODEL_SETUP.md`、`docs/TEST_RESULTS.md`、`docs/DEMO_SCRIPT.md`，并与配置层、模型测试入口及测试实现核对。

现有路径是 AutoGen 0.7.5 + OpenAI-compatible Chat Completions。读取优先级为进程环境、根目录 `.env`、`backend/.env`，不覆盖已有变量。原记录为 31 项离线测试和浏览器冒烟通过、在线验收未执行。本轮重新运行测试，未沿用旧记录充当新结果。

### 本轮实际命令与结果

| 检查 | 命令/入口 | 实际结果 |
| --- | --- | --- |
| 配置是否存在 | 通过 `ModelConfig.load()` 仅输出布尔值 | 根 `.env` 不存在；backend `.env` 不存在；有效凭据不存在；配置未就绪 |
| 现有后端健康 | `GET http://127.0.0.1:8000/api/health`，只输出选定状态字段 | HTTP 200，status=ok，running_service_configured=false |
| 后端自动化 | `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v` | Ran 31 tests in 7.273s；OK；0 项失败 |
| 前端生产构建 | 在 frontend 执行 `npm run build` | Vite 6.4.4；1743 modules transformed；built in 1.39s；退出码 0 |
| 浏览器冒烟 | 执行现有 `frontend/tests/smoke.mjs`，内存中仅替换测试端口/导入包装，断言未改 | 退出码 0；以下各流程通过 |
| 未配置 Live 阻止 | 隔离服务 POST `/api/runs`，mode=live | HTTP 400：请先配置 OPENAI_API_KEY 再启用 AutoGen 模式；新增任务数 0 |

浏览器实测通过项：1440px 总览、五阶段 Demo、报告预览与 Markdown 下载、证据搜索、后端审批、历史与配置、Replay 任务及报告标识、390px 上传/导航/纵向工作流、手机端证据/报告/审批/历史/配置无整页横向溢出、SSE offline→online 恢复终态且没有重复事件。

浏览器脚本会操作审批和上传，因此本轮启用独立的 FastAPI 18000 / Vite 15173 测试实例。临时 Vite 代理将测试 Origin 规范为应用既有允许值，未改生产 CORS/权限代码。原 8000/5173 服务未重启、未执行浏览器写操作。浏览器通过结果对应隔离实例，不代表已重新验收原实例中任意历史用户数据。

### Live 失败不回退

除现有超时、认证、5xx、429 和无效 JSON 测试外，额外执行了一次离线超时故障注入，并将 Demo 执行器替换为“被调用即失败”的观察器。输出：

```json
{
  "test_kind": "offline injected timeout, no online request",
  "mode": "live",
  "status": "failed",
  "error_code": "MODEL_TIMEOUT",
  "report_present": false,
  "demo_calls": 0,
  "stages": [
    {"id": "planner", "status": "failed"},
    {"id": "research", "status": "queued"},
    {"id": "analyst", "status": "queued"},
    {"id": "risk", "status": "queued"},
    {"id": "action", "status": "queued"}
  ],
  "last_event": "task.failed"
}
```

这验证了离线注入失败条件下没有静默回退。它不是在线服务调用结果，也不是对所有供应商故障组合的穷尽证明。

## 未验证或被阻塞

- 当前有效 API 凭据不存在，运行中后端也未配置模型。
- 按要求跳过最小真实调用，在线请求数为 0。没有在线成功结果、实际使用模型或在线耗时可记录；未收到远端错误响应。
- 因未满足“最小真实调用成功”的前提，未发起完整 Live 工作流。Planner、Research、Analyst、Risk Reviewer、Action 的在线执行情况均未验证。
- 在线认证、网络可达性、所选模型的 JSON 兼容性、实际延迟、真实用量及完整 Live 预算是否足够，仍需真实验收。
- 未创建或修改 `.env`，未输出、复制或记录密钥。

## 发现的问题

1. **提交阻塞：缺少在线验收凭据与结果。** 现有测试通过不足以证明真实在线推理成功。最小行动是由用户安全配置有效 OPENAI_API_KEY，并确认 OPENAI_MODEL/OPENAI_BASE_URL 与服务一致，然后单独验收；不需要重构。
2. **现有冒烟测试绑定固定端口并操作审批。** 脚本使用 5173 且按列表首项定位审批，直接对共享实例执行可能影响既有记录。本轮通过临时隔离服务避免此风险。最小改进建议为测试支持独立 BASE_URL 并按本次任务 ID 定位审批；本轮未修改，需确认后再做。
3. **版本提交准备无法通过 Git 核验。** `git status --short` 返回退出码 128：not a git repository。当前可验收文件与运行结果，但不能确认已提交、分支或工作区差异。若参赛要求 Git 仓库链接，需要另行初始化/关联仓库；本轮未执行。

本轮没有观察到自动化测试或生产构建失败。已知产品边界仍是进程内存存储、本机 Reviewer 会话、无生产多租户与外部执行；这些不计为本轮新增回归，但不能描述为完整生产能力。

## 是否达到提交条件

- **Demo/Replay 展示：通过本轮验收。** 文件上传、五阶段展示、证据、报告、审批和移动端都有本次运行结果支持。
- **以“完成真实多 Agent 在线推理”的标准提交：尚未达到。** 必需的最小在线调用和完整 Live 五阶段验收被凭据缺失阻塞。
- **总判定：有条件通过演示验收，最终 Live 提交门禁暂不通过。** 不将代码存在、Replay 或 mocked 客户端结果认定为在线验收。

## 下一步最小行动

1. 用户通过项目已有安全配置入口设置有效 OPENAI_API_KEY，并确认模型与服务地址。不要把密钥粘贴到聊天或报告。
2. 当前服务配置为空；如采用环境或 `.env` 配置，需在合适时机重启加载。项目数据在内存，重启会丢失当前运行记录与上传内容，请先保留所需资料；本轮未重启原服务。
3. 按现有 `/api/model/test` 入口仅做一次最小真实调用，记录模式、模型、成功/失败、耗时和脱敏错误。
4. 仅该调用成功后，使用明确标记的 Demo 输入执行一次 mode=live 完整链路，逐项记录五个 Agent 的状态、耗时、模型、用量（如服务提供）及报告/审批终态。
5. 如发现失败，先提交分类原因和最小修复建议，经确认后再改代码。无需重复开发已经通过的页面和架构。
