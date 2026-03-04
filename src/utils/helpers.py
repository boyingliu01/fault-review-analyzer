import re
from datetime import datetime


def truncate_text(text: str, max_length: int = 1000) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def sanitize_text(text: str) -> str:
    result = []
    for char in text:
        if ord(char) < 32:
            if char in "\n\r\t":
                result.append(char)
        else:
            result.append(char)
    return "".join(result)


def format_datetime(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        return ""
    return dt.strftime(fmt)


def extract_code_blocks(text: str) -> list[str]:
    pattern = r"```[\w]*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [match.strip() for match in matches]


def extract_stack_traces(text: str) -> list[str]:
    patterns = [
        r"(?:Exception|Error|Traceback)[\s\S]*?(?=\n\n|\Z)",
        r"at\s+[\w.]+\([^)]*\)",
        r"[\w.]+Exception:\s*[^\n]+",
    ]

    traces = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        traces.extend(matches)

    return traces


def extract_sql_queries(text: str) -> list[str]:
    keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"]
    pattern = r"\b(" + "|".join(keywords) + r")\b[\s\S]*?(?=;|$)"

    matches = re.findall(pattern, text, re.IGNORECASE)
    return [match.strip() for match in matches if match.strip()]


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def count_tokens_estimate(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if end < len(text) and overlap > 0:
            last_space = chunk.rfind(" ")
            if last_space != -1 and last_space > chunk_size - overlap:
                end = start + last_space
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end - overlap if end < len(text) else end

    return [c for c in chunks if c]
