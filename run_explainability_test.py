"""直接运行可解释性测试"""

import sys
import pytest

if __name__ == "__main__":
    # 禁用 conftest 加载，避免导入问题
    sys.exit(pytest.main(["tests/analysis/test_explainability.py", "-v", "--no-header", "-rN"]))
