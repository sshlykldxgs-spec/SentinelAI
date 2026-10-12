# SentinelAI 2.0 比赛代码仓库提交前清单

检查日期：2026-10-12（Asia/Shanghai）。仅提交代码仓库，**不提供独立在线演示链接**。评委从仓库本地启动；不要提交真实密钥或宣称未通过的在线流程已经通过。

## 1. 实际验证结果

| 项目 | 本轮实测 |
| --- | --- |
| 项目是否为 Git 仓库 | 否；`git rev-parse --is-inside-work-tree` 退出码 128，提示 not a git repository；未初始化、提交或推送 |
| 凭据加载 | `backend/app/config.py` 已从进程环境、根目录 `.env`、`backend/.env` 读取 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_BASE_URL`；环境变量优先，不覆盖现有配置 |
| 无凭据 Demo | 隔离进程中 POST `/api/runs` 返回 201，mode=demo，五阶段执行后状态 `waiting_approval`，已生成报告 |
| 无凭据 Replay | 隔离进程中 POST `/api/runs` 返回 201，mode=replay，五阶段执行后状态 `waiting_approval`，已生成报告；**这不是在线模型推理** |
| 无凭据 Live | `live_available=false`；POST `/api/runs` 返回 400，明确提示先配置 `OPENAI_API_KEY`，未静默降级 |
| CC Switch Deepseek | `sh scripts/deepseek.sh check` 报告配置完整，模型 `deepseek-flash`，未持久化凭据；不会自动启用在评委的普通后端中 |
| 本轮最小真实调用 | `sh scripts/deepseek.sh probe`，HTTP 200，响应模型 `deepseek-flash`，`SENTINELAI_DEEPSEEK_OK` 精确匹配，无重试，耗时 1.034 秒，输入 48 / 输出 29 / 合计 77 tokens |
| 完整 DeepSeek Live | **未通过，且本轮未重跑**。先前一次真实尝试在 Planner 结构化输出校验处失败；其余四阶段未执行、无完整 Live 报告，见 `docs/DEEPSEEK_ACCEPTANCE.md` |
| 后端自动化 | `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`：31/31 通过，7.395 秒，退出码 0 |
| 前端生产构建 | `cd frontend && npm run build`：1743 modules transformed，1.45 秒，退出码 0 |

本轮没有运行会写入审批历史的 Playwright 冒烟；既有验收记录见 `docs/TEST_RESULTS.md`。测试没有削弱断言或改动核心架构。

## 2. 评委快速启动

在**仓库根目录**执行。需要 Python 3.11+、Node.js 20+；如系统 `python3` 版本过低，显式使用 `python3.12`。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

另开终端：

```bash
cd frontend
npm ci
npm run dev
```

在本机打开 `http://127.0.0.1:5173`，API 文档为 `http://127.0.0.1:8000/docs`。初始预选示例 CSV/TXT 和业务问题。默认 **Demo**，无须凭据，启动后查看五阶段、证据、报告和待审批状态。切换 **Replay** 可演示相同链路的离线 AutoGen 回放；不要称为在线模型结果。评委无需安装或导入 CC Switch。

## 3. 评委用自己的密钥尝试 Live

项目沿用 OpenAI-compatible Chat Completions 的变量名，**不新增第二套 DeepSeek 凭据机制**。可在运行后端的终端设置环境变量，也可以在本机执行：

```bash
cp backend/.env.example backend/.env
# 在本机编辑 backend/.env，把 OPENAI_API_KEY 占位符换成自己的密钥。
```

示例文件只含占位符；示例模型为 `deepseek-chat`、地址为 `https://api.deepseek.com/v1`，须按自己使用的服务确认模型和地址。`backend/.env` 不应加入 Git。配置后启动/重启后端、刷新页面，先在配置页**主动**测试连接，再尝试 Live；这些操作会消耗模型额度。服务端拒绝缺失/占位凭据。在线失败保持 Live、标记失败，不会转为 Demo。**完整 Live 五阶段尚未通过验收**，不要作为评委可保证复现的成功演示。

本机已有 CC Switch Deepseek 服务，但仓库默认后端不读取它。`scripts/deepseek.sh` 是可选的本机只读桥接，**不是评委必要安装步骤**。其最小请求已验证 `deepseek-flash` 可用；不代表示例文件里的 `deepseek-chat` 或完整工作流已通过。具体差异见 `docs/MODEL_SETUP.md` 和 `docs/DEEPSEEK_ACCEPTANCE.md`。

## 4. 敏感信息及提交范围

- `.gitignore` 排除 `.env`、`.env.*`（仅放行 `.env.example`）、`.venv/`、`node_modules/`、`dist/`、缓存、日志、SQLite 数据库、私钥及常见凭据文件。
- 本轮候选源文件逐个扫描并与 CC Switch 中实际 Deepseek 凭据在进程内比较，没有发现真实凭据匹配；没有发现待提交范围内的私有日志/数据库/二进制文件。关键词候选为 `.env.example` 占位符和测试假数据，不是实际密钥。扫描只输出统计和路径，不输出值。
- 注意：**当前没有 Git 仓库，无法验证最终 Git 暂存区或提交对象**。创建仓库并选择文件后，须再次执行敏感扫描并审查 `git status` / staged diff；不要依赖 `.gitignore` 掩盖已被跟踪的文件。
- 当前无根目录、backend 或 frontend 的真实 `.env`。不要提交评委自行填写的 `.env`、浏览器下载的报告或本地截图。
- `scripts/deepseek.sh` 只读用户本机 CC Switch 配置，脚本本身不包含密钥；可以提交脚本，但不能提交 CC Switch 数据库或配置备份。

## 5. 已知限制与提交门禁

- Demo/Replay 可作为离线代码仓库评审路径。真实 DeepSeek 最小请求通过，但 Planner 结构化输出失败，不能宣称端到端 Live 五阶段成功。先前 completion 恰好达到 1800 tokens 上限，截断只是未证实的可能原因。
- 上传、任务和审批存放在内存，重启丢失；无生产级多租户身份、外部执行工具或 OCR。审批只代表授权，不会采购/付款/签合同。单期 CSV 不支持真实趋势分析。
- 如果比赛强制要求真实 Live 全链路可复现，当前**未达到该条件**。需要在确认诊断方案后记录脱敏的结构错误类型和完成原因，得到用户许可后再做最小修复及一次新验收；本轮不盲目增加输出长度或在线调用次数。
- 提交前仍需由仓库所有者决定是否初始化 Git、选择远程并提交；本轮没有代为操作。建议最后检查 README 启动命令、锁文件、忽略规则和最终暂存文件列表。
