# E2E 测试报告模板

**日期:** {date}
**测试环境:** {env}
**持续时间:** {duration}
**状态:** {status}

## 测试摘要

| 指标 | 数量 |
|------|------|
| 总测试数 | {total} |
| 通过 | {passed} ({passed_pct}%) |
| 失败 | {failed} |
| 跳过 | {skipped} |
|  flaky | {flaky} |

## 测试分类

### CLI 命令测试

| 测试 | 状态 | 耗时 |
|------|------|------|
| fetch --help | {status} | {duration}ms |
| analyze --help | {status} | {duration}ms |
| report --help | {status} | {duration}ms |

### Pipeline 测试

| 测试 | 状态 | 耗时 |
|------|------|------|
| Phase1 数据准备 | {status} | {duration}ms |
| Phase2 聚类分析 | {status} | {duration}ms |
| 报告生成 | {status} | {duration}ms |

### UI 测试

| 测试 | 状态 | 耗时 |
|------|------|------|
| 概览页面加载 | {status} | {duration}ms |
| 聚类分析页面 | {status} | {duration}ms |
| 相似查询页面 | {status} | {duration}ms |
| 可视化页面 | {status} | {duration}ms |

## 失败的测试

### {test_name}
- **文件:** `{file}:{line}`
- **错误:** {error}
- **截图:** {screenshot}
- **建议修复:** {fix}

## 产物

- HTML 报告: `playwright-report/index.html`
- 截图: `tests/e2e/artifacts/*.png`
- 视频: `tests/e2e/artifacts/videos/*.webm`
- traces: `tests/e2e/artifacts/trace.zip`

## 运行命令

```bash
# 运行所有 E2E 测试
pytest tests/e2e/ -v

# 只运行 CLI 测试
pytest tests/e2e/cli/ -v

# 只运行 Pipeline 测试
pytest tests/e2e/pipeline/ -v

# 只运行 UI 测试
pytest tests/e2e/ui/ -v --headed

# 生成 HTML 报告
pytest tests/e2e/ -v --html=report.html --self-contained-html
```
