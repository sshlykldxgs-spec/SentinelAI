# SentinelAI Git Release Cleanup

日期：2026-10-12（Asia/Shanghai）。在 FINAL RELEASE VERIFIED 的工作区版本上整理首次提交集合。本轮仅修改 `.gitignore`、项目 README，新增 evaluation 展示入口和本报告，并整理暂存区；未修改业务逻辑、Agent、Prompt、Schema、模型配置、timeout/retry 或 API Key。未执行 commit/push，未重新运行模型。

## 1. 移出暂存的文件

使用 `git rm --cached -- <明确路径>`，仅移除索引条目，以下文件全部保留在工作区且内容不变：

| 文件 | 排除原因 |
| --- | --- |
| `blackbox_case_2026-10-12/business_brief.txt` | 临时模拟业务输入 |
| `blackbox_case_2026-10-12/suppliers_simulated.csv` | 临时模拟供应商数据 |
| `blackbox_case_2026-10-12/public_source_note.txt` | 黑盒案例配套输入 |
| `blackbox_case_2026-10-12/final_retry_live_report_download.md` | 下载型业务运行产物 |
| `docs/FINAL_LIVE_DECISION_REPORT.md` | 完整生成业务报告，不属于源码或验收摘要 |

未发现其他需要从索引移除的依赖、构建、缓存、日志或临时目录。没有删除文件，也没有删除历史验收报告。保留 `demo/brief.txt`、`demo/suppliers.csv`，因为它们由后端默认启动直接读取，是产品内置示例。

## 2. 新增 ignore 规则

```gitignore
/blackbox_case_*/
/docs/FINAL_LIVE_DECISION_REPORT.md
build/
*.jsonl
*.tmp
*.bak
*.swp
```

保留原有 `.env`、真实凭据文件、虚拟环境、node_modules、dist、Python 缓存、日志及数据库规则；`.env.example` 继续允许提交。已用 `git check-ignore -v` 确认新规则匹配上述 5 个文件及对应临时/构建路径。未忽略所有 CSV/TXT，也未忽略 `docs/evaluation/`。

## 3. README 小幅修正

- 增加当前 **FINAL RELEASE VERIFIED** 状态及集中验收入口，明确技术流程完成与业务批准的区别。
- 删除将旧 Planner 失败当作当前状态的段落，更新为本次 242.61 秒完整 Live、Reviewer 一次既有恢复、无 fallback 和报告生成结果；保留本机桥接工具可选、评委无需 CC Switch 的说明。
- 明确评委从模型配置页填写自己的配置、测试连接、返回总览选择资料并启动 Live 的流程。
- 区分工作台内存配置立即生效与环境变量/`.env` 修改后重启，避免误导评委重启丢失临时配置。
- 将旧按钮名和“Live 按钮不可选”修正为当前“测试连接”及未配置启动时跳转设置；保留失败不回退的说明。

README 原有介绍、架构图、启动命令、模式表、API 和测试命令均保留，没有整体重写。没有将浏览器自动化下载取消描述成验收已通过项。

## 4. 展示资料与移动建议

新增 [evaluation/README.md](README.md)，集中链接最新 Final Attempt、历史 Live/黑盒验收、模型配置、稳定性和安全报告，并注明旧策略、旧失败、错误任务关联的阅读边界。项目 README 指向此入口及最新 Final Attempt 章节。

历史文件均保持原位。建议未来把早期失败、排障和准备过程文档归入 `docs/evaluation/history/`，移动时同步更新引用；本轮只提出移动建议，不移动、不删除。`docs/FINAL_BLACKBOX_RELEASE_TEST.md` 与本目录的同名报告内容不同，不能当作重复副本删除；本目录报告的任务混用问题通过 `ACTION_TIMEOUT_DIAGNOSIS.md` 明确提示。旧报告引用的原始业务输出不随仓库提交，只作为历史本地证据路径。

## 5. 暂存与 commit 前检查

清理前分支为 `main`、无 commit；72 个已暂存文件，7 个文件有更新未暂存，15 个未跟踪文件。清理时按明确路径暂存已有最新源码、测试、配置说明及验收文件，没有使用 `git add .`，也没有修改这些业务文件。

本报告纳入暂存后，提交集合为 **84 个新增文件**：清理前 72 个，减去 5 个排除项，加上原有 15 个未跟踪文件，再加展示入口与本报告。所有提交内容均应与当前工作区版本一致，无待暂存修改或未跟踪的非忽略文件。

| 检查 | 结果 |
| --- | --- |
| 业务代码、配置、测试及历史文档保留 | 85 个既有文件的内容哈希与本轮开始一致（排除获准修改的项目 README 和 `.gitignore`，包含被移出暂存的文件） |
| 临时业务输入/下载产物 | 5 个路径已移出索引，仍存在且被忽略 |
| 暂存版本 | 已将原先漏暂存的模型配置/诊断实现和对应测试纳入索引，无业务修改 |
| 暂存敏感内容检查 | 报告生成前 83 个实际索引 blob 均已扫描；本报告纳入后的 84 个文件复查无高可信密钥模式命中，未发现已确认真实凭据 |
| 禁止路径/二进制产物 | 索引中未发现 `.env`、依赖、构建、缓存、日志、数据库、黑盒原始输入或下载型业务报告 |
| 空白与冲突检查 | `git diff --cached --check` 通过 |
| 文档入口 | 项目 README、evaluation 入口、本报告的相对链接与 Final Attempt 章节锚点全部通过，无缺失链接 |
| 已验收版本 | 本轮未改运行逻辑，不重跑测试/构建/Live；沿用此前 102 项测试和最终 Live 验收记录 |

扫描包括常见模型/API 密钥、访问 Token、JWT、私钥、Bearer 字面值、凭据 URL、密码/密钥赋值及禁止路径；只输出路径与分类。25 处匹配为离线夹具/占位符；其余 3 处分别为 `test_model_config_ui.py` 的 canary URL、`test_v2.py` 的脱敏夹具，以及 `deepseek.sh` 从配置构造认证头的代码，均不是硬编码真实凭据。未读取外部真实 Key、未扫描私人目录或运行依赖全文；这是提交内容检查，不是对所有未知秘密或漏洞的绝对保证。

历史文档仍保留原时点的失败、配置和本机路径引用；集中入口明确区分历史与当前，不伪装成全部文档已重写。它们不是私人日志文件，不作为本次应用运行结果。

**结论：提交范围清理已完成，commit 前检查通过，可进入首次 commit 的人工确认阶段。** 最终为 84 个新增暂存文件，无未暂存修改或未跟踪的非忽略文件，索引与工作区一致。技术验收状态保持 FINAL RELEASE VERIFIED；没有执行 commit 或 push。按本轮要求停止。
