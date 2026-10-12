# 模型连接测试与内部严格探针分离：修复报告

日期：2026-10-12（Asia/Shanghai）。本轮仅修复用户连接测试的响应判定与页面反馈；真实模型 API 调用 0 次，未重启现有服务、未运行 Live、未修改密钥或执行 Git 写操作。

## 修复内容

- 用户入口 `POST /api/model/test` 保持一次最小 Chat Completions 请求。请求成功、得到非空文本且 `finish_reason=stop` 即返回成功；不再要求回复精确等于 `OK`。空文本、截断、内容过滤、工具调用和未知结束原因仍返回失败。原有错误分类、请求上限和重试设置保持不变。
- 成功响应返回 `ok`、当前配置的模型名称、耗时及固定的简短摘要“收到非空文本响应并正常结束；五阶段结构化工作流需另行验收。”页面显示这些信息，不显示模型回复正文。摘要不从模型内容截取，避免回显敏感文本。
- `scripts/deepseek.sh probe` 的固定 marker 校验保持原样，继续用于开发验收和自动化测试；没有将它改为宽松判断，也没有执行真实探针。
- 同步更新 `docs/MODEL_SETUP.md` 的连接测试说明。没有修改 Agent、Prompt、Schema、Live 执行链、timeout/retry、模型配置或 API Key。

## 离线验证

- 后端：`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`，99/99 通过。包含非固定文本正常结束成功、空文本和非正常结束失败、单次请求及无正文回显的断言；独立严格探针的 marker 不匹配测试仍通过。全部为 Replay/模拟结果，未连接真实模型。
- 前端：`npm run build` 通过，1743 modules transformed。
- 模型配置页面：`node tests/model-connection-offline.mjs` 在 1440px 和 390px 通过。浏览器拦截所有 `/api/*` 请求；验证模型、耗时、固定摘要、失败提示、Key 清空和无水平溢出，没有请求现有后端或模型服务。
- `git diff --check` 通过。未执行 add、commit、push 或修改仓库配置。

## 验收边界

这是**离线修复验证通过**，不是 Final Release Verification 的真实连接或五阶段 Live 重跑。当前已运行的 8000 后端没有重启，仍使用旧进程加载的连接判定；本轮未用真实密钥测试新代码，也没有把旧验收报告改写为成功结论。按本轮指令到此停止。
