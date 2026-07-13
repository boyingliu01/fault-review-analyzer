#!/usr/bin/env python
"""演示：故障单分析全流程（mock数据模式）"""

import json
from pathlib import Path
from datetime import datetime

# 创建模拟故障单数据
MOCK_TASKS = [
    {
        "task_id": 11745664,
        "task_no": "11745664",
        "title": "reconnection复装业务更换卡类型问题",
        "description": """
【问题现象】
用户在办理复装业务时，选择ESIM卡后，又更换为物理卡，系统报错无法继续办理。

【处理过程】
1. 初步排查发现是状态转换问题
2. 代码审查发现缺少状态校验
3. 修复后验证通过

【根因分析】
开发环节：状态机设计不完善，缺少"复装+ESIM -> 换物理卡"的状态转换路径。
测试环节：测试用例覆盖不全，未覆盖该组合场景。
        """,
        "status": "已关闭",
        "task_src": "缺陷单",
        "created_date": "2024-01-15",
        "finish_date": "2024-01-16",
        "is_commit_code": True,
        "development": {"root_cause": "状态转换场景遗漏", "solution": "补充状态校验逻辑"},
        "testing": {"root_cause": "关联场景考虑不全", "improvement": "补充测试用例"},
    },
    {
        "task_id": 11748712,
        "task_no": "11748712",
        "title": "创建唯一索引和主键约束导致的数据库异常",
        "description": """
【问题现象】
数据库迁移脚本执行失败，提示唯一索引冲突。

【处理过程】
1. 检查发现历史数据存在重复
2. 清理重复数据后重新执行
3. 添加数据清洗脚本

【根因分析】
开发环节：创建唯一索引前未检查历史数据重复情况。
数据环节：缺乏数据质量监控。
        """,
        "status": "已关闭",
        "task_src": "缺陷单",
        "created_date": "2024-01-18",
        "finish_date": "2024-01-19",
        "is_commit_code": True,
        "development": {"root_cause": "数据库脚本未考虑历史数据", "solution": "增加数据预检查"},
        "testing": {"root_cause": "数据库迁移测试不充分", "improvement": "增加数据兼容性测试"},
    },
    {
        "task_id": 11751534,
        "task_no": "11751534",
        "title": "并发场景下订单状态不一致",
        "description": """
【问题现象】
高并发场景下，订单状态出现不一致，部分订单显示"处理中"但已扣款。

【处理过程】
1. 日志分析发现竞态条件
2. 代码审查发现缺少分布式锁
3. 增加Redis分布式锁

【根因分析】
开发环节：并发控制缺失，多线程场景下状态更新冲突。
设计环节：未充分考虑高并发场景。
        """,
        "status": "已关闭",
        "task_src": "缺陷单",
        "created_date": "2024-01-20",
        "finish_date": "2024-01-22",
        "is_commit_code": True,
        "development": {"root_cause": "并发控制缺失", "solution": "增加分布式锁"},
        "testing": {"root_cause": "并发测试缺失", "improvement": "增加压力测试"},
    },
    {
        "task_id": 11751363,
        "task_no": "11751363",
        "title": "SQL注入漏洞导致的安全风险",
        "description": """
【问题现象】
安全扫描发现SQL注入漏洞，用户输入未做充分校验。

【处理过程】
1. 定位所有拼接SQL的位置
2. 改为参数化查询
3. 增加输入校验

【根因分析】
开发环节：使用字符串拼接SQL，未使用参数化查询。
规范环节：代码审查未覆盖SQL安全问题。
        """,
        "status": "已关闭",
        "task_src": "缺陷单",
        "created_date": "2024-01-21",
        "finish_date": "2024-01-22",
        "is_commit_code": True,
        "development": {"root_cause": "SQL注入漏洞", "solution": "参数化查询"},
        "testing": {"root_cause": "安全测试缺失", "improvement": "增加安全扫描"},
    },
    {
        "task_id": 11750733,
        "task_no": "11750733",
        "title": "空指针异常导致服务崩溃",
        "description": """
【问题现象】
生产环境偶发空指针异常，导致服务重启。

【处理过程】
1. 分析日志定位空指针位置
2. 增加空值校验
3. 增加异常捕获

【根因分析】
开发环节：方法入口未做空值校验。
测试环节：未覆盖边界条件测试。
        """,
        "status": "已关闭",
        "task_src": "缺陷单",
        "created_date": "2024-01-22",
        "finish_date": "2024-01-23",
        "is_commit_code": True,
        "development": {"root_cause": "空指针异常", "solution": "增加空值校验"},
        "testing": {"root_cause": "边界测试缺失", "improvement": "增加边界值测试"},
    },
]


def create_mock_analysis_report(task: dict) -> dict:
    """创建模拟分析报告"""

    # 根据故障单内容生成对应的根因分析
    root_causes = []
    violations = []
    suggestions = []

    desc_lower = task["description"].lower()

    # 状态/场景相关
    if "状态" in desc_lower or "场景" in desc_lower:
        root_causes.append(
            {
                "cause_type": "设计层面",
                "description": "状态机设计不完善，缺少关键状态转换路径的定义",
                "evidence": ["故障描述中提到状态转换问题", "复装+ESIM换物理卡场景缺失"],
                "confidence": 0.85,
            }
        )
        suggestions.append("在代码走查checklist中增加状态机覆盖验证项")

    # 数据库相关
    if "数据库" in desc_lower or "索引" in desc_lower or "sql" in desc_lower:
        root_causes.append(
            {
                "cause_type": "开发层面",
                "description": "数据库脚本未考虑历史数据兼容性，创建约束前未做数据清洗",
                "evidence": ["历史数据存在重复", "未做数据预检查"],
                "confidence": 0.90,
            }
        )
        violations.append(
            {
                "rule_id": "J000107",
                "rule_name": "数据库脚本规范",
                "severity": "high",
                "message": "创建约束前必须检查历史数据",
                "evidence": "未做数据预检查",
            }
        )
        suggestions.append("建立数据库变更checklist，强制要求数据兼容性验证")

    # 并发相关
    if "并发" in desc_lower or "锁" in desc_lower:
        root_causes.append(
            {
                "cause_type": "开发层面",
                "description": "并发控制缺失，高并发场景下出现竞态条件",
                "evidence": ["订单状态不一致", "多线程更新冲突"],
                "confidence": 0.88,
            }
        )
        violations.append(
            {
                "rule_id": "J000014",
                "rule_name": "并发安全规范",
                "severity": "high",
                "message": "多线程场景必须使用同步机制",
                "evidence": "缺少分布式锁",
            }
        )
        suggestions.append("在高并发场景必须使用分布式锁或乐观锁")

    # 安全相关
    if "sql注入" in desc_lower or "安全" in desc_lower:
        root_causes.append(
            {
                "cause_type": "开发层面",
                "description": "存在SQL注入漏洞，使用字符串拼接SQL语句",
                "evidence": ["安全扫描发现问题", "使用字符串拼接SQL"],
                "confidence": 0.95,
            }
        )
        violations.append(
            {
                "rule_id": "SEC001",
                "rule_name": "SQL注入防护",
                "severity": "critical",
                "message": "必须使用参数化查询，禁止字符串拼接SQL",
                "evidence": "存在字符串拼接SQL",
            }
        )
        suggestions.append("强制使用参数化查询或ORM框架")

    # 空指针相关
    if "空指针" in desc_lower or "null" in desc_lower:
        root_causes.append(
            {
                "cause_type": "开发层面",
                "description": "空值校验缺失，方法入口未对参数进行null检查",
                "evidence": ["空指针异常日志", "方法参数未校验"],
                "confidence": 0.92,
            }
        )
        violations.append(
            {
                "rule_id": "J000120",
                "rule_name": "空值校验规范",
                "severity": "medium",
                "message": "public方法必须做空值校验",
                "evidence": "方法入口未校验",
            }
        )
        suggestions.append("方法入口统一增加空值校验")

    # 测试相关根因（通用）
    root_causes.append(
        {
            "cause_type": "测试层面",
            "description": f"测试用例覆盖不全，缺少{task['testing']['root_cause']}",
            "evidence": [f"测试环节分析：{task['testing']['root_cause']}"],
            "confidence": 0.80,
        }
    )

    # 生成改进措施
    improvements = []
    for i, suggestion in enumerate(suggestions, 1):
        improvements.append(
            {
                "description": suggestion,
                "acceptance_criteria": f"完成第{i}项改进措施并验证",
                "expected_impact": f"减少此类故障发生概率",
                "priority": "high" if i <= 2 else "medium",
            }
        )

    return {
        "task_id": task["task_id"],
        "title": task["title"],
        "root_causes": root_causes,
        "violations": violations,
        "improvements": improvements,
        "labels": [
            {"name": task["task_src"], "category": "类型", "confidence": 0.95},
            {
                "name": "代码缺陷" if task["is_commit_code"] else "配置问题",
                "category": "性质",
                "confidence": 0.85,
            },
        ],
    }


def generate_report_markdown(analysis: dict) -> str:
    """生成Markdown格式报告"""
    lines = [
        f"# 故障复盘分析报告 - 任务 {analysis['task_id']}",
        "",
        "## 基本信息",
        "",
        f"- **任务ID**: {analysis['task_id']}",
        f"- **标题**: {analysis['title']}",
        f"- **报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 分类标签",
        "",
    ]

    for label in analysis["labels"]:
        lines.append(
            f"- **{label['name']}** ({label['category']}) - 置信度: {label['confidence'] * 100:.0f}%"
        )

    lines.extend(["", "## 根因分析", ""])

    for i, rc in enumerate(analysis["root_causes"], 1):
        lines.extend(
            [
                f"### {i}. {rc['cause_type']}",
                "",
                rc["description"],
                "",
                "**证据**:",
            ]
        )
        for evidence in rc["evidence"]:
            lines.append(f"- {evidence}")
        lines.extend(["", f"置信度: {rc['confidence'] * 100:.0f}%", ""])

    if analysis["violations"]:
        lines.extend(["## 规范违规", ""])
        for v in analysis["violations"]:
            lines.extend(
                [
                    f"### ⚠️ {v['rule_name']} (严重度: {v['severity']})",
                    "",
                    f"- **规则ID**: {v['rule_id']}",
                    f"- **问题**: {v['message']}",
                    f"- **证据**: {v['evidence']}",
                    "",
                ]
            )

    if analysis["improvements"]:
        lines.extend(["## 改进措施", ""])
        for i, imp in enumerate(analysis["improvements"], 1):
            lines.extend(
                [
                    f"{i}. **{imp['description']}**",
                    f"   - 验收标准: {imp['acceptance_criteria']}",
                    f"   - 预期影响: {imp['expected_impact']}",
                    f"   - 优先级: {imp['priority']}",
                    "",
                ]
            )

    lines.append("---")
    lines.append("*本报告由故障复盘分析系统自动生成*")

    return "\n".join(lines)


def main():
    """主函数：执行mock分析"""
    print("=" * 60)
    print("故障复盘分析系统 - MOCK模式演示")
    print("=" * 60)
    print()

    output_dir = Path("output/phase1")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_analysis = []

    print("【阶段1】分析单个故障单...")
    print()

    for task in MOCK_TASKS[:2]:  # 只分析前2个用于阶段1
        print(f"正在分析故障单 {task['task_id']}: {task['title'][:30]}...")

        # 执行分析
        analysis = create_mock_analysis_report(task)
        all_analysis.append(analysis)

        # 生成报告
        report = generate_report_markdown(analysis)
        report_path = output_dir / f"task_{task['task_id']}_report.md"
        report_path.write_text(report, encoding="utf-8")

        print(f"  ✓ 根因数量: {len(analysis['root_causes'])}")
        print(f"  ✓ 违规数量: {len(analysis['violations'])}")
        print(f"  ✓ 改进措施: {len(analysis['improvements'])}")
        print(f"  ✓ 报告已保存: {report_path}")
        print()

    print("【阶段1完成】")
    print()

    # 保存汇总数据供阶段2使用
    summary_path = output_dir / "phase1_summary.json"
    summary_path.write_text(
        json.dumps(all_analysis, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"汇总数据已保存: {summary_path}")
    print()

    # 输出验证清单
    print("=" * 60)
    print("阶段1验证清单（你需要人工核对这些点）")
    print("=" * 60)
    print()
    for analysis in all_analysis:
        print(f"故障单 {analysis['task_id']}: {analysis['title']}")
        print()
        print("  □ 根因类型是否准确？（设计/开发/测试层面）")
        print("  □ 根因描述是否具体可落地？")
        print("  □ 改进措施是否针对性强？")
        print("  □ 违规检测是否合理？")
        print()

    print("=" * 60)
    print("请查看 output/phase1/ 目录下的报告文件进行人工验证")
    print("=" * 60)


if __name__ == "__main__":
    main()
