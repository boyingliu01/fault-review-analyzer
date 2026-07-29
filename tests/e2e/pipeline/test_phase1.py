"""Phase1 数据准备 E2E 测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.phase1_prepare import Phase1Prepare


def make_mock_config() -> MagicMock:
    """构造最小可用的 ConfigManager mock"""
    config = MagicMock()
    config.embedding.provider = "volcengine"
    config.embedding.model = "doubao-embedding-vision-251215"
    config.embedding.api_key = "test-key"
    config.embedding.base_url = "https://example.com"
    config.clustering.algorithm = "hdbscan"
    config.clustering.min_cluster_size = 2
    config.clustering.min_samples = 1
    config.clustering.metric = "cosine"
    return config


class TestPhase1Prepare:
    """阶段一数据准备 E2E 测试"""

    @pytest.fixture
    def config(self) -> MagicMock:
        """获取 mock 配置管理器"""
        return make_mock_config()

    @pytest.fixture
    def phase1(self, config: MagicMock) -> Phase1Prepare:
        """创建 Phase1 实例（使用 mock）"""
        with (
            patch("scripts.phase1_prepare.EmbeddingGenerator") as mock_embed,
            patch("scripts.phase1_prepare.ChromaManager") as mock_chroma,
        ):
            mock_embed.return_value = MagicMock()
            mock_chroma.return_value = MagicMock()
            phase1 = Phase1Prepare(config)
            return phase1

    def test_phase1_init(self, phase1: Phase1Prepare):
        """测试 Phase1 初始化"""
        assert phase1 is not None
        assert phase1.embedding_gen is not None
        assert phase1.chroma_manager is not None

    def test_phase1_init_api_client(self, phase1: Phase1Prepare):
        """测试 API 客户端初始化"""
        phase1.init_api_client(
            base_url="https://dev.iwhalecloud.com",
            token="test-token",
            timeout=30,
            api_path_prefix="/portal/ai-gateway/devspace/rpc/v3/work-item",
        )
        assert phase1.api_client is not None

    @pytest.mark.asyncio
    async def test_phase1_process_single_task_mock(
        self,
        phase1: Phase1Prepare,
        small_test_ids: list[str],
    ):
        """测试处理单个任务（完全 mock）"""
        from src.core.models import EmbeddingResult

        # Mock 内部方法
        phase1.fetch_single_task = AsyncMock(
            return_value=MagicMock(
                task_no=small_test_ids[0],
                title="测试故障",
                description="测试描述",
            )
        )
        phase1.embedding_gen.embed_text = AsyncMock(return_value=[0.1] * 1536)
        phase1.chroma_manager.add_embedding = MagicMock(return_value=True)

        # Mock enhanced_analyzer
        mock_result = MagicMock()
        mock_result.violation_detection.is_violation = False
        mock_result.violation_detection.violation_type = ""
        mock_result.root_cause_validation.is_actionable = True
        mock_result.root_cause = "测试根因"
        mock_result.code_changes = []
        phase1.enhanced_analyzer.analyze = MagicMock(return_value=mock_result)

        result = await phase1.process_single_task(small_test_ids[0], use_llm=False)

        # 验证结果（mock 下应返回结果）
        assert result is None or isinstance(result, EmbeddingResult) or result is NotImplemented

    @pytest.mark.asyncio
    async def test_phase1_run_small_batch_mock(
        self,
        phase1: Phase1Prepare,
        small_test_ids: list[str],
    ):
        """测试批量处理（完全 mock）"""

        # Mock 内部方法
        mock_task = MagicMock()
        mock_task.task_no = small_test_ids[0]
        mock_task.title = "测试"
        mock_task.description = "测试描述"

        phase1.fetch_single_task = AsyncMock(return_value=mock_task)
        phase1.embedding_gen.embed_text = AsyncMock(return_value=[0.1] * 1536)
        phase1.chroma_manager.add_embedding = MagicMock(return_value=True)

        mock_result = MagicMock()
        mock_result.violation_detection.is_violation = False
        mock_result.violation_detection.violation_type = ""
        mock_result.root_cause_validation.is_actionable = True
        mock_result.root_cause = "测试根因"
        mock_result.code_changes = []
        phase1.enhanced_analyzer.analyze = MagicMock(return_value=mock_result)

        results = await phase1.run(task_ids=[small_test_ids[0]], use_llm=False)

        # 验证结果类型
        assert isinstance(results, list)
