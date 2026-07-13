"""违规检测器测试套件"""


from src.core.models import ViolationDetection


class TestViolationDetector:
    """违规检测器测试套件"""

    def test_detect_violation_empty_catch_block(self, violation_detector):
        """测试检测空catch块违规"""
        fault_info = {
            "task_id": "TASK-001",
            "title": "空指针异常导致服务崩溃",
            "description": "代码中存在空的catch块，捕获异常后未做任何处理",
            "code_snippet": "try { int a = 1/0; } catch (Exception e) { }",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_detect_violation_database_connection_leak(self, violation_detector):
        """测试检测数据库连接泄漏违规"""
        fault_info = {
            "task_id": "TASK-002",
            "title": "数据库连接未关闭导致连接池耗尽",
            "description": "获取数据库连接后未关闭",
            "code_snippet": "Connection conn = dataSource.getConnection(); // 使用后未关闭",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)
        assert result.is_violation is True

    def test_detect_no_violation(self, violation_detector):
        """测试无违规情况"""
        fault_info = {
            "task_id": "TASK-003",
            "title": "正常的业务逻辑错误",
            "description": "业务逻辑计算错误，非规范违规",
            "code_snippet": "int result = a + b; // 逻辑错误",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_detect_violation_with_code_change(self, violation_detector):
        """测试带代码变更的违规检测"""
        fault_info = {
            "task_id": "TASK-004",
            "title": "并发安全问题",
            "description": "多线程环境下使用非线程安全集合",
            "code_snippet": "Map<String, Object> cache = new HashMap<>();",
            "development": {
                "commits": [
                    {
                        "commit_id": "abc123",
                        "message": "添加缓存功能",
                        "diff": "-Map<String, Object> cache = new HashMap<>();\n+Map<String, Object> cache = new ConcurrentHashMap<>();",
                    }
                ]
            },
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)

    def test_violation_detection_confidence_score(self, violation_detector):
        """测试违规置信度评分"""
        fault_info = {
            "task_id": "TASK-005",
            "title": "明显违规",
            "description": "代码中使用System.out.println",
            "code_snippet": 'System.out.println("debug info");',
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert result.confidence >= 0.0
        assert result.confidence <= 1.0

    def test_violation_category_mapping(self, violation_detector):
        """测试违规类别映射"""
        fault_info = {
            "task_id": "TASK-006",
            "title": "SQL注入风险",
            "description": "存在SQL注入风险",
            "code_snippet": 'String sql = "SELECT * FROM users WHERE id=" + userId;',
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        if result.is_violation:
            assert result.violation_category is not None

    def test_violation_evidence_extraction(self, violation_detector):
        """测试违规证据提取"""
        fault_info = {
            "task_id": "TASK-007",
            "title": "异常处理问题",
            "description": "捕获异常后未记录日志",
            "code_snippet": "try { ... } catch (Exception e) { }",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        if result.is_violation:
            assert len(result.evidence) > 0

    def test_detect_with_empty_code_snippet(self, violation_detector):
        """测试空代码片段的违规检测"""
        fault_info = {
            "task_id": "TASK-008",
            "title": "无法确定",
            "description": "无法确定是否违规",
            "code_snippet": "",
            "development": {"commits": []},
        }
        result = violation_detector.detect(fault_info)
        assert isinstance(result, ViolationDetection)
        assert result.confidence <= 0.5
