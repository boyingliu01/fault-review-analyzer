"""国际化翻译模块"""

from typing import Any

# 翻译词典
TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh": {
        # 错误消息
        "error.api.connection": "API连接失败",
        "error.api.authentication": "认证失败",
        "error.api.timeout": "API请求超时",
        "error.api.not_found": "资源未找到",
        "error.embedding.failed": "嵌入生成失败",
        "error.clustering.failed": "聚类分析失败",
        "error.analysis.failed": "分析失败",
        "error.rules.load": "规则加载失败",
        "error.cache.miss": "缓存未命中",
        # API响应
        "api.success": "成功",
        "api.failed": "失败",
        "api.data_processed": "数据已处理",
        "api.clusters_found": "发现聚类",
        "api.violations_detected": "检测到违规",
        # 报告标题
        "report.title": "故障分析报告",
        "report.summary": "摘要",
        "report.clusters": "聚类分析",
        "report.violations": "违规检测",
        "report.recommendations": "改进建议",
        "report.roots": "根因分析",
        "report.analysis": "深度分析",
        "report.metadata": "元数据",
        "report.tasks": "任务列表",
        "report.metrics": "指标",
        "report.duration": "执行时间",
        # 聚类报告
        "cluster.id": "聚类ID",
        "cluster.size": "聚类大小",
        "cluster.label": "聚类标签",
        "cluster.violations": "违规数量",
        "cluster.similarity": "相似度",
        "cluster.representative": "代表性任务",
        # 违规报告
        "violation.rule": "规则",
        "violation.category": "分类",
        "violation.severity": "严重程度",
        "violation.evidence": "证据",
        "violation.message": "违规信息",
        # 严重程度
        "severity.critical": "严重",
        "severity.high": "高",
        "severity.medium": "中",
        "severity.low": "低",
        # 分类
        "category.security": "安全",
        "category.performance": "性能",
        "category.code": "代码质量",
        "category.architecture": "架构",
        "category.testing": "测试",
        "category.documentation": "文档",
        # 根因分析
        "root_cause.primary": "主要根因",
        "root_cause.secondary": "次要根因",
        "root_cause.recommendation": "建议",
        "root_cause.action": "改进措施",
        "root_cause.impact": "影响范围",
        "root_cause.probability": "发生概率",
        # 改进建议
        "improvement.title": "改进建议",
        "improvement.description": "描述",
        "improvement.priority": "优先级",
        "improvement.estimated_effort": "预估工作量",
        "improvement.impact": "改进效果",
        "improvement.risk": "风险评估",
    },
    "en": {
        # Error messages
        "error.api.connection": "API connection failed",
        "error.api.authentication": "Authentication failed",
        "error.api.timeout": "API request timeout",
        "error.api.not_found": "Resource not found",
        "error.embedding.failed": "Embedding generation failed",
        "error.clustering.failed": "Clustering analysis failed",
        "error.analysis.failed": "Analysis failed",
        "error.rules.load": "Rules loading failed",
        "error.cache.miss": "Cache miss",
        # API responses
        "api.success": "Success",
        "api.failed": "Failed",
        "api.data_processed": "Data processed",
        "api.clusters_found": "Clusters found",
        "api.violations_detected": "Violations detected",
        # Report titles
        "report.title": "Fault Analysis Report",
        "report.summary": "Summary",
        "report.clusters": "Cluster Analysis",
        "report.violations": "Violation Detection",
        "report.recommendations": "Improvement Recommendations",
        "report.roots": "Root Cause Analysis",
        "report.analysis": "Deep Analysis",
        "report.metadata": "Metadata",
        "report.tasks": "Task List",
        "report.metrics": "Metrics",
        "report.duration": "Execution Time",
        # Cluster report
        "cluster.id": "Cluster ID",
        "cluster.size": "Cluster Size",
        "cluster.label": "Cluster Label",
        "cluster.violations": "Violations",
        "cluster.similarity": "Similarity",
        "cluster.representative": "Representative Task",
        # Violation report
        "violation.rule": "Rule",
        "violation.category": "Category",
        "violation.severity": "Severity",
        "violation.evidence": "Evidence",
        "violation.message": "Message",
        # Severity
        "severity.critical": "Critical",
        "severity.high": "High",
        "severity.medium": "Medium",
        "severity.low": "Low",
        # Categories
        "category.security": "Security",
        "category.performance": "Performance",
        "category.code": "Code Quality",
        "category.architecture": "Architecture",
        "category.testing": "Testing",
        "category.documentation": "Documentation",
        # Root cause analysis
        "root_cause.primary": "Primary Root Cause",
        "root_cause.secondary": "Secondary Root Cause",
        "root_cause.recommendation": "Recommendation",
        "root_cause.action": "Action Item",
        "root_cause.impact": "Impact Scope",
        "root_cause.probability": "Occurrence Probability",
        # Improvement recommendations
        "improvement.title": "Improvement",
        "improvement.description": "Description",
        "improvement.priority": "Priority",
        "improvement.estimated_effort": "Estimated Effort",
        "improvement.impact": "Impact",
        "improvement.risk": "Risk Assessment",
    },
}


def get_translation(key: str, language: str = "zh") -> str:
    """
    获取翻译文本

    Args:
        key: 翻译键
        language: 语言代码 (zh 或 en)

    Returns:
        翻译后的文本
    """
    lang = language.lower()

    if lang not in TRANSLATIONS:
        lang = "zh"

    if key in TRANSLATIONS[lang]:
        return TRANSLATIONS[lang][key]

    return key


def translate_dict(data: dict[str, Any], language: str = "zh") -> dict[str, Any]:
    """
    递归翻译字典中的文本

    Args:
        data: 要翻译的数据字典
        language: 目标语言

    Returns:
        翻译后的字典
    """
    if isinstance(data, dict):
        return {k: translate_dict(v, language) for k, v in data.items()}
    elif isinstance(data, list):
        return [translate_dict(item, language) for item in data]
    elif isinstance(data, str):
        translated = get_translation(data, language)
        return translated
    else:
        return data
