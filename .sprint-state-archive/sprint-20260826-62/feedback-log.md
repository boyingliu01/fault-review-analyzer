# Feedback Log — Sprint sprint-20260826-62

## VERIFY 阶段反馈

### 验证执行
- **全量测试**: 1298 passed, 85 deselected(e2e), 0 failures
- **ruff**: src/ui + tests/ui 全部通过
- **test-specification-alignment (#367)**: PASS (score 100, 6/6 REQ 覆盖)
- **AppTest 真实渲染**: 0 异常，批次导览/帕累托图/违规条款/明细链接/详情联动均正常
- **LSP diagnostics**: 干净

### 反馈项
1. **Streamlit 1.55 API 适配**: 原 `use_container_width=True` 已弃用（2025-12-31 移除），改为 `width="stretch"`
2. **selection_mode 取值**: 用 `"single-row"`（`"single"` 非法会抛 StreamlitAPIException）
3. **LinkColumn 用 URL 字符串**: 非 markdown，cell 值必须是 URL
4. **批次推断**: 用 all_analysis_*.json 时间戳（progress mtime 不可靠，实测 181 文件跨 43 分钟仅 2 真实批次）
5. **孤儿 progress**: 归入"未归档"批次，实测 14 起孤儿

### 无阻塞问题
- scripts/run_all_parallel.py 8 个预先存在 ruff 错误（非本次引入，不在 CI 严格范围）
- npx/tsx 环境损坏，test-alignment 报告用 Python 脚本生成（确定性等价实现）
