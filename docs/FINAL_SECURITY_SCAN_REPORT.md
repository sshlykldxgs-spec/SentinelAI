# SentinelAI 最终交付前只读安全扫描

日期：2026-10-12（Asia/Shanghai）。写入前确认本报告不存在。本轮仅扫描和新增本报告，未修改业务代码、配置或忽略规则，没有删除文件、执行Git命令、构建、真实模型请求或服务重启。

## 总体判定

**未发现已确认的真实模型密钥、访问Token、认证头或带凭据URL泄露；“无关运行产物全部排除”尚未满足。** 需要人工决定业务运行报告、临时观察数据和本机路径文档的提交范围，且补查未来实际暂存内容。没有为通过检查自动删除或更改这些文件。

本目录不存在.git，尚无真实Git暂存/提交集合可审查。本轮按要求没有执行Git操作；不能据本地文件安全推断外部仓库历史安全，也不能保证忽略规则会移除将来已经跟踪的内容。

## 扫描范围与方法

- 只读扫描12760个普通文件：自有源码/本地文件43、docs文档28、依赖与缓存12686、前端生成文件3。报告自身是扫描完成后新增，不包含凭据。
- 对上述普通文件进行本项目已授权Deepseek凭据的进程内逐字比对，只读取该提供商条目，不枚举其他账号/模型凭据，密钥不落盘、不回显。该比对全部未命中。
- 对自有文件、配置、文档和前端生成文件额外扫描DeepSeek/OpenAI/其它常见模型密钥格式、GitHub/Slack/HF等Token格式、凭据赋值、认证头、凭据URL/敏感查询参数及私钥材料；不打印匹配行或值。依赖/缓存中的未知秘密仅做已知密钥比对，不做全量第三方内容逐项人工审计，不能视为供应链安全审计。
- 对本项目已知的46个/tmp产物进行已知凭据及日志结构字段检查，含保护快照逐成员读取；没有解压到新文件。未扫描无关个人文件或系统日志。
- 符号链接未跟随；列出的链接都位于已忽略的依赖/虚拟环境中（工具入口或Python链接）。普通文件没有不可读取项；未解析日志文件数0。

## 1. API密钥、Token与认证头

已确认泄露文件清单：**空**。可信的未知凭据模式待确认项：**空**。

共有24处敏感模式候选经分类为占位符或离线测试假数据，不是真实凭据。代表路径/类型如下（不显示匹配原文）：

| 路径 | 行号 | 类型 | 判定 |
| --- | --- | --- | --- |
| backend/.env.example | 3 | 模型凭据字段 | 占位符，可提交示例 |
| backend/tests/test_deepseek_probe.py | 26 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_blackbox_fixes.py | 68、85、99 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_retry_restore.py | 53、76、86 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_reviewer_optimization.py | 133、155、172 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_output_validation.py | 93、137 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_stability.py | 51、116、157 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_app.py | 91、108 | 模拟客户端凭据 | 离线测试假数据 |
| backend/tests/test_v2.py | 41、68、124、148、155、250 | 模拟客户端凭据/脱敏测试 | 离线测试假数据 |

代码中用于后端真实请求的认证字段构造不是硬编码凭据；本轮只报告其存在与用途，不回显完整请求头。没有发起真实请求来测试密钥。

## 2. 配置与模板

项目发现的环境配置文件仅为 **backend/.env.example**，没有实际.env或其备份。示例凭据为占位符，非敏感模型名、地址、超时、重试、token数量参数可作评委模板。MODEL_MAX_OUTPUT_TOKENS等数值限制不属于访问Token，不应误报为凭据。

.gitignore覆盖.env、.env.*，显式仅放行.env.example，另外排除.envrc、.npmrc、.pypirc、常见认证JSON、私钥、数据库及日志。评委创建真实backend/.env后，按这些规则应被忽略；**当前没有Git集合可验证，未来若手动强制暂存或曾经跟踪，仍可能进入提交**。

服务端沿用OPENAI_API_KEY等现有变量，前端不是密钥配置入口。scripts/deepseek.sh不含真实Key，读的是用户本机条目；不能把CC Switch数据库、配置备份或账号文件一起提交。

## 3. 日志与用户数据

项目内未发现请求/调试/错误日志、JSONL日志或私有数据库文件。应用核心模块config/main/engine/output_validation没有直接print调用；这不等于证明所有第三方或远端日志安全。

项目外的5个观察日志/快照：

- /private/tmp/sentinelai-before-final-restart.json
- /private/tmp/sentinelai-blackbox-round2-observation.json
- /private/tmp/sentinelai-final-blackbox-http.jsonl
- /private/tmp/sentinelai-final-blackbox-observation.json
- /private/tmp/sentinelai-judge-ui-observation.json

检查未发现已知密钥、可信认证模式或非空敏感结构字段。HTTP日志是响应元数据；观察快照中**存在案例数据、任务/证据和阶段输出**，不是可以随意发布的纯运行计数。其来源为公开/模拟测试资料，不是已确认机密用户数据，但仍应排除在代码仓库之外，未经逐项确认不要复制进项目。截图和保护快照也属于临时运行产物；本轮没有删除它们。

当前用户可能存在于进程内存的数据、不可访问远端日志、未知格式秘密不在文件扫描可完全保证范围中。不能用“不含Key”代替“无任何用户数据”。

## 4. 构建产物与忽略覆盖

| 类型 | 当前情况 | 提交建议 |
| --- | --- | --- |
| .venv | 存在 | 已忽略，不提交 |
| node_modules | 存在 | 已忽略，不提交 |
| frontend/dist | 3个当前构建文件 | 已忽略，已扫描无凭据，不提交 |
| __pycache__/pyc | 存在 | 已忽略，不提交 |
| .pytest_cache/.cache | 规则已覆盖 | 不提交 |
| build | 存在第三方依赖内的build路径；自有候选未见独立build产物 | 当前**无一般build/规则**；依赖内build被上级忽略。未来顶层build需另行排除 |
| tmp/ | 当前规则覆盖同名目录 | 不提交 |
| *.tmp/*.bak/*.swp等临时扩展 | 自有候选未发现 | 当前**无一般扩展名规则**；后续产生时要人工检查 |
| source map | 自有候选/前端dist未发现 | 后续生成需按目录忽略并扫描 |

当前构建文件：frontend/dist/index.html、frontend/dist/assets/index-CZaajtYp.js、frontend/dist/assets/index-Dpmsrari.css。未匹配已知密钥或可信的凭据模式。文件数量分类与路径计数可能重叠，不能把依赖内dist/build重复计为项目生成内容。

## 5. 文档与运行产物

docs中未发现真实密钥、认证头或带密码/Token的URL。公开来源URL、本地服务URL不是私密URL凭据。

以下**业务运行输出当前不被.gitignore排除**，与纯代码及模板不同：

- docs/FINAL_LIVE_DECISION_REPORT.md
- blackbox_case_2026-10-12/final_retry_live_report_download.md

它们通过扫描没有密钥，来源为公开/模拟案例，但包含实际运行任务、模型分析与审批建议。若只交代码，建议人工决定排除或仅保留明确标注的样本；本轮没有删除、移动或修改。不能将含业务数据的下载报告当作必须提交的代码。

以下7份文档引用本机绝对路径或/tmp观察路径，属于**发布前隐私与可移植性审查项**，不是已确认密钥泄露：

- docs/BLACKBOX_FINAL_ACCEPTANCE_CONNECTED.md
- docs/BLACKBOX_FINAL_ACCEPTANCE.md
- docs/IMPLEMENTATION_AUDIT.md
- docs/BLACKBOX_FIX_REPORT.md
- docs/FINAL_ACCEPTANCE_2026-10-12.md
- docs/FINAL_BLACKBOX_ACCEPTANCE.md
- docs/BLACKBOX_JUDGE_TEST_2026-10-12.md

报告中的英文token用量及模型名称不属于API密钥。历史测试/验收文字不是本轮新执行结果，不能因扫描文档存在就声称又跑过测试。

## 剩余人工决定

1. 决定是否提交上述两份运行生成报告，及是否处理本机绝对路径引用；在获得授权前不删除或修改。
2. 提交范围中明确排除依赖、构建、缓存、观察快照和用户资料；若希望补充build/或临时扩展忽略规则，需另行授权，本轮未改。
3. 未来初始化/暂存获授权后，应检查**实际暂存内容**再进行秘密扫描；.gitignore不能清除已跟踪内容或替代Git历史检查。本轮未执行任何Git命令。

最终：**已检查范围内未发现真实凭据泄露；运行产物和文档本机信息仍有待选择/排除，当前不能无条件确认整个目录可以原样提交。** 仅新增本扫描报告，所有旧文件与服务保持不变。到此停止。
