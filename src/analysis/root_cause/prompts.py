"""根因分析Prompt模板"""

from __future__ import annotations

ROOT_CAUSE_ANALYSIS_PROMPT = """你是一个故障根因分析专家。请根据以下信息，分析故障的根本原因。

## 故障信息
- 单号：{task_no}
- 标题：{title}
- 描述：{description}
- 故障来源：{task_src}
- 创建时间：{created_date}
- 关闭时间：{finish_date}

## 现有故障复盘结论（仅供参考，不要直接复制）

### 研发环节分析
- 分类：{dev_catalog} > {dev_catalog_detail}
- 原因：{dev_reason}
- 结论：{dev_conclusion}
- 改进措施：{dev_improve_stage}

### 测试环节分析
- 分类：{test_catalog} > {test_catalog_detail}
- 原因：{test_reason}
- 结论：{test_conclusion}
- 改进措施：{test_improve_stage}

---

## 分析要求

### 1. 问题分类
请先判断问题属于哪一类：
- 【开发引入】代码逻辑错误、设计缺陷、接口问题
- 【测试泄露】用例设计遗漏、用例执行偏差
- 【需求问题】需求描述不清、确认不到位
- 【外部依赖】第三方服务、基础设施问题

### 2. 深层根因挖掘
对于归因为"场景考虑不全"的分析，请继续追问：

1. **为什么没考虑到？**
   - 是设计阶段的问题？（设计文档、接口契约、状态机）
   - 是编码阶段的问题？（代码走查、防御性编程、异常处理）
   - 是测试阶段的问题？（用例设计方法、checklist、场景组合）

2. **哪个环节的checklist或流程可以发现这个问题？**

3. **如果是开发引入，是什么导致了代码缺陷？**

### 3. 输出格式
请按以下JSON格式输出分析结果：
```json
{{
  "problemCategory": "开发引入/测试泄露/需求问题/外部依赖",
  "initialCause": "现有系统给出的初步归因",
  "deepRootCauses": [
    {{
      "layer": "设计层面/编码层面/测试层面/流程层面/知识管理层面",
      "rootCause": "具体根因描述",
      "whyReason": "为什么认为这是根因",
      "evidence": "支撑证据"
    }}
  ],
  "actionableImprovements": [
    {{
      "type": "直接改进/流程改进",
      "action": "具体可执行的改进措施",
      "owner": "建议的责任方",
      "priority": "高/中/低"
    }}
  ],
  "checklistRecommendations": [
    "建议在XXX流程/规范中增加的checklist项"
  ]
}}
```

### 4. 注意事项
1. 不要直接使用现有复盘结论，而要以它为起点进一步追问
2. 每个根因必须有支撑证据，不能凭空猜测
3. 改进措施必须可落地，避免"加强注意"这类模糊表述
"""
