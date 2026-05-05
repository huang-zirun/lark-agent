from __future__ import annotations

import unittest
from pathlib import Path


class TextEncodingTests(unittest.TestCase):
    def test_user_facing_docs_and_fixtures_do_not_contain_mojibake(self) -> None:
        paths = [
            Path("README.md"),
            Path("devflow/intake/analyzer.py"),
            Path("devflow/intake/prompt.py"),
            Path("tests/test_requirement_intake.py"),
            Path("tests/test_llm.py"),
        ]
        mojibake_markers = ["鐩", "鑳", "闇", "楠", "锛", "銆", "€"]

        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in mojibake_markers:
                self.assertNotIn(marker, text, f"{path} contains mojibake marker {marker!r}")


if __name__ == "__main__":
    unittest.main()
