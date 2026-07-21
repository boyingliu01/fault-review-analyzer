from datetime import datetime

from src.api.models import (
    CodeReview,
    DesignInfo,
    DevelopmentInfo,
    ProductionInfo,
    RequirementInfo,
    TaskInfo,
    TestingInfo,
)
from src.preprocessor.models import ProcessedTask, TextSegment


class TestDataPreprocessor:
    def test_process_task(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        assert result is not None
        assert result.task_id == 12345
        assert len(result.segments) > 0

    def test_extract_title_segment(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        title_segments = [s for s in result.segments if s.type == "title"]
        assert len(title_segments) == 1
        assert "SQL查询导致OOM" in title_segments[0].content

    def test_extract_description_segment(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        desc_segments = [s for s in result.segments if s.type == "description"]
        assert len(desc_segments) == 1

    def test_extract_commit_segments(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        commit_segments = [s for s in result.segments if s.type == "commit"]
        assert len(commit_segments) == 1
        assert "添加查询功能" in commit_segments[0].content

    def test_extract_production_segments(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        # 检查是否有生产相关的片段
        prod_segments = [
            s
            for s in result.segments
            if s.type in ["symptom", "log", "stack_trace", "resolution", "production"]
        ]
        assert len(prod_segments) > 0

    def test_combine_all_text(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        combined = result.combined_text

        assert "SQL查询导致OOM" in combined
        assert "内存溢出" in combined

    def test_empty_task(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="",
            description="",
            status="",
            create_time=datetime.now(),
        )

        result = preprocessor.process(task)

        assert result is not None
        assert result.task_id == 1

    def test_segment_metadata(self, preprocessor, sample_task):
        result = preprocessor.process(sample_task)

        for segment in result.segments:
            assert segment.task_id == 12345
            assert segment.type is not None
            assert segment.content is not None


class TestTextSegment:
    def test_create_segment(self):
        segment = TextSegment(
            task_id=12345,
            type="title",
            content="Test content",
            metadata={"source": "api"},
        )

        assert segment.task_id == 12345
        assert segment.type == "title"
        assert segment.content == "Test content"

    def test_segment_with_empty_metadata(self):
        segment = TextSegment(
            task_id=1,
            type="description",
            content="Test",
        )

        assert segment.metadata == {}


class TestProcessedTask:
    def test_create_processed_task(self):
        task = ProcessedTask(
            task_id=12345,
            segments=[
                TextSegment(task_id=12345, type="title", content="Test"),
            ],
            combined_text="Test",
        )

        assert task.task_id == 12345
        assert len(task.segments) == 1

    def test_get_segments_by_type(self):
        task = ProcessedTask(
            task_id=1,
            segments=[
                TextSegment(task_id=1, type="title", content="Title"),
                TextSegment(task_id=1, type="description", content="Desc"),
                TextSegment(task_id=1, type="title", content="Title2"),
            ],
            combined_text="Title Desc Title2",
        )

        titles = task.get_segments_by_type("title")

        assert len(titles) == 2

    def test_process_batch(self, preprocessor, sample_task):
        tasks = [sample_task, sample_task]
        results = preprocessor.process_batch(tasks)
        assert len(results) == 2

    def test_process_batch_preserves_all_tasks(self, preprocessor):
        """process_batch 应保持与输入列表一一对应，不过滤空任务。"""
        task = TaskInfo(
            task_id=1,
            title="",
            description="",
            status="",
            create_time=datetime.now(),
        )
        results = preprocessor.process_batch([task])
        assert len(results) == 1  # 不再过滤，保持一一对应

    def test_truncate_text(self, preprocessor, sample_task):
        preprocessor.max_text_length = 50
        result = preprocessor.process(sample_task)
        assert len(result.combined_text) <= 53

    def test_task_with_requirement(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            create_time=datetime.now(),
            requirement=RequirementInfo(
                description="需求文档内容",
            ),
        )
        result = preprocessor.process(task)
        req_segments = [s for s in result.segments if s.type == "requirement"]
        assert len(req_segments) == 1

    def test_task_with_design(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            create_time=datetime.now(),
            design=DesignInfo(
                design_document="设计文档内容",
            ),
        )
        result = preprocessor.process(task)
        design_segments = [s for s in result.segments if s.type == "design"]
        assert len(design_segments) == 1

    def test_task_with_testing(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            create_time=datetime.now(),
            testing=TestingInfo(
                test_cases=["测试用例1", "测试用例2"],
                defects=["缺陷1"],
            ),
        )
        result = preprocessor.process(task)
        test_segments = [s for s in result.segments if s.type in ["test_case", "defect"]]
        assert len(test_segments) == 3

    def test_task_with_code_review(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            create_time=datetime.now(),
            development=DevelopmentInfo(
                commits=[],
                code_reviews=[
                    CodeReview(
                        reviewer="reviewer1",
                        time=datetime.now(),
                        approved=True,
                        comments=["comment1"],
                    )
                ],
            ),
        )
        result = preprocessor.process(task)
        review_segments = [s for s in result.segments if s.type == "code_review"]
        assert len(review_segments) == 1

    def test_production_with_no_symptoms(self, preprocessor):
        task = TaskInfo(
            task_id=1,
            title="Test",
            description="Test",
            status="open",
            create_time=datetime.now(),
            production=ProductionInfo(
                incident_time=datetime.now(),
                symptoms="",
                logs=[],
                stack_traces=[],
                resolution="",
            ),
        )
        result = preprocessor.process(task)
        prod_segments = [s for s in result.segments if s.type in ["production", "symptom"]]
        assert len(prod_segments) > 0
