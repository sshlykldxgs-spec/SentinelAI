# 模型配置接口加载：仅启动验证

日期：2026-10-12（Asia/Shanghai）。目标报告新增前确认不存在。本轮仅授权重启及接口检查，真实模型API调用0次，未运行黑盒或分析工作流。

## 重启记录

- 重启前确认旧8000进程PID 8452，没有运行中的任务；已有1个终态任务、3份用户上传资料元数据。
- 在停止之前，将公开bootstrap中的脱敏任务/证据/文件元数据归档至 `/tmp/sentinelai-model-config-load-before-restart.json`（本地私有权限）。此快照不是上传原始字节备份，也不是跨进程自动恢复。原始测试案例和已下载报告文件未改动。
- 重启操作开始：2026-10-12 04:46:02.566 +08:00；新进程开始：2026-10-12 04:46:47 +08:00（PID 9568，监听127.0.0.1:8000）。
- 使用当前已有安全启动方式 `sh scripts/deepseek.sh serve --port 8000`，只读原CC Switch Deepseek条目，凭据注入该进程，不落盘；没有更换模型、Key或Base URL，不修改.env或配置文件。
- 5173前端进程和API代理未修改、未重启。后端内存历史因已授权重启清空；归档和原始案例文件保留。

## 服务状态与接口注册

核验时间：2026-10-12 04:52:37.316 +08:00。OpenAPI与本地响应检查：

| 入口 | 注册/检查结果 |
| --- | --- |
| GET /api/health（8000） | HTTP200，status=ok |
| GET /api/model/config（经5173 /api代理） | HTTP200，新配置来源/地址字段存在，API响应不含api_key |
| POST /api/model/config | 已在新OpenAPI注册；本轮没有提交表单或更改配置 |
| POST /api/model/test | 已注册；本轮没有点击或发起模型测试 |
| POST /api/runs | 原Live/Demo/Replay创建路径仍注册；本轮未创建任务 |
| GET /api/runs/{run_id} / events / report | 原查询、SSE、下载路径仍注册 |
| POST /api/files | 原上传路径仍注册；本轮未新增上传 |
| POST /api/approvals/{approval_id} | 原审批路径仍注册；本轮未审批 |

bootstrap响应live_available=true，Demo示例文件2份，新进程任务数0。没有把接口注册当作完整功能执行通过；本轮只确认可访问的公开配置和健康响应。

## 有效配置未改变

实际模型deepseek-flash，服务api.deepseek.com，配置来源environment（现有桥接进程环境）；独立超时仍Planner60、Research120、Analyst90、Reviewer120、Action120秒，任务300秒。执行器重试1、SDK重试1。本地输出token上限与任务token预算null。与旧进程公开值一致。

没有新增API Key或将凭据复制到源码、前端、报告或日志，没有修改Agent、Prompt、Schema、timeout或retry代码与值，没有Git操作、部署或清理历史文件。

## 前端验证

真实Chromium只进行页面加载和点击首页「模型配置」：5173可用、bootstrap HTTP200、表单可见、API Key输入type=password且为空，「保存配置」「测试连接」各一个。没有点击保存、测试、启动分析或审批，因此没有隐式额度消耗。浏览器已关闭。

## 是否建议进入最终黑盒验收

**可以进入另行授权的最终UI黑盒验收**：后端加载新配置入口，健康与前端代理正常。下一轮可测试评委填表→主动测试连接→Live启动，但仍需明确模型额度与测试范围；本轮没有代替执行。

原Live/Demo路径的注册与配置检查未观察到异常；实际任务执行、连接测试、保存配置和审批写入本轮均未测试，不能称为再次完整回归通过。此前98/98离线测试与构建结果是历史证据。

到此停止，服务保持8000/5173可用。仅新增本报告及重启前的本地观察归档，未修改业务代码、配置或密钥。
