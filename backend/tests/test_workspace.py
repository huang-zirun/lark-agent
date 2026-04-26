import os
import tempfile

import pytest

from app.core.workspace.workspace_manager import (
    get_directory_tree,
    read_file_content,
    get_code_context,
    EXCLUDED_DIRS,
)


class TestGetDirectoryTree:
    def test_nonexistent_path(self):
        result = get_directory_tree("/nonexistent/path")
        assert "error" in result

    def test_basic_tree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (open(os.path.join(tmpdir, "main.py"), "w")).close()
            (open(os.path.join(tmpdir, "test.py"), "w")).close()

            result = get_directory_tree(tmpdir, max_depth=2)
            assert "tree" in result
            assert "main.py" in str(result["tree"])

    def test_excludes_git_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, ".git"))
            os.makedirs(os.path.join(tmpdir, "src"))
            (open(os.path.join(tmpdir, "src", "app.py"), "w")).close()

            result = get_directory_tree(tmpdir, max_depth=2)
            tree_str = str(result["tree"])
            assert ".git" not in tree_str
            assert "src" in tree_str

    def test_max_depth(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, "a", "b", "c", "d"))

            result = get_directory_tree(tmpdir, max_depth=2)
            tree_str = str(result["tree"])
            assert "..." in tree_str


class TestReadFileContent:
    def test_read_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.py")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("print('hello')")

            content = read_file_content(tmpdir, "test.py")
            assert content == "print('hello')"

    def test_read_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content = read_file_content(tmpdir, "nonexistent.py")
            assert content is None

    def test_max_lines_truncation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "long.py")
            with open(filepath, "w", encoding="utf-8") as f:
                for i in range(300):
                    f.write(f"line {i}\n")

            content = read_file_content(tmpdir, "long.py", max_lines=10)
            assert "more lines truncated" in content


class TestGetCodeContext:
    def test_nonexistent_workspace(self):
        result = get_code_context("/nonexistent/path")
        assert result["directory_tree"] is None
        assert result["file_contents"] is None

    def test_with_affected_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "app.py")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# app code")

            result = get_code_context(tmpdir, affected_files=["app.py"])
            assert result["directory_tree"] is not None
            assert result["file_contents"] is not None
            assert "app.py" in result["file_contents"]

    def test_without_affected_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_code_context(tmpdir)
            assert result["directory_tree"] is not None
            assert result["file_contents"] is None
