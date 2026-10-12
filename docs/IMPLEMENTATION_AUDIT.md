# SentinelAI 2.0 实施审计

审计日期：2026-10-11。依据实际源文件、安装版本、接口和测试结果；不是仅依据 README。

## 基线

- FastAPI 入口 `backend/app/main.py`；文档解析 `documents.py`；五阶段编排与报告 `workflow.py`。
- 已安装 FastAPI 0.143.0、Uvicorn 0.54.0、pypdf 6.20.0、AutoGen AgentChat/Ext/Core 0.7.5。保持核心依赖，不升级。
- React 19、Vite 6、lucide-react、react-markdown；入口 `frontend/src/main.jsx`，没有路由库、图表库或组件框架；导航为 React state，CSS 在 `style.css`。
- `OPENAI_API_KEY` 和 `OPENAI_MODEL` 环境变量直接用于 `OpenAIChatCompletionClient`；没有 Base URL、超时、重试、输出预算的统一层。
- 现场检查仅报告凭据是否存在，没有输出密钥。当前环境没有 API Key，根目录和 backend 目录都没有 `.env`；不进行在线调用。

## 实际 Agent 实现

Planner/Research/Analyst/Risk/Action 在 live 模式分别创建独立 `AssistantAgent`，共享模型客户端。任务文本包含原始资料和前序 Markdown。demo 模式使用 Python 计算 CSV 指标和固定规则模板，含固定延迟；Replay 仅在测试中替换模型客户端。自由文本输出无结构校验、证据 ID 或审查门禁。

## API 与事件

已有 GET health/bootstrap、POST files/runs、GET runs/{id}、GET runs/{id}/report。文档、历史仅在内存；750ms 前端轮询；无 SSE。失败终止后续 Agent，但原始异常文本可能暴露服务细节。上传限制 10 MB/12 文件，解析 2000 CSV 行、40000 字符；PDF 无 OCR。CSV 数值未检查有限值和合法区间。

## 复用与保护

复用现有上传路径、PDF/CSV/TXT 解析、CSV 指标、Agent 角色、下载路由、React/Markdown/Lucide、Vite 代理。保留旧 API 核心字段 `agents[].output`、`report` 和文件解析返回契约，新增字段采用增量扩展。不能覆盖用户凭据、Demo 原始文件、用户资料，也不能为视觉改动破坏上传与下载。V1 源码保护快照：`/tmp/sentinelai-v1-baseline.tar.gz`（不含密钥）。

## 实测基线

- `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`：10/10 通过。
- `npm run build`：通过（1741 modules，构建 1.37s）。
- `GET /api/health`：ok，模型未配置。
- 原有 Playwright desktop/mobile 冒烟：总览、五阶段、报告预览/下载、手机上传/导航/工作流通过。

## 已知问题与实施顺序

1. 新增配置/结构契约/证据与输出验证；保持 AutoGen 0.7.5。
2. 固定串行编排升级为预算约束、有限重试、保留失败事件、显式 demo/live/replay。
3. 新增 SSE 补发、重试新任务、幂等提交与并发限制；进程级恢复，不承诺跨重启恢复。
4. 审查及行动落为结构化报告/人工审批；本机审批凭短期会话和服务端角色，非完整企业身份系统。
5. 在现有 React app 升级七个真实页面、深色工作台/浅色报告及手机纵向链路。
6. 离线测试涵盖模式、模型异常、结构错误、事件、证据和审批；在线验收仅在明确配置凭据后单独执行。
