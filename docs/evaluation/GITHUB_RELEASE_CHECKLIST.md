# SentinelAI 私人 GitHub 仓库发布检查清单

检查日期：2026-10-12（Asia/Shanghai）。本轮仅核对本地 Git、扫描 HEAD 内容并生成本清单；未修改源码、Agent、Prompt、Schema、模型配置、timeout/retry、README 或依赖，未提交、创建 GitHub 仓库、添加 remote 或 push。

## 1. 当前 commit 信息

| 项目 | 实际结果 |
| --- | --- |
| 当前分支 | `main` |
| HEAD | `8db007acdd39e097c4149fcb020554df230f10af` |
| Commit message | `release: finalize SentinelAI evaluation-ready version` |
| 提交时间 | 2026-10-12 10:54:16 +08:00（Asia/Shanghai） |
| 对象类型 | `git cat-file -t` 确认为 commit |
| 历史 | 1 个 root commit，无父提交 |
| 提交文件数 | 84 |
| 发布基准 | 与用户指定的 FINAL RELEASE VERIFIED commit 完全一致 |

技术验收依据为已提交的 [FINAL_RELEASE_VERIFICATION.md](FINAL_RELEASE_VERIFICATION.md) 中 Final Attempt 章节。本轮未重复执行测试、构建或模型请求，也不扩展此前验收范围。

## 2. Git 状态及远程配置

检查开始时 `git status` 显示 `main`，没有已暂存变更或已跟踪文件修改，仅以下文件未跟踪：

```text
docs/evaluation/GIT_FIRST_COMMIT_REPORT.md
```

84 个 HEAD 文件均与工作区对应内容一致。本清单生成后，新增第二个未跟踪文件：

```text
docs/evaluation/GITHUB_RELEASE_CHECKLIST.md
```

因此当前状态是**跟踪文件干净、两份报告未跟踪**，不能称为整个工作区干净。两份报告不在冻结 commit 中，也不会随现有 commit 的 push 自动上传。本轮不暂存它们、不追加提交、不 amend。

`git remote -v` 无输出：**需要添加 GitHub remote。** 本轮未添加，未尝试连接或检查任何 GitHub 仓库，远端是否存在及其可见性均未验证。

## 3. HEAD 安全检查结果

直接读取当前 HEAD 的 84 个 blob，共 661549 字节；扫描对象不是临时工作区副本或历史安全报告。全部为可读取文本，无二进制产物。

| 检查项 | 结果 |
| --- | --- |
| 实际 `.env`、认证配置 | HEAD 中未发现；`backend/.env.example` 仅含占位 Key |
| API Key、访问 Token、密码、私钥 | 未发现已确认真实凭据 |
| 私人日志、JSONL 观察文件、数据库 | HEAD 中未发现 |
| 临时黑盒输入及下载型业务报告 | `blackbox_case_2026-10-12/` 与 `docs/FINAL_LIVE_DECISION_REPORT.md` 不在 HEAD 中 |
| node_modules、虚拟环境、Python 缓存 | HEAD 中未发现 |
| build/dist 与临时文件 | HEAD 中未发现 |
| 内置 Demo | `demo/` 保留，为默认启动必需示例，不是临时黑盒输入 |

扫描覆盖常见模型/API 密钥、GitHub/Slack/HF Token、AWS access key、JWT、私钥、Bearer 字面值、凭据 URL/查询参数、密码/密钥赋值及禁止路径。25 处匹配为离线夹具/占位符；另 3 处经复核为：

- `backend/tests/test_model_config_ui.py:92`：无效 URL/脱敏测试用 canary 查询参数。
- `backend/tests/test_v2.py:250`：`test_config_and_redaction` 内的测试夹具。
- `scripts/deepseek.sh:70`：从运行配置构造 Authorization，并非字面真实 Key。

没有打印或保存敏感候选值，也未读取外部实际密钥作比对。这是指定提交的模式扫描与候选复核，不是对未知格式秘密、第三方依赖或所有软件漏洞的绝对保证。被忽略的本地文件不属于本次上传集合，不能因其存在而误认为已进入 HEAD。

发布前隐私提示：`docs/FINAL_ACCEPTANCE_2026-10-12.md` 和 `docs/GIT_PRECOMMIT_CHECK.md` 含历史本机主目录路径；它们不是已确认凭据泄露。本次提交身份由本机自动推断，GitHub 收到提交后会保留其中的作者/提交者元数据。按冻结约束，本轮不更改这些内容或改写提交。

## 4. GitHub 创建建议（仅建议）

1. 由用户在确认的个人账号下创建空仓库；可用名称 `SentinelAI`，以实际可用性和用户选择为准。
2. 可见性选择 **Private**，创建后再检查一次可见性与仓库所有者。
3. 不勾选初始化 README、`.gitignore` 或 License，避免产生独立初始提交；这些内容已由本地提交管理。
4. 选择 SSH 或 HTTPS 克隆地址。HTTPS 认证使用安全凭据管理方式，勿将密码或 Token 嵌入 remote URL、文档或命令记录。
5. 仓库建立后再单独授权添加 remote 和 push。本轮没有创建仓库或执行任何发布操作。

## 5. Push 前人工确认事项

- [ ] GitHub 仓库归属和名称正确，实际可见性为 Private；协作者权限符合预期。
- [ ] 远程仓库为空；若已有提交，先检查双方历史，不使用强制推送覆盖远端。
- [ ] 本地仍在 `main`，HEAD 仍为 `8db007acdd39e097c4149fcb020554df230f10af`，提交信息与基准相同。
- [ ] 接受当前 commit 中自动推断的作者身份及历史文档中的本机路径信息；如需调整，另行决定，不在本轮改写冻结 commit。
- [ ] 确认两份未跟踪报告不属于当前发布 commit；不要为了纳入它们而未经授权执行 `git add .` 或新提交。
- [ ] 添加 remote 前核实地址无内嵌凭据，且指向目标私人仓库；目前本地没有 remote。
- [ ] 明确授权后仅发布目标 `main`，不顺带推送全部分支或标签。Push 后核对 GitHub 上的 commit SHA 和 Private 可见性。

**结论：本地冻结 commit 与基准一致，本次 HEAD 检查未发现禁止提交内容或已确认真实凭据；可以进入私人仓库发布的人工确认步骤。当前仍未配置 remote、未发布。** 不创建 GitHub 仓库，不添加 remote，不 push，不 commit；到此停止。
