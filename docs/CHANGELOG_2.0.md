# 2.0 修改清单与剩余项

## 修改文件

- `backend/app/main.py`：配置状态/API、SSE、幂等和并发、本机会话审批、重跑、生命周期清理。
- `backend/app/workflow.py`：沿用五个角色/规则 Demo/指标，移交新版执行器并过滤非法数值。
- `backend/app/documents.py`：保留解析接口，新增 CSV 行列与二进制内容校验。
- `backend/app/config.py`（新增）：统一服务端配置、客户端创建、错误分类与脱敏。
- `backend/app/contracts.py`（新增）：Agent/Claim/Risk/Action 的严格结构契约。
- `backend/app/evidence.py`（新增）：来源定位、指标/假设证据、引用/数值校验。
- `backend/app/events.py`（新增）：不可变 payload 编号事件。
- `backend/app/engine.py`（新增）：五阶段执行、模式、预算、重试、Reviewer 门禁、报告与审批建议。
- `backend/tests/test_app.py`：保留原测试场景，适配 JSON 契约和 waiting_approval 终态。
- `backend/tests/test_v2.py`（新增）：离线配置/异常/事件/审批/预算/重跑测试。
- `backend/.env.example`、`backend/requirements.txt`：新增配置说明和显式声明已安装的 python-dotenv，核心依赖未升级。
- `frontend/src/main.jsx`：七页导航、SSE、连接/模式/任务状态、指标与工作流、提交保护。
- `frontend/src/cockpit.jsx`（新增）：风险矩阵、证据、审批、历史、设置、报告洞察与事件时间线。
- `frontend/src/cockpit.css`（新增）：深色工作台、浅色报告、手机纵向执行链。
- `frontend/tests/smoke.mjs`：增加 2.0 页面、审批、Replay 与 SSE 断网恢复；保留桌面/手机上传报告测试。
- `README.md`、`docs/IMPLEMENTATION_AUDIT.md`、`ARCHITECTURE_2.0.md`、`MODEL_SETUP.md`、`DEMO_SCRIPT.md`、`TEST_RESULTS.md`：架构、操作、限制与实测记录。

没有改写真实 `.env`、用户密钥或 Demo 原始资料；未创建替代仓库或升级 AutoGen。

## 完成与待验收

可运行 2.0 MVP 已具备显式模式、结构化五阶段链、证据校验、SSE 重连、专业页面和人工审查。没有真实凭据，在线模型调用尚未验收；需要用户安全配置并主动执行连接测试/Live 任务。

最终离线回归：31/31 后端测试通过，前端构建通过；Playwright 完成桌面和移动端七页导航、上传、报告下载、审批、Replay 标识与断网重连。以上均非在线模型验收。

未实现跨重启持久化、多租户/SSO、外部检索或执行、OCR、CSV 跨源合并、完整文档覆盖和多期趋势。数值契约能校验声明值，但无法证明全部自由文字的语义支持；Reviewer 与业务负责人仍需复核。审批权限仅本机 MVP，不能作为生产身份系统。
