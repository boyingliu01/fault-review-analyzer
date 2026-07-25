#!/usr/bin/env python3
"""解析浩鲸规范库文本文件，生成结构化 JSON 规范数据。

输出到 data/standards/production/ 目录。

用法:
    python scripts/parse_standards.py
"""

import json
import re
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
STANDARDS_TXT = PROJECT_ROOT / "docs" / "规范库内容.txt"
OUTPUT_DIR = PROJECT_ROOT / "data" / "standards" / "production"

# 标题续行起始字符（PDF硬换行截断的强信号，如"必须作"+"为单例复用"）
_CONT_STARTERS = (
    "为", "了", "的", "和", "或", "与", "及", "并", "在", "于",
    "对", "将", "被", "且", "，", "、", "。", "；", "：", ")", "）",
)


def _is_break_line(line: str) -> bool:
    """判断是否为规则正文的分界行（不应拼入标题）。"""
    if not line:
        return True
    if line.startswith(("===", "正例", "反例", "说明", "检查工具", "检查⼯具", "故障警示", "浩鲸云")):
        return True
    if re.search(r"【\s*J\d+\s*】", line):
        return True
    return bool(re.match(r"^(2\.\d+)\.\s+\S", line))


def _join_multiline_title(lines: list[str], start: int, title: str) -> tuple[str, int]:
    """拼接PDF提取文本中跨行的规则标题，返回(标题, 额外消费行数)。

    拼接条件（满足其一）：
    1. 标题以逗号/顿号结尾或过短（明显截断）
    2. 下一行以续行字符开头（如"必须作"+"为..."="必须作为..."）
    """
    consumed = 0
    for k in range(1, 3):  # 最多拼接2行
        if start + k >= len(lines):
            break
        nxt = lines[start + k].strip()
        if _is_break_line(nxt):
            break
        nxt_clean = re.sub(r"\s+", " ", nxt)
        needs_join = title.endswith(("，", "、", ",")) or len(title) < 10
        if not needs_join and nxt_clean and nxt_clean[0] in _CONT_STARTERS:
            needs_join = True
        if not needs_join:
            break
        title += nxt_clean if title.endswith(("，", "、")) else " " + nxt_clean
        consumed += 1
    return title.strip(), consumed

# 子章节映射: section_number -> (subcategory_name, subcategory_id)
SUBSECTION_MAP: dict[str, tuple[str, str]] = {
    "2.1": ("集合处理", "collection"),
    "2.2": ("并发处理", "concurrency"),
    "2.3": ("控制语句", "control_flow"),
    "2.4": ("异常处理", "exception"),
    "2.5": ("资源管理", "resource"),
    "2.6": ("日志规约", "logging"),
    "2.7": ("其他", "misc"),
}

# 安全篇大章节映射: section_number -> (category_name, subcategory_prefix)
SECURITY_SECTION_MAP: dict[str, tuple[str, str]] = {
    "5": ("数据校验", "input_validation"),
    "6": ("异常行为", "exception"),
    "7": ("I/O操作", "io_security"),
    "8": ("序列化和反序列化", "serialization"),
    "9": ("平台安全", "platform_security"),
    "10": ("运行环境", "runtime_security"),
    "11": ("其他安全规则", "other_security"),
}


def parse_java_standards(lines: list[str]) -> dict:
    """解析 Java 语言编码规范（编程惯例部分）"""
    rules: list[dict] = []
    current_subcategory = ""
    current_subcategory_id = ""
    seen_ids: set[str] = set()

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测子章节标题: 2.1. 集合处理
        sub_match = re.match(r"^(2\.\d+)\.\s+(.+)", stripped)
        if sub_match and "【" not in stripped:
            sec_num = sub_match.group(1)
            if sec_num in SUBSECTION_MAP:
                current_subcategory, current_subcategory_id = SUBSECTION_MAP[sec_num]
            continue

        # 检测规则: 【J000000】强制：xxx
        rule_match = re.search(r"【\s*(J\d+)\s*】\s*(强制|推荐|参考)[：:]\s*(.*)", stripped)
        if not rule_match:
            continue

        rule_id = rule_match.group(1)
        level = rule_match.group(2)
        title_raw = rule_match.group(3).strip()

        # 去重（有些规则在文本中出现两次）
        if rule_id in seen_ids:
            continue
        seen_ids.add(rule_id)

        # 清理标题并拼接跨行部分（PDF提取文本标题常被硬换行截断）
        title = re.sub(r"\s+", " ", title_raw).strip()
        title, consumed = _join_multiline_title(lines, i, title)

        # 提取规则内容（标题后面到下一个规则之间的说明文字）
        content_lines = []
        for j in range(i + 1 + consumed, min(i + 15 + consumed, len(lines))):
            next_stripped = lines[j].strip()
            if next_stripped.startswith("==="):
                continue
            if re.search(r"【\s*J\d+\s*】", next_stripped):
                break
            if re.match(r"^(2\.\d+)\.\s+\S", next_stripped) and "【" not in next_stripped:
                break
            if next_stripped.startswith("正例") or next_stripped.startswith("反例"):
                break
            if next_stripped.startswith("检查工具") or next_stripped.startswith("检查⼯具"):
                break
            if next_stripped:
                content_lines.append(next_stripped)

        content = " ".join(content_lines[:3])  # 取前3行作为规则内容
        content = re.sub(r"\s+", " ", content).strip()

        rules.append({
            "id": rule_id,
            "category": "Java编码规范",
            "subcategory": current_subcategory or "其他",
            "title": title,
            "content": content if content else title,
            "level": level,
            "code": rule_id,
            "examples": [],
        })

    return {
        "version": "2.0",
        "category": "java_coding",
        "name": "Java编码规范（浩鲸科技）",
        "description": "浩鲸科技Java语言编码规范，涵盖集合处理、并发编程、控制语句、异常处理、资源管理、日志规约等方面",
        "source": "浩鲸在线规范库",
        "rules": rules,
    }


def parse_security_standards(lines: list[str]) -> dict:
    """解析 Java 编码规范-安全篇

    安全篇使用章节编号格式，每个章节标题就是一条规则：
    - 5.1. 校验跨信任边界传递的不可信数据
    - 5.2. #禁止直接使用不可信数据来拼接SQL语句
    - 6.1. 不要抑制或者忽略已检查异常
    - ...
    大章节: 5=数据校验, 6=异常行为, 7=I/O操作, 8=序列化和反序列化, 9=平台安全, 10=运行环境
    """
    rules: list[dict] = []
    current_section_name = ""
    current_section_id = ""
    rule_counter = 0
    seen_titles: set[str] = set()

    # 安全篇正文从 "5. 数据校验" 开始（跳过前面的目录和FAQ部分）
    start_idx = 0
    for i, l in enumerate(lines):
        if l.strip() == "5. 数据校验":
            start_idx = i
            break

    if start_idx == 0:
        # 回退：尝试找安全篇标题
        for i, l in enumerate(lines):
            if l.strip() == "Java编码规范 -安全篇":
                start_idx = i
                break

    if start_idx == 0:
        return {
            "version": "2.0", "category": "security",
            "name": "Java编码规范-安全篇", "rules": [],
        }

    # 匹配规则标题: "5.1. xxx" 或 "10.3. #xxx"
    rule_pattern = re.compile(
        r"^(\d+)\.(\d+)\.\s*(#?)(.+)"
    )
    # 匹配大章节标题: "6. 异常行为" 或 "10. 运行环境"
    section_pattern = re.compile(
        r"^(\d+)\.\s+(\S.+)"
    )
    # 用于跳过的非规则行
    skip_patterns = [
        re.compile(r"^说明[：:]"),
        re.compile(r"^正例"),
        re.compile(r"^反例"),
        re.compile(r"^例外"),
        re.compile(r"^检查⼯具"),
        re.compile(r"^检查工具"),
    ]

    for i in range(start_idx, len(lines)):
        stripped = lines[i].strip()

        # 跳过页码分隔符
        if stripped.startswith("===") or not stripped:
            continue

        # 检测大章节: "6. 异常行为", "7. I/O操作" 等
        sec_match = section_pattern.match(stripped)
        if sec_match and "." not in sec_match.group(2)[:3]:
            sec_num = sec_match.group(1)
            sec_title = sec_match.group(2).strip()
            if sec_num in SECURITY_SECTION_MAP:
                current_section_name, current_section_id = SECURITY_SECTION_MAP[sec_num]
            elif int(sec_num) <= 4:
                # 前4章是前言/术语等，跳过
                continue
            continue

        # 检测规则标题: "5.1. xxx", "10.3. #xxx"
        rule_match = rule_pattern.match(stripped)
        if not rule_match:
            continue

        major_num = rule_match.group(1)
        minor_num = rule_match.group(2)
        has_hash = rule_match.group(3) == "#"
        title_raw = rule_match.group(4).strip()

        # 只处理安全篇的章节 (5-11)
        if int(major_num) < 5 or int(major_num) > 11:
            continue

        # 跳过子子章节 (如 5.1.1, 5.3.2.1 等三级以上编号)
        if re.match(r"^\d+\.", title_raw):
            continue

        # 跳过 FAQ 章节
        if "Q1" in title_raw or "Q2" in title_raw or "Q3" in title_raw:
            continue

        # 清理标题
        title = re.sub(r"\s+", " ", title_raw).strip()
        # 如果标题太短，尝试拼接下一行
        if len(title) < 8 and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith("===") and not rule_pattern.match(next_line):
                title += " " + re.sub(r"\s+", " ", next_line).strip()

        # 跳过去重（有些标题重复出现，如 11.1）
        if title in seen_titles:
            continue
        seen_titles.add(title)

        rule_counter += 1
        rule_id = f"SEC-J{rule_counter:05d}"

        # 提取说明内容（规则标题后面的说明、正例、反例之前的文字）
        content_lines = []
        for j in range(i + 1, min(i + 20, len(lines))):
            next_stripped = lines[j].strip()
            if next_stripped.startswith("==="):
                continue
            if not next_stripped:
                continue
            # 遇到下一条规则标题则停止
            if rule_pattern.match(next_stripped):
                break
            # 遇到大章节标题则停止
            sec_m = section_pattern.match(next_stripped)
            if sec_m and "." not in sec_m.group(2)[:3]:
                break
            # 跳过代码块和示例标记
            if any(p.match(next_stripped) for p in skip_patterns):
                if next_stripped.startswith("说明"):
                    # 提取说明文字
                    desc = re.sub(r"^说明[：:]\s*", "", next_stripped).strip()
                    if desc:
                        content_lines.append(desc)
                continue
            # 收集说明性文字（排除纯代码行）
            if not next_stripped.startswith("//") and not next_stripped.startswith("{"):
                content_lines.append(next_stripped)
            if len(content_lines) >= 3:
                break

        content = " ".join(content_lines[:3])
        content = re.sub(r"\s+", " ", content).strip()

        # 确定 subcategory
        if major_num in SECURITY_SECTION_MAP:
            subcategory = SECURITY_SECTION_MAP[major_num][0]
        else:
            subcategory = current_section_name or "其他"

        rules.append({
            "id": rule_id,
            "category": "security",
            "subcategory": subcategory,
            "title": title,
            "content": content if content else title,
            "level": "强制",
            "code": rule_id,
            "examples": [],
        })

    return {
        "version": "2.0",
        "category": "security",
        "name": "Java编码规范-安全篇（浩鲸科技）",
        "description": "针对Java编程中的输入校验、异常处理、IO操作、序列化、平台安全与运行安全等安全问题的编码规范",
        "source": "浩鲸在线规范库",
        "rules": rules,
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="解析浩鲸规范库文本，生成结构化JSON")
    parser.add_argument(
        "--input",
        type=Path,
        default=STANDARDS_TXT,
        help="规范库文本文件路径（默认 docs/规范库内容.txt）",
    )
    parser.add_argument(
        "--skip-security",
        action="store_true",
        help="跳过安全篇解析（输入文本不含安全篇时使用，保留现有安全篇JSON）",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="JSON输出目录（默认 data/standards/production）",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"错误: 规范库文件不存在: {args.input}")
        return

    lines = args.input.read_text(encoding="utf-8").splitlines()
    print(f"读取规范库文件: {args.input} ({len(lines)} 行)")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 解析 Java 编码规范
    java_data = parse_java_standards(lines)
    java_file = args.output_dir / "java_coding_standards.json"
    java_file.write_text(
        json.dumps(java_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Java编码规范: {len(java_data['rules'])} 条规则 → {java_file}")

    # 2. 解析安全编码规范（可选跳过）
    if args.skip_security:
        print("安全编码规范: 已跳过（--skip-security），保留现有JSON")
        print(f"\n总计: {len(java_data['rules'])} 条Java规则")
        return

    security_data = parse_security_standards(lines)
    security_file = args.output_dir / "security_standards.json"
    security_file.write_text(
        json.dumps(security_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"安全编码规范: {len(security_data['rules'])} 条规则 → {security_file}")

    print(f"\n总计: {len(java_data['rules']) + len(security_data['rules'])} 条规则")
    print(f"输出目录: {args.output_dir}")


if __name__ == "__main__":
    main()
