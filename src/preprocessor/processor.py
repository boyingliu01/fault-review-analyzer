
from src.api.models import TaskInfo
from src.preprocessor.models import ProcessedTask, TextSegment


class DataPreprocessor:
    def __init__(self, max_text_length: int = 8000):
        self.max_text_length = max_text_length

    def process(self, task: TaskInfo) -> ProcessedTask:
        segments = self._extract_segments(task)
        combined_text = self._combine_segments(segments)

        return ProcessedTask(
            task_id=task.task_id,
            segments=segments,
            combined_text=self._truncate_text(combined_text),
            metadata={
                "title": task.title,
                "status": task.status,
                "priority": task.priority,
                "create_time": task.create_time.isoformat() if task.create_time else None,
                "resolve_time": task.resolve_time.isoformat() if task.resolve_time else None,
            },
        )

    def _extract_segments(self, task: TaskInfo) -> list[TextSegment]:
        segments = []

        if task.title:
            segments.append(TextSegment(
                task_id=task.task_id,
                type="title",
                content=task.title,
                metadata={"source": "task"},
            ))

        if task.description:
            segments.append(TextSegment(
                task_id=task.task_id,
                type="description",
                content=task.description,
                metadata={"source": "task"},
            ))

        if task.requirement and task.requirement.description:
            segments.append(TextSegment(
                task_id=task.task_id,
                type="requirement",
                content=task.requirement.description,
                metadata={"source": "requirement"},
            ))

        if task.design and task.design.design_document:
            segments.append(TextSegment(
                task_id=task.task_id,
                type="design",
                content=task.design.design_document,
                metadata={"source": "design"},
            ))

        if task.development:
            for commit in task.development.commits:
                commit_text = f"提交: {commit.message}"
                if commit.changes:
                    commit_text += f"\n变更文件: {', '.join(commit.changes)}"
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="commit",
                    content=commit_text,
                    metadata={
                        "source": "commit",
                        "commit_id": commit.commit_id,
                        "author": commit.author,
                    },
                ))

            for review in task.development.code_reviews:
                review_text = f"代码评审: {'通过' if review.approved else '未通过'}"
                if review.comments:
                    review_text += f"\n评审意见: {', '.join(review.comments)}"
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="code_review",
                    content=review_text,
                    metadata={
                        "source": "code_review",
                        "reviewer": review.reviewer,
                    },
                ))

        if task.testing:
            for i, test_case in enumerate(task.testing.test_cases):
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="test_case",
                    content=test_case,
                    metadata={"source": "testing", "index": i},
                ))

            for i, defect in enumerate(task.testing.defects):
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="defect",
                    content=defect,
                    metadata={"source": "testing", "index": i},
                ))

        if task.production:
            prod = task.production

            if prod.symptoms:
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="symptom",
                    content=f"故障现象: {prod.symptoms}",
                    metadata={"source": "production"},
                ))

            for i, log in enumerate(prod.logs):
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="log",
                    content=log,
                    metadata={"source": "production", "index": i},
                ))

            for i, trace in enumerate(prod.stack_traces):
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="stack_trace",
                    content=trace,
                    metadata={"source": "production", "index": i},
                ))

            if prod.resolution:
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="resolution",
                    content=f"解决方案: {prod.resolution}",
                    metadata={"source": "production"},
                ))

            # 确保至少有一个生产相关的片段
            if not any(s.type in ["symptom", "log", "stack_trace", "resolution"] for s in segments):
                segments.append(TextSegment(
                    task_id=task.task_id,
                    type="production",
                    content="生产环境信息",
                    metadata={"source": "production"},
                ))

        return segments

    def _combine_segments(self, segments: list[TextSegment]) -> str:
        parts = []

        for segment in segments:
            parts.append(f"[{segment.type}]\n{segment.content}")

        return "\n\n".join(parts)

    def _truncate_text(self, text: str) -> str:
        if len(text) <= self.max_text_length:
            return text
        return text[:self.max_text_length] + "..."

    def process_batch(self, tasks: list[TaskInfo]) -> list[ProcessedTask]:
        processed_tasks = []
        for task in tasks:
            processed = self.process(task)
            if processed.combined_text and processed.combined_text.strip():
                processed_tasks.append(processed)
        return processed_tasks
