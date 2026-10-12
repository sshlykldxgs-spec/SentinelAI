# SentinelAI Release Freeze — Git 提交准备检查

日期：2026-10-12（Asia/Shanghai）。本轮仅检查 Git 状态、候选提交内容、忽略规则和展示文档，并新增本报告。未暂存、取消暂存、删除、移动或修改既有文件；未执行 commit/push、真实模型请求、服务重启或业务代码修改。

**结论：应用版本已 FINAL RELEASE VERIFIED；当前 Git 暂存内容尚未达到直接 commit 条件。** 需要整理提交范围、将已验收的工作区版本纳入暂存，并处理展示资料中的过时说明。这里的提交准备未通过不撤销技术验收结果，也不要求修改已冻结的运行逻辑。

## 1. 当前 Git 状态

`git status` 确认分支为 **main**，**No commits yet**。本报告创建前：

| 集合 | 数量 | 状态 |
| --- | ---: | --- |
| 已暂存 | 72 | 全部为新增文件 A；其中 7 个文件的工作区又有更新 |
| 未暂存修改 | 7 | 暂存 blob 与当前工作区版本不同 |
| 未跟踪普通文件 | 14 | 包含新增测试和完整 evaluation 目录 |
| 工作区候选文件 | 86 | 72 个已跟踪路径的当前内容，加 14 个未跟踪文件 |

已暂存清单按目录如下，当前准确名单可由只读 `git diff --cached --name-status` 查看：

| 暂存分组 | 数量 | 内容 |
| --- | ---: | --- |
| 根目录 | 2 | `.gitignore`、`README.md` |
| `backend/` | 23 | `.env.example`、requirements、全部当前已跟踪 app 模块及 9 份测试文件 |
| `frontend/` | 11 | HTML、package.json、锁文件、Vite 配置、src 文件及 3 份原有浏览器测试 |
| `scripts/` | 1 | `deepseek.sh` |
| `demo/` | 2 | `brief.txt`、`suppliers.csv` |
| `docs/` | 29 | 架构、配置、演示与历史验收报告；不含未跟踪的 evaluation 文件 |
| `blackbox_case_2026-10-12/` | 4 | 三份案例输入、一份下载报告；建议移出暂存 |

7 个未暂存修改：

- `README.md`
- `backend/app/config.py`
- `backend/app/main.py`
- `docs/MODEL_SETUP.md`
- `frontend/src/cockpit.css`
- `frontend/src/cockpit.jsx`
- `frontend/src/main.jsx`

14 个未跟踪文件（报告生成前）：

- `backend/tests/test_model_config_ui.py`
- `frontend/tests/model-config-ui.mjs`
- `frontend/tests/model-connection-offline.mjs`
- `docs/FINAL_BLACKBOX_RELEASE_TEST.md`
- `docs/GIT_PRECOMMIT_CHECK.md`
- `docs/MODEL_CONFIG_INTERFACE_LOAD_REPORT.md`
- `docs/MODEL_CONFIG_UI_REPORT.md`
- `docs/evaluation/ACTION_TIMEOUT_DIAGNOSIS.md`
- `docs/evaluation/FINAL_BLACKBOX_RELEASE_TEST.md`
- `docs/evaluation/FINAL_RELEASE_VERIFICATION.md`
- `docs/evaluation/MODEL_CONNECTION_RUNTIME_DIAGNOSIS.md`
- `docs/evaluation/MODEL_CONNECTION_SECOND_DIAGNOSIS.md`
- `docs/evaluation/MODEL_CONNECTION_TEST_DIAGNOSIS.md`
- `docs/evaluation/MODEL_CONNECTION_TEST_FIX_REPORT.md`

本报告新增后，未跟踪文件应为 15 个；不会自动进入暂存区。当前暂存版本缺少最新模型配置入口、连接判定与诊断等修改，**直接提交当前索引不能代表已经验收的版本**。后续应暂存这些现成修改，不要还原工作区去匹配旧索引。

检查时索引条目（`git ls-files --stage -z`）SHA-256：`8bca2bc8ba8fd3107a5b2bb081838feb8966a752f1c21c084771dcfba0f80b33`，用于本轮确认索引未变，不是提交 ID。

## 2. 安全扫描结果

分别读取 **72 个实际暂存 blob（788685 字节）**和 **86 个工作区候选文件（884312 字节）**。扫描对象包含旧暂存内容，不能用工作区扫描替代索引扫描。全部可读、UTF-8 文本，无二进制文件或符号链接读取失败。

检查常见模型密钥、GitHub/Slack/HF Token、AWS access key、JWT、私钥、凭据 URL/查询参数、Bearer 字面值、密码/密钥赋值及敏感路径。只输出路径、行号和分类，不输出候选凭据原文。结果：

| 项目 | 本轮结果 |
| --- | --- |
| 已确认真实 API Key、访问 Token、密码、私钥 | 未发现 |
| 实际 `.env` 或认证配置进入候选集合 | 未发现；仅 `backend/.env.example`，Key 是占位符 |
| 依赖、构建、Python 缓存、私有日志/数据库进入索引或未跟踪候选 | 未发现 |
| 离线夹具/占位符模式 | 索引 22 处、工作区 25 处自动识别；不是生产凭据 |
| 其他模式候选 | 人工复核后均为代码构造或测试数据，见下文 |
| 不符合提交范围的业务案例/生成报告 | 5 个已暂存路径，必须处理，见第 4 节 |

其他候选的具体分类：`backend/tests/test_v2.py:250` 是 `test_config_and_redaction` 中的脱敏测试夹具；`scripts/deepseek.sh:70` 从配置对象构造 Authorization，未硬编码真实 Key；旧暂存 `backend/app/config.py:115` 从 `os.getenv` 读取值；`backend/tests/test_model_config_ui.py:92` 是无效地址/凭据回显防护用的离线 canary URL。`.env.example:3` 为明确占位符。模型输出 Token 数量不是访问凭据。

这是提交内容的模式扫描与候选复核，**不是全仓库漏洞审计，也不保证发现所有未知格式秘密**。本轮未读取外部 CC Switch 密钥进行逐字比对；旧安全报告中的已知密钥比对不能称为本轮执行。未扫描忽略目录的依赖全文、工作区外私人日志或远端仓库历史。首次 commit 后的历史对象目前不存在。

本地路径检查：部分文档引用 `/tmp/` 观察文件，说明运行产物留在仓库外，不表示这些文件已暂存。`docs/FINAL_ACCEPTANCE_2026-10-12.md` 和 `docs/GIT_PRECOMMIT_CHECK.md` 含个人主目录绝对路径，建议展示版本改成仓库相对路径，或作为历史资料单独归档；本轮未改动。浏览器测试中的 `/tmp/` 截图输出路径不是私人日志内容或真实凭据。

## 3. 建议提交文件与展示资料

保留并在后续整理时选取**当前工作区版本**：`.gitignore`、README、`backend/app/`、`backend/requirements.txt`、`backend/.env.example`、`backend/tests/`、`frontend/src/`、HTML、package.json、package-lock.json、Vite 配置与浏览器测试。`scripts/deepseek.sh` 可作为可选本机工具保留，不包含真实凭据；评委标准启动不依赖 CC Switch。

**保留 `demo/brief.txt`、`demo/suppliers.csv`。** 它们是产品内置 Demo 示例，`backend/app/main.py` 的 `DEMO_FILES` 和启动 bootstrap 直接读取它们，不是本轮要排除的临时黑盒案例。排除这两份文件会破坏当前已验收的默认启动流程。

保留 `docs/ARCHITECTURE_2.0.md`、`docs/MODEL_SETUP.md`、`docs/DEMO_SCRIPT.md` 及必要说明。以 `docs/evaluation/` 为评委验收资料入口，所需文件目前位置如下：

| 期望展示名 | 现有文件 | 建议 |
| --- | --- | --- |
| `FINAL_RELEASE_VERIFICATION.md` | `docs/evaluation/FINAL_RELEASE_VERIFICATION.md` | 保留并纳入后续暂存；Final Attempt 是最新有效结论 |
| `FINAL_LIVE_ACCEPTANCE_REPORT.md` | `docs/FINAL_LIVE_ACCEPTANCE_REPORT.md` | 保留历史成功证据；可在 evaluation 建相对链接入口 |
| `FINAL_BLACKBOX_ACCEPTANCE.md` | `docs/FINAL_BLACKBOX_ACCEPTANCE.md` | 保留并链接；区分历史任务与本次 Final Attempt |
| `MODEL_CONFIG_UI_REPORT.md` | `docs/MODEL_CONFIG_UI_REPORT.md` | 保留历史记录；展示入口注明后续 marker 修复和诊断报告 |
| `STABILITY_OPTIMIZATION_REPORT.md` | `docs/STABILITY_OPTIMIZATION_REPORT.md` | 保留历史优化记录；同时链接 `docs/RETRY_RESTORE_REPORT.md` 和最新验收 |
| `SECURITY_SCAN_REPORT.md` | `docs/FINAL_SECURITY_SCAN_REPORT.md` | 可在 evaluation 建同名入口，注明旧扫描时间/范围并链接本次提交扫描 |

除第一项外，其余五个要求的文件名目前**不在 `docs/evaluation/` 下**。建议增加短索引/相对链接文档集中展示，保留既有报告原位，避免移动造成链接失效或复制一整套易过时副本。本轮没有创建这些入口、复制、移动或删除历史报告。

重复/过时资料的处理建议：

- 文档 SHA-256 对比未发现完全相同的文件。`docs/FINAL_BLACKBOX_RELEASE_TEST.md` 与 `docs/evaluation/FINAL_BLACKBOX_RELEASE_TEST.md` 同名但内容不同，不可按重复文件自动删除。
- evaluation 下的 `FINAL_BLACKBOX_RELEASE_TEST.md` 已被 `ACTION_TIMEOUT_DIAGNOSIS.md` 指出混用了不同任务记录；建议保留更正说明，将错误报告明确标为历史、不得用于当前验收结论。
- `MODEL_CONFIG_UI_REPORT.md` 仍描述精确 OK 校验；`STABILITY_OPTIMIZATION_REPORT.md` 仍描述旧 SDK/Schema 重试策略；旧安全报告仍写“无 Git、前端不是密钥入口”。它们都是时间点记录，不应直接改写成当前实现说明。
- `FINAL_RELEASE_VERIFICATION.md` 将最新成功章节追加在旧失败之后，建议展示入口直接定位 Final Attempt，或在顶部加简短最新状态索引，不删除失败历史。
- `docs/FINAL_SUBMISSION_CHECKLIST.md`、早期 `DEEPSEEK_*` 及 `TEST_RESULTS.md` 不作为当前放行依据；建议归档分类或标明历史时点，避免评委将旧失败误认成当前状态。

### README 检查

| 必需内容 | 当前覆盖 |
| --- | --- |
| 项目介绍 | 第 3–5 行 |
| 架构说明 | 五阶段与架构图，第 7–34 行 |
| 启动方式 | Python/Node 版本、后端/前端命令，第 44–61 行 |
| 模型配置 | 工作台配置与环境变量方式，第 63–77 行；UI 说明尚未暂存 |
| Demo/Live 区别 | 第 36–40 行，同时解释 Replay |
| 评委如何运行 | 第 42、61 行及演示路线 |
| API Key 说明 | 使用评委自己的 Key，不提交真实凭据；内存保存边界 |

无需大幅重写；建议仅做以下文档级校正，**本轮未改 README**：

1. 第 79 行“完整 Live 在 Planner 失败、尚未通过”是旧结论。改为引用最新 Final Attempt：连接与五阶段完成、报告已生成，Reviewer 仍要求补证据；保留早期失败链接为历史。
2. 第 75 行旧按钮名和“Live 按钮不可选”与当前行为不符，应改成“测试连接”和“未配置启动 Live 时提示并转到模型配置”；与第 65 行一致。
3. 第 73 行“更新配置后重启”只适用于环境/本地文件配置，工作台内存保存立即生效；避免引导评委重启后丢失刚保存的内存配置。
4. 第 111 行增加最新验收入口，避免只指向旧测试报告。不把浏览器自动化下载取消改写成已通过。

## 4. 建议排除文件与忽略规则

以下 5 个路径**建议移出暂存，保留本地文件**：

| 路径 | 理由 |
| --- | --- |
| `blackbox_case_2026-10-12/business_brief.txt` | 黑盒模拟业务输入 |
| `blackbox_case_2026-10-12/suppliers_simulated.csv` | 黑盒模拟供应商业务数据 |
| `blackbox_case_2026-10-12/public_source_note.txt` | 与该案例配套的运行输入，整体排除临时案例目录 |
| `blackbox_case_2026-10-12/final_retry_live_report_download.md` | 下载生成的业务报告 |
| `docs/FINAL_LIVE_DECISION_REPORT.md` | 完整业务运行输出，建议保留验收元数据报告而不提交生成正文 |

本次未发现这些文件包含真实密钥，但“不含密钥”不等于满足本轮禁止提交模拟黑盒原始数据的范围要求。移出后历史验收中的文件路径作为本地证据说明保留，展示入口应说明原始业务报告不随代码交付。不要把 `/tmp/` 中的观察 JSON、截图、日志或此次最终 Markdown 副本复制进仓库。

现有 `.gitignore` 已验证覆盖 `.env`、`.env.*`（仅放行 `.env.example`）、虚拟环境、node_modules、dist、Python 缓存、常见日志/数据库/凭据文件和 `tmp/`。当前实际被忽略的目录为 `.venv/`、两处 `__pycache__/`、`frontend/dist/`、`frontend/node_modules/`，没有进入索引。

建议后续追加以下规则，**此处仅建议，未编辑 `.gitignore`**：

```gitignore
/blackbox_case_*/
/docs/FINAL_LIVE_DECISION_REPORT.md
build/
*.jsonl
*.tmp
*.bak
*.swp
```

`build/`、JSONL 与上述临时扩展当前未被通用规则覆盖；在当前候选集合未发现相应产物。不要忽略全部 `*.csv`、`*.txt` 或 `docs/evaluation/`，否则会漏掉 Demo 依赖、requirements 和验收资料。**仅新增 ignore 不会移除已经暂存的 5 个文件**，后续须另行取消其暂存；本轮不执行该操作。

## 5. 是否达到 commit 条件

**当前结论：NOT READY TO COMMIT。应用验收通过，提交集合尚需整理。** 必须在保持业务冻结的前提下完成：

1. 将第 4 节 5 个产物移出暂存并加入针对性忽略规则，文件保留本地。
2. 将第 1 节最新工作区代码/测试及选定文档纳入暂存；不使用旧索引替代已验收版本，也不盲目再次 `git add .`。
3. 完成上述 README 最小文档校正和 evaluation 展示入口，明确历史报告时点及已知错误关联。
4. 对整理后的实际索引重新扫描，确认没有禁止内容、最新冻结版本均已包含、链接指向正确，再由用户决定第一次 commit。

本轮只新增本报告，不自动执行以上建议。之前 102 项离线测试和 Final Attempt 成功是既有验收证据，本轮未重跑测试、构建或 Live。未 commit、未 push、未删除文件。
