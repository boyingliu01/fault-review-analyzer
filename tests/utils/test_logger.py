"""日志记录器测试"""

import json

from src.utils.logger import (
    StructuredLogger,
    get_correlation_id,
    get_logger,
    setup_logger,
)


class TestSetupLogger:
    """测试日志记录器设置"""

    def test_setup_console_logger(self):
        """测试设置控制台日志记录器"""
        setup_logger(level="INFO", log_file=None, json_format=False)
        logger = get_logger("test")

        # 验证可以正常记录日志
        logger.info("Test message")

    def test_setup_json_logger(self, capsys):
        """测试设置 JSON 格式日志记录器"""
        setup_logger(level="INFO", log_file=None, json_format=True)
        logger = get_logger("test")

        logger.info("Test message", task_id="12345", correlation_id="abc-123")

        # 捕获输出（loguru 使用 stderr）
        captured = capsys.readouterr()
        assert captured.err.strip() != ""

        # 验证是有效的 JSON
        lines = captured.err.strip().splitlines()
        assert len(lines) == 1
        log_json = json.loads(lines[0])
        assert log_json["message"] == "Test message"
        assert log_json["level"] == "INFO"
        assert log_json["task_id"] == "12345"
        assert log_json["correlation_id"] == "abc-123"

    def test_setup_file_logger(self, tmp_path):
        """测试设置文件日志记录器"""
        log_file = tmp_path / "test.log"
        setup_logger(level="INFO", log_file=str(log_file), json_format=False)
        logger = get_logger("test")

        test_message = "File logger test message"
        logger.info(test_message)

        # 验证日志已写入文件
        assert log_file.exists()
        with open(log_file, encoding="utf-8") as f:
            content = f.read()
            assert test_message in content


class TestGetLogger:
    """测试获取日志记录器"""

    def test_get_named_logger(self):
        """测试获取命名的日志记录器"""
        logger1 = get_logger("test1")
        logger2 = get_logger("test2")
        assert logger1 is not logger2

    def test_get_default_logger(self):
        """测试获取默认日志记录器"""
        logger = get_logger()
        assert logger is not None


class TestGetCorrelationId:
    """测试 correlation_id 生成"""

    def test_correlation_id_format(self):
        """测试 correlation_id 格式是有效的 UUID"""
        import uuid

        for _ in range(10):
            corr_id = get_correlation_id()
            assert isinstance(corr_id, str)
            # 验证是有效的 UUID v4
            uuid_obj = uuid.UUID(corr_id)
            assert uuid_obj.version == 4

    def test_correlation_id_uniqueness(self):
        """测试 correlation_id 是唯一的"""
        ids = set()
        for _ in range(100):
            corr_id = get_correlation_id()
            assert corr_id not in ids
            ids.add(corr_id)


class TestStructuredLogger:
    """测试结构化日志记录器"""

    def test_structured_logger_methods(self, capsys):
        """测试结构化日志记录器的方法"""
        setup_logger(level="DEBUG", json_format=True)
        logger = StructuredLogger("structured_test")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        captured = capsys.readouterr()
        lines = captured.err.strip().splitlines()
        assert len(lines) == 5

        levels = set()
        for line in lines:
            log_json = json.loads(line)
            levels.add(log_json["level"])

        assert {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}.issubset(levels)

    def test_structured_logger_bindings(self, capsys):
        """测试结构化日志记录器的绑定属性"""
        setup_logger(level="INFO", json_format=True)
        logger = StructuredLogger("structured_test")

        logger.info("Task completed", task_id="12345", status="success")

        captured = capsys.readouterr()
        log_json = json.loads(captured.err.strip())

        assert log_json["message"] == "Task completed"
        assert log_json["task_id"] == "12345"
        assert log_json["status"] == "success"


class TestLoggerLevels:
    """测试日志级别"""

    def test_log_levels(self, capsys):
        """测试不同级别的日志记录"""
        setup_logger(level="DEBUG", json_format=True)
        logger = get_logger("levels_test")

        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        captured = capsys.readouterr()
        assert len(captured.err.strip().splitlines()) == 5

    def test_level_filtering(self, capsys):
        """测试日志级别过滤"""
        setup_logger(level="WARNING", json_format=True)
        logger = get_logger("filter_test")

        logger.debug("Debug message - should not appear")
        logger.info("Info message - should not appear")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        captured = capsys.readouterr()
        lines = captured.err.strip().splitlines()
        assert len(lines) == 3

        for line in lines:
            log_json = json.loads(line)
            level_name = log_json["level"]
            assert level_name in ["WARNING", "ERROR", "CRITICAL"]
