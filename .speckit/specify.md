# Feature Specification

## Feature Name
故障复盘分析系统 - 核心流水线

## Description
构建一个 AI 驱动的故障复盘分析流水线系统。系统从研发云平台 REST API 获取故障工单数据，经过文本预处理、向量 Embedding、HDBSCAN 密度聚类发现相似问题簇，结合开发规范进行违规检测，最终通过 LLM 生成根因标签、深度根因分析和改进建议。系统支持 CLI 命令行操作和 Streamlit Web 可视化界面。

## User Stories

### Primary Story
**As a** 研发团队负责人或质量工程师
**I want** 自动化分析历史故障工单，发现相似问题模式并识别根本原因
**So that** 能够针对性改进开发流程，减少同类故障重复发生

### Additional Stories
- **As a** 开发工程师
- **I want** 查看自己负责模块的故障聚类结果和根因分析
- **So that** 了解常见问题模式，改进编码习惯

- **As a** 测试工程师
- **I want** 根据聚类结果补充测试用例覆盖遗漏场景
- **So that** 提高测试覆盖率，预防类似故障

## Acceptance Criteria

### Functional Requirements
- [ ] 系统能够从研发云 API 获取指定故障单的完整信息（包括代码变更、复盘结论）
- [ ] 系统能够对故障描述进行文本预处理（提取关键字段、组合分析文本）
- [ ] 系统能够生成向量 Embedding 并存储到 ChromaDB
- [ ] 系统能够使用 HDBSCAN 对故障进行聚类，发现相似问题簇
- [ ] 系统能够为每个聚类簇生成语义标签（如"数据库问题"、"并发问题"等）
- [ ] 系统能够基于开发规范检测代码变更中的违规行为
- [ ] 系统能够进行深度根因分析（5层追问机制）
- [ ] 系统能够生成改进建议和行动项
- [ ] 系统提供 CLI 命令行工具进行批量操作
- [ ] 系统提供 Streamlit Web 界面进行交互式分析
- [ ] 系统生成可视化报告（聚类散点图、统计图表）

### Non-Functional Requirements
- [ ] **性能**: 单个故障单处理时间 < 30秒（不含 LLM 调用延迟）
- [ ] **可扩展性**: 支持处理 1000+ 故障单的批量分析
- [ ] **可靠性**: API 缓存机制保证重复请求不消耗额外资源
- [ ] **可维护性**: 模块化架构，各组件可独立替换

## User Flow

### Steps（CLI 批量分析流程）
1. 用户通过 Excel 文件提供故障单号列表
2. 系统执行 Phase1：批量获取、预处理、Embedding，存储到 ChromaDB
3. 系统执行 Phase2：聚类、标签生成、根因分析、违规检测
4. 系统生成分析报告（Excel + 可视化图表）
5. 用户在 Streamlit 界面查看交互式分析结果

### Steps（单个故障分析流程）
1. 用户指定单个故障单号
2. 系统获取故障详情和复盘结论
3. 系统进行深度根因分析
4. 系统生成改进建议
5. 用户查看分析结果

### Edge Cases
- **如果 API 返回空数据或超时**
  - **预期行为**: 使用缓存数据或提示用户检查网络/API 状态

- **如果故障单没有代码变更记录**
  - **预期行为**: 跳过违规检测，仅进行根因分析

- **如果聚类结果中某个簇只有一个样本**
  - **预期行为**: 标记为噪声点，不生成簇标签

- **如果 LLM API 不可用**
  - **预期行为**: 使用本地备用模型或提示用户检查配置

## Data Requirements

### Input Data（故障单）
| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| taskNo | str | 故障单号 | 必填，纯数字格式 |
| taskName | str | 故障标题 | 必填 |
| description | str | 故障描述 | 可选 |
| resolveTime | datetime | 解决时间 | 可选 |
| isCommitCode | str | 是否有代码变更 | Y/N |
| codeChanges | list | 代码变更记录 | 可选 |

### Output Data（分析结果）
| Field | Type | Description |
|-------|------|-------------|
| cluster_id | int | 聚类簇编号 |
| cluster_label | str | 簇语义标签 |
| root_causes | list | 根因列表 |
| violations | list | 违规项列表 |
| improvements | list | 改进建议列表 |

## Business Rules

1. **规则 1**：只有代码变更记录（isCommitCode=Y）的故障单才进行违规检测
   - **条件**: 故障单标记为有代码变更
   - **行为**: 提取代码变更内容，对照开发规范检测违规

2. **规则 2**：聚类簇大小小于 min_cluster_size 的标记为噪声
   - **条件**: HDBSCAN 聚类结果为 -1
   - **行为**: 不生成簇标签，单独分析

3. **规则 3**：根因分析优先使用现有复盘结论
   - **条件**: 故障单已有复盘分析记录
   - **行为**: 结合现有结论进行深度追问，补充遗漏维度

4. **规则 4**：改进建议需关联具体开发规范条款
   - **条件**: 检测到违规行为
   - **行为**: 改进建议引用对应规范编号（如 J000001）

## Error Handling

| Error Condition | Error Message | User Action |
|-----------------|--------------|-------------|
| Invalid taskNo | "故障单号格式无效，请输入纯数字" | 检查输入格式 |
| API timeout | "API 请求超时，请检查网络连接" | 重试或检查网络 |
| Authentication failed | "API 认证失败，请检查 DEVCLOUD_TOKEN" | 检查环境变量 |
| LLM unavailable | "LLM 服务不可用，请检查配置" | 检查 LLM_API_KEY |
| ChromaDB error | "向量数据库操作失败" | 检查 ChromaDB 状态 |

## Success Criteria

### Definition of Done
- [ ] 所有验收标准已满足
- [ ] 所有边界情况已处理
- [ ] 所有业务规则已实现
- [ ] 所有错误条件已处理
- [ ] 测试覆盖率 ≥ 79.9%
- [ ] 代码审查已通过
- [ ] 文档已更新（CLAUDE.md）

### Metrics
- **功能完整性**: 所有核心模块功能可用
- **代码质量**: Ruff lint 无错误，类型检查通过
- **测试覆盖**: 核心模块覆盖率 ≥ 80%

## Dependencies

### Internal Dependencies
- 研发云平台 API（故障单详情、复盘结论）
- ChromaDB 向量数据库
- SQLite 缓存数据库

### External Dependencies
- LLM API（火山引擎豆包 / OpenAI / 智谱）
- Embedding API（火山引擎 / OpenAI / 本地 sentence-transformers）

## Open Questions

1. **Question**: 是否支持实时增量分析（新故障单自动触发分析）？
   - **Status**: Open
   - **Decision**: 第一版仅支持批量分析，增量分析作为后续迭代

2. **Question**: 根因分析结果是否需要人工确认后再入库？
   - **Status**: Open
   - **Decision**: 第一版自动入库，保留人工复核接口

## Out of Scope

- 实时监控和告警功能（Phase 2）
- 自动创建 Jira 工单跟踪改进项（Phase 3）
- 多租户和权限管理（Phase 3）
- 与 CI/CD 流程集成（Phase 2）

## References

- **API Documentation**: `swagger.txt`
- **Development Standards**: `docs/浩鲸在线规范库.pdf`
- **Test Data**: `故障单列表.xlsx` (1924条)
- **Existing Analysis**: `docs/故障复盘分析系统/MANUAL_VERIFICATION_CHECKLIST.md`

---

**Notes**:
- This specification focuses on WHAT, not HOW
- Technical implementation details belong in `plan.md`
- Questions and clarifications should be addressed before implementation
- Update this document as requirements change

**Status**: Draft
**Owner**: Development Team
**Last Updated**: 2026-03-30