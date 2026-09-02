"""introduceTaskNo（引入缺陷任务单号）解析防回归测试。

背景（故障单 11757372）：泄漏缺陷单未强制填写引入单号时，复盘无法追溯
缺陷引入的真实代码变更。引入单号接入后：
- 详情接口响应中若回显 introduceTaskNo，TaskInfo 必须携带
- 单据未填写/响应缺失时防御性降级为 None（详情接口响应是否回显取决于
  服务端版本，不得因字段缺失而中断解析）
"""

from src.api.client import APIClient


class TestParseIntroduceTaskNo:
    """_parse_introduce_task_no 提取矩阵"""

    def setup_method(self):
        self.client = APIClient(base_url="https://api.example.com", api_key="k")

    def test_extracts_string_no(self):
        assert (
            self.client._parse_introduce_task_no({"introduceTaskNo": "11758001"})
            == "11758001"
        )

    def test_extracts_numeric_no_as_string(self):
        """API 返回数字单号时归一化为字符串"""
        assert (
            self.client._parse_introduce_task_no({"introduceTaskNo": 11758001})
            == "11758001"
        )

    def test_missing_field_returns_none(self):
        """详情接口响应未回显 introduceTaskNo → None（不中断解析）"""
        assert self.client._parse_introduce_task_no({"taskId": 1}) is None

    def test_none_value_returns_none(self):
        assert self.client._parse_introduce_task_no({"introduceTaskNo": None}) is None

    def test_empty_string_returns_none(self):
        assert self.client._parse_introduce_task_no({"introduceTaskNo": ""}) is None

    def test_whitespace_only_returns_none(self):
        assert self.client._parse_introduce_task_no({"introduceTaskNo": "  "}) is None

    def test_parse_task_carries_introduce_task_no(self):
        """_parse_task 全链路：响应含 introduceTaskNo 时 TaskInfo 携带"""
        payload = {
            "data": {
                "apiTask": {
                    "taskId": 11757372,
                    "taskTitle": "号码接口报错",
                    "comments": "描述",
                    "createdDate": "2026-08-27 10:00:00",
                    "introduceTaskNo": "11758001",
                }
            }
        }
        task = self.client._parse_task(payload)
        assert task.introduce_task_no == "11758001"

    def test_parse_task_without_introduce_task_no_defaults_none(self):
        """响应缺失 introduceTaskNo 时 TaskInfo.introduce_task_no 为 None"""
        payload = {
            "data": {
                "apiTask": {
                    "taskId": 11757372,
                    "taskTitle": "号码接口报错",
                    "comments": "描述",
                    "createdDate": "2026-08-27 10:00:00",
                }
            }
        }
        task = self.client._parse_task(payload)
        assert task.introduce_task_no is None
