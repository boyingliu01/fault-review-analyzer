"""Streamlit 应用测试套件"""

from unittest.mock import MagicMock, patch

from src.ui.streamlit_app import FaultAnalysisUI


class TestFaultAnalysisUI:
    """故障分析 UI 测试"""

    def test_create_ui(self):
        """测试创建 UI 实例"""
        with patch("src.ui.streamlit_app.ChromaManager"):
            ui = FaultAnalysisUI()
            assert ui is not None

    def test_load_all_embeddings(self):
        """测试加载嵌入向量"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            # 模拟 ChromaManager
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1, 0.2], [0.3, 0.4]],
                "metadatas": [{"task_id": "T1"}, {"task_id": "T2"}],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            ui = FaultAnalysisUI()
            embeddings, metadatas = ui._load_all_embeddings()

            assert len(embeddings) == 2
            assert len(metadatas) == 2
            assert metadatas[0]["task_id"] == "T1"

    def test_load_all_embeddings_empty(self):
        """测试加载空数据"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [],
                "metadatas": [],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            ui = FaultAnalysisUI()
            embeddings, metadatas = ui._load_all_embeddings()

            assert len(embeddings) == 0
            assert len(metadatas) == 0

    def test_load_all_embeddings_error(self):
        """测试加载失败"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_chroma.return_value.get_or_create_collection.side_effect = Exception("连接失败")

            ui = FaultAnalysisUI()
            embeddings, metadatas = ui._load_all_embeddings()

            assert len(embeddings) == 0
            assert len(metadatas) == 0


class TestStreamlitComponents:
    """Streamlit 组件测试"""

    @patch("src.ui.streamlit_app.st")
    def test_page_navigation(self, mock_st):
        """测试页面导航"""
        with patch("src.ui.streamlit_app.ChromaManager"):
            mock_st.radio.return_value = "📊 数据概览"
            mock_st.session_state = {}

            ui = FaultAnalysisUI()
            ui._render_sidebar()

            # 验证 radio 被调用
            mock_st.radio.assert_called_once()

    @patch("src.ui.streamlit_app.st")
    def test_overview_page(self, mock_st):
        """测试概览页面"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1] * 2048],
                "metadatas": [
                    {
                        "task_id": "TASK-001",
                        "introduce_phase": "开发",
                        "has_violation": True,
                        "root_cause": "代码bug",
                    }
                ],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            ui = FaultAnalysisUI()
            ui._render_overview()

            # 验证标题被设置
            mock_st.title.assert_called()

    @patch("src.ui.streamlit_app.st")
    def test_overview_page_empty(self, mock_st):
        """测试空数据概览页面"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [],
                "metadatas": [],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            ui = FaultAnalysisUI()
            ui._render_overview()

            # 验证警告被显示
            mock_st.warning.assert_called_once()


class TestClusteringPage:
    """聚类分析页面测试"""

    @patch("src.ui.streamlit_app.st")
    def test_clustering_page_no_data(self, mock_st):
        """测试无数据时的聚类页面"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [],
                "metadatas": [],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            mock_st.selectbox.return_value = "hdbscan"
            mock_st.button.return_value = True
            mock_st.columns.return_value = [MagicMock(), MagicMock()]

            ui = FaultAnalysisUI()
            ui._render_clustering()

            # 应该显示警告
            mock_st.warning.assert_called()


class TestImprovementsPage:
    """改进措施页面测试"""

    @patch("src.ui.streamlit_app.st")
    def test_improvements_page(self, mock_st):
        """测试改进措施页面"""
        with patch("src.ui.streamlit_app.ChromaManager") as mock_chroma:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "embeddings": [[0.1] * 2048],
                "metadatas": [
                    {
                        "task_id": "TASK-001",
                        "root_cause": "需求遗漏",
                        "has_violation": False,
                    }
                ],
            }
            mock_chroma.return_value.get_or_create_collection.return_value = mock_collection

            ui = FaultAnalysisUI()
            ui._render_improvements()

            # 验证标题被设置
            mock_st.title.assert_called()


class TestSimilaritySearchPage:
    """相似故障查询页面测试"""

    @patch("src.ui.streamlit_app.st")
    def test_similarity_search_no_input(self, mock_st):
        """测试无输入时的相似查询页面"""
        with patch("src.ui.streamlit_app.ChromaManager"):
            mock_st.text_input.return_value = ""

            ui = FaultAnalysisUI()
            ui._render_similarity_search()

            # 应该显示提示信息
            mock_st.info.assert_called_once()


class TestVisualizationPage:
    """可视化页面测试"""

    @patch("src.ui.streamlit_app.st")
    def test_visualization_no_clustering(self, mock_st):
        """测试无聚类结果时的可视化页面"""
        with patch("src.ui.streamlit_app.ChromaManager"):
            mock_st.session_state = {}

            ui = FaultAnalysisUI()
            ui._render_visualization()

            # 应该显示警告
            mock_st.warning.assert_called_once()
