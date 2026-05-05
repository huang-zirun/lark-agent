from __future__ import annotations

import unittest

from devflow.pipeline_config import PipelineConfigError, resolve_pipeline_config


class PipelineConfigTests(unittest.TestCase):
    def test_default_template_contains_built_in_order_and_dependencies(self) -> None:
        config = resolve_pipeline_config(None)

        self.assertEqual(config["template"], "default")
        self.assertEqual(
            [stage["name"] for stage in config["stages"]],
            [
                "requirement_intake",
                "solution_design",
                "code_generation",
                "test_generation",
                "code_review",
                "delivery",
            ],
        )
        self.assertEqual(config["stages"][0]["dependencies"], [])
        self.assertEqual(config["stages"][1]["dependencies"], ["requirement_intake"])
        self.assertEqual(config["stages"][5]["agent"], "delivery")

    def test_inline_stage_names_become_validated_linear_template(self) -> None:
        config = resolve_pipeline_config(["requirement_intake", "solution_design", "delivery"])

        self.assertEqual(config["template"], "inline")
        self.assertEqual([stage["name"] for stage in config["stages"]], ["requirement_intake", "solution_design", "delivery"])
        self.assertEqual(config["stages"][2]["dependencies"], ["solution_design"])

    def test_inline_stage_objects_can_define_dependencies_and_agent_binding(self) -> None:
        config = resolve_pipeline_config(
            [
                {"name": "requirement_intake", "agent": "requirement_intake", "dependencies": []},
                {"name": "delivery", "agent": "delivery", "dependencies": ["requirement_intake"]},
            ]
        )

        self.assertEqual(config["stages"][1]["name"], "delivery")
        self.assertEqual(config["stages"][1]["dependencies"], ["requirement_intake"])

    def test_rejects_unknown_stage_name(self) -> None:
        with self.assertRaises(PipelineConfigError) as raised:
            resolve_pipeline_config(["requirement_intake", "magic_stage"])

        self.assertIn("不支持的流水线阶段", str(raised.exception))

    def test_rejects_missing_dependency(self) -> None:
        with self.assertRaises(PipelineConfigError) as raised:
            resolve_pipeline_config(
                [
                    {"name": "requirement_intake", "dependencies": []},
                    {"name": "delivery", "dependencies": ["code_review"]},
                ]
            )

        self.assertIn("依赖的阶段不存在", str(raised.exception))

    def test_rejects_cycle(self) -> None:
        with self.assertRaises(PipelineConfigError) as raised:
            resolve_pipeline_config(
                [
                    {"name": "requirement_intake", "dependencies": ["delivery"]},
                    {"name": "delivery", "dependencies": ["requirement_intake"]},
                ]
            )

        self.assertIn("存在循环依赖", str(raised.exception))

