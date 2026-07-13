"""反馈管理器"""
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from src.feedback.models import Feedback, FeedbackRating, FeedbackType


class FeedbackManager:
    """反馈管理器"""

    def __init__(self, db_path: str = "data/feedback.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建反馈表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    original_result TEXT NOT NULL,
                    corrected_result TEXT,
                    rating INTEGER NOT NULL,
                    comment TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    reviewed INTEGER NOT NULL DEFAULT 0,
                    reviewed_by TEXT,
                    reviewed_at TEXT
                )
            """)

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_task_id ON feedback(task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_type ON feedback(feedback_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_rating ON feedback(rating)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_reviewed ON feedback(reviewed)")

            conn.commit()

        logger.debug(f"Feedback database initialized at {self.db_path}")

    def add_feedback(self, feedback: Feedback) -> str:
        """添加反馈"""
        import json

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO feedback (
                    id, task_id, feedback_type, original_result, corrected_result,
                    rating, comment, created_by, created_at, reviewed, reviewed_by, reviewed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                feedback.id,
                feedback.task_id,
                feedback.feedback_type.value,
                json.dumps(feedback.original_result),
                json.dumps(feedback.corrected_result) if feedback.corrected_result else None,
                feedback.rating.value,
                feedback.comment,
                feedback.created_by,
                feedback.created_at.isoformat(),
                1 if feedback.reviewed else 0,
                feedback.reviewed_by,
                feedback.reviewed_at.isoformat() if feedback.reviewed_at else None
            ))
            conn.commit()

        logger.debug(f"Feedback added: {feedback.id}")
        return feedback.id

    def get_feedback(self, feedback_id: str) -> Feedback | None:
        """获取反馈"""
        import json

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM feedback WHERE id = ?
            """, (feedback_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return Feedback(
                id=row["id"],
                task_id=row["task_id"],
                feedback_type=FeedbackType(row["feedback_type"]),
                original_result=json.loads(row["original_result"]),
                corrected_result=json.loads(row["corrected_result"]) if row["corrected_result"] else None,
                rating=FeedbackRating(row["rating"]),
                comment=row["comment"],
                created_by=row["created_by"],
                created_at=self._parse_datetime(row["created_at"]),
                reviewed=bool(row["reviewed"]),
                reviewed_by=row["reviewed_by"],
                reviewed_at=self._parse_datetime(row["reviewed_at"]) if row["reviewed_at"] else None
            )

    def get_feedback_by_task(self, task_id: str) -> list[Feedback]:
        """获取任务的所有反馈"""
        import json

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM feedback WHERE task_id = ? ORDER BY created_at DESC
            """, (task_id,))
            rows = cursor.fetchall()

            return [
                Feedback(
                    id=row["id"],
                    task_id=row["task_id"],
                    feedback_type=FeedbackType(row["feedback_type"]),
                    original_result=json.loads(row["original_result"]),
                    corrected_result=json.loads(row["corrected_result"]) if row["corrected_result"] else None,
                    rating=FeedbackRating(row["rating"]),
                    comment=row["comment"],
                    created_by=row["created_by"],
                    created_at=self._parse_datetime(row["created_at"]),
                    reviewed=bool(row["reviewed"]),
                    reviewed_by=row["reviewed_by"],
                    reviewed_at=self._parse_datetime(row["reviewed_at"]) if row["reviewed_at"] else None
                ) for row in rows
            ]

    def list_feedback(
        self,
        feedback_type: FeedbackType | None = None,
        rating: FeedbackRating | None = None,
        reviewed: bool | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> list[Feedback]:
        """列出反馈"""
        import json

        query = "SELECT * FROM feedback WHERE 1=1"
        params = []

        if feedback_type:
            query += " AND feedback_type = ?"
            params.append(feedback_type.value)

        if rating:
            query += " AND rating = ?"
            params.append(rating.value)

        if reviewed is not None:
            query += " AND reviewed = ?"
            params.append(1 if reviewed else 0)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            return [
                Feedback(
                    id=row["id"],
                    task_id=row["task_id"],
                    feedback_type=FeedbackType(row["feedback_type"]),
                    original_result=json.loads(row["original_result"]),
                    corrected_result=json.loads(row["corrected_result"]) if row["corrected_result"] else None,
                    rating=FeedbackRating(row["rating"]),
                    comment=row["comment"],
                    created_by=row["created_by"],
                    created_at=self._parse_datetime(row["created_at"]),
                    reviewed=bool(row["reviewed"]),
                    reviewed_by=row["reviewed_by"],
                    reviewed_at=self._parse_datetime(row["reviewed_at"]) if row["reviewed_at"] else None
                ) for row in rows
            ]

    def review_feedback(
        self,
        feedback_id: str,
        reviewed_by: str
    ) -> bool:
        """审核反馈"""
        from datetime import datetime

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE feedback
                SET reviewed = 1, reviewed_by = ?, reviewed_at = ?
                WHERE id = ?
            """, (reviewed_by, datetime.now().isoformat(), feedback_id))
            conn.commit()

            return cursor.rowcount > 0

    def get_statistics(self) -> dict[str, Any]:
        """获取反馈统计"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 总反馈数
            cursor.execute("SELECT COUNT(*) FROM feedback")
            total_feedback = cursor.fetchone()[0]

            # 按类型统计
            cursor.execute("""
                SELECT feedback_type, COUNT(*)
                FROM feedback
                GROUP BY feedback_type
            """)
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            # 按评分统计
            cursor.execute("""
                SELECT rating, COUNT(*)
                FROM feedback
                GROUP BY rating
            """)
            by_rating = {int(row[0]): row[1] for row in cursor.fetchall()}

            # 已审核数
            cursor.execute("SELECT COUNT(*) FROM feedback WHERE reviewed = 1")
            reviewed_count = cursor.fetchone()[0]

            # 计算纠错率和好评率
            correction_count = 0
            positive_count = 0

            if total_feedback > 0:
                # 纠错类型反馈数
                correction_count = by_type.get("label_correction", 0) + by_type.get("root_cause_correction", 0)

                # 好评数（4分及以上）
                positive_count = sum(
                    by_rating.get(rating, 0) for rating in [4, 5]
                )

            correction_ratio = correction_count / total_feedback if total_feedback > 0 else 0.0
            positive_ratio = positive_count / total_feedback if total_feedback > 0 else 0.0

            return {
                "total_feedback": total_feedback,
                "by_type": by_type,
                "by_rating": by_rating,
                "reviewed_count": reviewed_count,
                "correction_ratio": correction_ratio,
                "positive_ratio": positive_ratio,
            }

    def _parse_datetime(self, date_str: str):
        """解析日期时间字符串"""
        from datetime import datetime
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception as e:
            logger.error(f"Failed to parse datetime: {date_str}, error: {e}")
            return datetime.now()

    def close(self) -> None:
        """关闭数据库连接（SQLite不需要显式关闭）"""
        pass
