from __future__ import annotations

from pathlib import Path

import pytest

from devflow.config import ReferenceConfig
from devflow.references.registry import ReferenceRegistry

REFERENCES_DIR = Path(__file__).resolve().parent.parent / "devflow" / "references"

EXPECTED_DOCUMENTS = {
    "adr-template": {"title": "架构决策记录模板", "applicable_stages": ["solution_design"], "priority": 9},
    "api-design": {"title": "REST API 设计指南", "applicable_stages": ["solution_design"], "priority": 5},
    "auth-flow": {"title": "认证授权流程模式", "applicable_stages": ["solution_design"], "priority": 3},
    "db-schema": {"title": "数据库 Schema 设计原则", "applicable_stages": ["solution_design"], "priority": 4},
    "ears-syntax": {"title": "EARS 需求语法模式", "applicable_stages": ["requirement_intake"], "priority": 10},
    "env-management": {"title": "环境与配置管理策略", "applicable_stages": ["code_generation"], "priority": 4},
    "git-conventions": {"title": "Git 分支与提交约定", "applicable_stages": ["code_generation"], "priority": 5},
    "karpathy-coding-guidelines": {"title": "Karpathy 编码行为指南", "applicable_stages": ["code_generation", "test_generation", "code_review"], "priority": 15},
    "layered-architecture": {"title": "分层架构模式", "applicable_stages": ["solution_design"], "priority": 6},
    "nfr-checklist": {"title": "非功能需求检查清单", "applicable_stages": ["requirement_intake", "code_review"], "priority": 8},
    "release-checklist": {"title": "发布就绪检查清单", "applicable_stages": ["code_review", "delivery"], "priority": 6},
    "tech-selection": {"title": "技术选型评估框架", "applicable_stages": ["solution_design"], "priority": 7},
    "testing-strategy": {"title": "测试策略与覆盖率目标", "applicable_stages": ["test_generation"], "priority": 10},
}


@pytest.fixture
def registry() -> ReferenceRegistry:
    return ReferenceRegistry(REFERENCES_DIR)


@pytest.fixture
def empty_registry() -> ReferenceRegistry:
    return ReferenceRegistry("/nonexistent/path/that/does/not/exist")


class TestIndexBuilding:
    def test_index_contains_all_documents(self, registry: ReferenceRegistry) -> None:
        assert len(registry._index) == 13
        assert set(registry._index.keys()) == set(EXPECTED_DOCUMENTS.keys())

    @pytest.mark.parametrize("name", list(EXPECTED_DOCUMENTS.keys()))
    def test_index_metadata(self, registry: ReferenceRegistry, name: str) -> None:
        meta = registry._index[name]
        expected = EXPECTED_DOCUMENTS[name]
        assert meta["name"] == name
        assert meta["title"] == expected["title"]
        assert meta["applicable_stages"] == expected["applicable_stages"]
        assert meta["priority"] == expected["priority"]


class TestLazyLoading:
    def test_cache_empty_after_init(self, registry: ReferenceRegistry) -> None:
        assert len(registry._cache) == 0

    def test_cache_populated_after_get_document(self, registry: ReferenceRegistry) -> None:
        registry.get_document("ears-syntax")
        assert "ears-syntax" in registry._cache
        assert len(registry._cache["ears-syntax"]) > 0


class TestGetDocument:
    def test_returns_dict_with_required_keys(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax")
        assert doc is not None
        assert "name" in doc
        assert "title" in doc
        assert "content" in doc

    def test_name_and_title_correct(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax")
        assert doc["name"] == "ears-syntax"
        assert doc["title"] == "EARS 需求语法模式"

    def test_content_non_empty(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax")
        assert len(doc["content"]) > 0


class TestSectionExtraction:
    def test_section_returned(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax", section="Agent 使用指引")
        assert doc is not None
        assert doc["content"].startswith("## Agent 使用指引")
        assert "## 概述" not in doc["content"]

    def test_nonexistent_section_returns_empty(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax", section="不存在的章节")
        assert doc is not None
        assert doc["content"] == ""


class TestCharacterTruncation:
    def test_content_truncated_with_notice(self, registry: ReferenceRegistry) -> None:
        doc = registry.get_document("ears-syntax", max_chars=100)
        assert doc is not None
        assert len(doc["content"]) > 100
        assert doc["content"].startswith(doc["content"][:100])
        assert "截断" in doc["content"]
        assert "section" in doc["content"]


class TestGetDocumentsForStage:
    def test_solution_design_returns_correct_docs(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("solution_design")
        names = [d["name"] for d in docs]
        for name in names:
            assert "solution_design" in EXPECTED_DOCUMENTS[name]["applicable_stages"]

    def test_solution_design_sorted_by_priority_desc(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("solution_design")
        priorities = [EXPECTED_DOCUMENTS[d["name"]]["priority"] for d in docs]
        assert priorities == sorted(priorities, reverse=True)

    def test_requirement_intake(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("requirement_intake")
        names = [d["name"] for d in docs]
        assert "ears-syntax" in names
        assert "nfr-checklist" in names

    def test_code_generation(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("code_generation")
        names = [d["name"] for d in docs]
        assert "git-conventions" in names
        assert "env-management" in names
        assert "karpathy-coding-guidelines" in names

    def test_test_generation(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("test_generation")
        names = [d["name"] for d in docs]
        assert "testing-strategy" in names
        assert "karpathy-coding-guidelines" in names

    def test_code_review(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("code_review")
        names = [d["name"] for d in docs]
        assert "nfr-checklist" in names
        assert "release-checklist" in names
        assert "karpathy-coding-guidelines" in names


class TestMaxTotalCharsBudget:
    def test_total_chars_within_budget(self, registry: ReferenceRegistry) -> None:
        docs = registry.get_documents_for_stage("solution_design", max_total_chars=500)
        total = sum(len(d["content"]) for d in docs)
        truncation_notice_len = len("\n\n... (截断，如需特定章节请指定 section 参数)")
        max_overhead = truncation_notice_len * len(docs)
        assert total <= 500 + max_overhead


class TestEmptyRegistry:
    def test_get_document_returns_none(self, empty_registry: ReferenceRegistry) -> None:
        assert empty_registry.get_document("anything") is None

    def test_get_documents_for_stage_returns_empty(self, empty_registry: ReferenceRegistry) -> None:
        assert empty_registry.get_documents_for_stage("solution_design") == []

    def test_index_is_empty(self, empty_registry: ReferenceRegistry) -> None:
        assert len(empty_registry._index) == 0


class TestNonExistentDocument:
    def test_returns_none(self, registry: ReferenceRegistry) -> None:
        assert registry.get_document("nonexistent") is None


class TestConfigIntegration:
    def test_default_values(self) -> None:
        config = ReferenceConfig()
        assert config.enabled is True
        assert config.max_chars_per_stage == 4000
        assert config.max_chars_per_document == 2000
