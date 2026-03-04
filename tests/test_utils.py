
import gc

from loguru import logger

from src.utils.helpers import (
    chunk_text,
    count_tokens_estimate,
    extract_code_blocks,
    extract_sql_queries,
    extract_stack_traces,
    format_datetime,
    normalize_whitespace,
    sanitize_text,
    truncate_text,
)
from src.utils.logger import get_logger, setup_logger


class TestLogger:
    def test_setup_logger(self, temp_dir):
        log_file = temp_dir / "test.log"

        setup_logger(level="DEBUG", log_file=str(log_file))

        test_logger = get_logger("test")
        test_logger.info("Test message")

        assert log_file.exists()
        logger.remove()
        gc.collect()

    def test_logger_level(self, temp_dir):
        log_file = temp_dir / "test.log"
        setup_logger(level="WARNING", log_file=str(log_file))

        test_logger = get_logger("test")
        test_logger.debug("Debug message")
        test_logger.warning("Warning message")

        content = log_file.read_text()
        assert "Debug message" not in content
        assert "Warning message" in content
        logger.remove()
        gc.collect()


class TestHelpers:
    def test_truncate_text_short(self):
        text = "Short text"
        result = truncate_text(text, max_length=100)
        assert result == text

    def test_truncate_text_long(self):
        text = "A" * 200
        result = truncate_text(text, max_length=100)
        assert len(result) == 103
        assert result.endswith("...")

    def test_sanitize_text(self):
        text = "Hello\x00World\nNewLine\tTab"
        result = sanitize_text(text)
        assert "\x00" not in result
        assert "\n" in result
        assert "\t" in result

    def test_sanitize_text_remove_control_chars(self):
        text = "Hello\x1b\x1c\x1dWorld"
        result = sanitize_text(text)
        assert result == "HelloWorld"

    def test_format_datetime(self):
        from datetime import datetime

        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = format_datetime(dt)

        assert result == "2024-01-15 10:30:45"

    def test_format_datetime_none(self):
        result = format_datetime(None)
        assert result == ""

    def test_extract_code_blocks(self):
        text = '''
Here is some code:
```python
def hello():
    print("Hello World")
```
And more text.
'''
        result = extract_code_blocks(text)
        assert len(result) == 1
        assert 'def hello():' in result[0]

    def test_extract_code_blocks_multiple(self):
        text = '''
```python
code1
```
some text
```javascript
code2
```
'''
        result = extract_code_blocks(text)
        assert len(result) == 2

    def test_extract_stack_traces(self):
        text = '''
Exception in thread "main" java.lang.NullPointerException
    at com.example.Main.main(Main.java:10)
RuntimeError: Something went wrong
'''
        result = extract_stack_traces(text)
        assert len(result) > 0

    def test_extract_sql_queries(self):
        text = '''
SELECT * FROM users WHERE id = 1;
INSERT INTO logs VALUES ('test');
UPDATE users SET name = 'test';
'''
        result = extract_sql_queries(text)
        assert len(result) >= 3

    def test_normalize_whitespace(self):
        text = "Hello    World\n\nTest"
        result = normalize_whitespace(text)
        assert result == "Hello World Test"

    def test_count_tokens_estimate(self):
        text = "This is a test sentence"
        result = count_tokens_estimate(text)
        assert result == 5

    def test_chunk_text_short(self):
        text = "Short text"
        result = chunk_text(text, chunk_size=100)
        assert result == ["Short text"]

    def test_chunk_text_long(self):
        text = "A" * 2000
        result = chunk_text(text, chunk_size=500, overlap=50)
        assert len(result) > 1

    def test_chunk_text_no_spaces(self):
        text = "A" * 2000
        result = chunk_text(text, chunk_size=500, overlap=50)
        assert len(result) > 0
