# SDK、限流与Schema有限重试恢复

日期：2026-10-12。真实API请求0次，没有读取或修改密钥、真实.env、模型或Base URL，未重启现有共享后端或执行Git操作。历史稳定性报告保留，本报告记录其后策略变更。

## 当前策略

- MODEL_SDK_MAX_RETRIES新增可选0/1字段，未设置时跟随MODEL_MAX_RETRIES，默认1。客户端实际max_retries传入该值，SDK的限流与传输恢复启用。
- MODEL_MAX_RETRIES继续限制执行器最多一次恢复。SDK启用时，传输错误返回后记录recovery_owner=sdk及executor_retry_suppressed=true，不再叠加执行器传输恢复；包括外层阶段截止，以防反复等待。
- SDK关闭时执行器可对timeout、connection、429、502/503/504恢复一次。
- JSON/Schema/角色必填校验错误由执行器恢复一次。修正要求保存在JSON上下文output_correction字段中，不包含原无效响应，不改变原Schema。第二次非法则failed、下游blocked，无伪造报告。
- length截断、不支持的完成类型、认证、请求参数错误、业务审核needs_evidence不进行执行器恢复；Reviewer和Action审批门禁保持。
- SDK遵循已安装OpenAI SDK的传输重试规则，不保证仅限502/503/504；默认规则也包括408/409/429及其它5xx/显式重试指示。最多一次SDK重试，独立Agent和整个任务截止仍生效。

## 调用上限与记录边界

SDK=1加执行器Schema恢复=1，最坏一个阶段可发生4次HTTP请求（先一次逻辑调用内2次，结构失败再一次逻辑调用内2次），五阶段最坏20次；SDK耗尽后同类错误不再被执行器恢复，所以不是无限相乘。Schema修正可能带来更多计费，超时的旧请求远端是否已取消不可保证。

attempt_history/first_failure继续保留执行器逻辑尝试与错误脱敏；SDK内部单次HTTP失败不直接进入这些记录，不能将attempts当作实际HTTP总次数。SDK恢复耗尽标记会进入阶段和任务最终错误。现有retrying(1/1)只表示执行器恢复，SDK退避仍发生在一次逻辑请求内部。

## 修改文件

- backend/app/config.py：SDK重试配置与客户端参数、429和Schema错误恢复分类。
- backend/app/engine.py：两层恢复协调、输出修正保持JSON上下文、耗尽记录传递终态。
- backend/.env.example、docs/MODEL_SETUP.md：仅配置名/占位符与上限说明。
- backend/tests/test_retry_restore.py新增4项；test_v2.py/test_stability.py/test_token_limits.py适配本轮策略，不放宽结构/失败/审核断言。
- 本报告。未修改UI或业务Schema。

## 实际离线验证

- 全量后端：`PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -v`，**90/90通过，23.247秒**，0失败/错误/跳过。
- 前端`npm run build`：**通过，1743 modules，1.44秒**。
- 实际配置客户端 + SDK + 内存MockTransport：第一次429、第二次200，确认恰好2次HTTP；没有网络请求。
- SDK已启用时模拟传输耗尽：执行器不再重复，错误抑制标记保留，无报告。
- 第一次Schema错误、第二次有效输出：完成五阶段离线回放，Reviewer保留，原Schema未放宽。两次Schema错误则结束；截断依然只尝试一次。
- 关闭SDK时429有限恢复、Action恢复保留人工审批、两次失败没有外部行动及无完整报告测试继续通过。

首轮回归曾发现修正提示破坏JSON上下文和终态漏掉SDK协调标记，已最小修复并全量重新验证。不存在尚未通过的自动化项。离线结果不等于真实DeepSeek稳定性已验收。

共享后端仍是此前启动的旧代码/无重试进程，未重启、不清除历史。需要另行确认重启或使用新独立进程后才能加载新的SDK策略；显式MODEL_MAX_RETRIES=0且SDK变量未设置仍关闭两层，符合现有无重试验收脚本语义。
