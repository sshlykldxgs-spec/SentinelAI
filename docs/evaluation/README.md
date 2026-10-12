# SentinelAI 评委验收资料

当前技术验收状态：**FINAL RELEASE VERIFIED**。先阅读[最终发布验收的 Final Attempt 章节](FINAL_RELEASE_VERIFICATION.md#2026-10-12-final-attempt独立实例asiashanghai)：连接测试及五阶段 Live 完成，报告已生成；Reviewer 仍要求补证据，行动未获批准。该报告前部保留历史失败，不代表当前版本状态。浏览器自动化下载取消的限制也保留在最新章节中。

## 集中阅读入口

| 资料 | 用途与时点 |
| --- | --- |
| [FINAL_RELEASE_VERIFICATION.md](FINAL_RELEASE_VERIFICATION.md) | 最新 Final Attempt：任务 `051451dc-1226-4e06-a34d-8ce1da31ab66`，五阶段技术验收依据 |
| [FINAL_LIVE_ACCEPTANCE_REPORT.md](../FINAL_LIVE_ACCEPTANCE_REPORT.md) | 历史五阶段成功记录；其模型参数及耗时属于当时运行 |
| [FINAL_BLACKBOX_ACCEPTANCE.md](../FINAL_BLACKBOX_ACCEPTANCE.md) | 历史黑盒成功任务；不与最新任务混用 |
| [MODEL_CONFIG_UI_REPORT.md](../MODEL_CONFIG_UI_REPORT.md) | 配置入口初版记录；后续以[连接测试修复](MODEL_CONNECTION_TEST_FIX_REPORT.md)和[运行诊断](MODEL_CONNECTION_RUNTIME_DIAGNOSIS.md)为准 |
| [STABILITY_OPTIMIZATION_REPORT.md](../STABILITY_OPTIMIZATION_REPORT.md) | 历史稳定性优化；后续恢复策略见[RETRY_RESTORE_REPORT.md](../RETRY_RESTORE_REPORT.md)，真实恢复结果见最新 Final Attempt |
| [FINAL_SECURITY_SCAN_REPORT.md](../FINAL_SECURITY_SCAN_REPORT.md) | 历史安全扫描，保留原时点与范围；最新提交集合检查见[GIT_CLEANUP_REPORT.md](GIT_CLEANUP_REPORT.md) |

本目录集中展示入口，历史报告仍保留在原路径，未复制、移动或删除。评委启动方式与模型配置见[项目 README](../../README.md)和[MODEL_SETUP.md](../MODEL_SETUP.md)。临时黑盒案例输入、下载型业务报告及 `/tmp/` 观察文件不随仓库提交；默认 Demo 示例保留。

## 历史报告与移动建议

- [ACTION_TIMEOUT_DIAGNOSIS.md](ACTION_TIMEOUT_DIAGNOSIS.md) 已说明 [FINAL_BLACKBOX_RELEASE_TEST.md](FINAL_BLACKBOX_RELEASE_TEST.md) 混用了任务记录；后者不能作为当前发布判定。另一份[同名报告](../FINAL_BLACKBOX_RELEASE_TEST.md)内容不同，也不是可直接删除的重复副本。
- 未来可将早期失败、排障与提交准备过程报告归入 `docs/evaluation/history/`，移动时同步修正引用；本轮仅提出建议，不实施移动。
- 不改写历史报告中的失败、旧策略或旧计数。历史报告若仍写“尚无 Git”“Live 未通过”或“精确 OK 校验”，应结合其时点阅读，当前状态以 Final Attempt 和当前配置说明为准。
