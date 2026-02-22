"""Unit tests for telos_agent.mcp.gemini.multimodal — file walking, hashing, skip-dir filtering."""

from __future__ import annotations

from telos_agent.mcp.gemini import settings
from telos_agent.mcp.gemini.multimodal import _walk_multimodal_paths, multimodal_hash


class TestWalkMultimodalPaths:
    def test_finds_images(self, tmp_path):
        (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8")
        (tmp_path / "diagram.png").write_bytes(b"\x89PNG")
        settings.set_base_dir(tmp_path)
        paths = list(_walk_multimodal_paths())
        names = {p.name for p in paths}
        assert "photo.jpg" in names
        assert "diagram.png" in names

    def test_finds_pdfs(self, tmp_path):
        (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4")
        settings.set_base_dir(tmp_path)
        paths = list(_walk_multimodal_paths())
        assert any(p.name == "doc.pdf" for p in paths)

    def test_skips_text_files(self, tmp_path):
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "main.py").write_text("print(1)")
        settings.set_base_dir(tmp_path)
        paths = list(_walk_multimodal_paths())
        names = {p.name for p in paths}
        assert "readme.md" not in names
        assert "main.py" not in names

    def test_skips_skip_dirs(self, tmp_path):
        d = tmp_path / "node_modules"
        d.mkdir()
        (d / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "ok.jpg").write_bytes(b"\xff\xd8")
        settings.set_base_dir(tmp_path)
        paths = list(_walk_multimodal_paths())
        names = {p.name for p in paths}
        assert "ok.jpg" in names
        assert "image.png" not in names

    def test_recurses_subdirs(self, tmp_path):
        sub = tmp_path / "assets" / "images"
        sub.mkdir(parents=True)
        (sub / "logo.png").write_bytes(b"\x89PNG")
        settings.set_base_dir(tmp_path)
        paths = list(_walk_multimodal_paths())
        assert any(p.name == "logo.png" for p in paths)

    def test_empty_dir(self, tmp_path):
        settings.set_base_dir(tmp_path)
        assert list(_walk_multimodal_paths()) == []


class TestMultimodalHash:
    def test_hash_is_hex(self, tmp_path):
        (tmp_path / "img.jpg").write_bytes(b"\xff\xd8")
        settings.set_base_dir(tmp_path)
        h = multimodal_hash()
        assert isinstance(h, str)
        assert len(h) == 32
        int(h, 16)  # should not raise

    def test_hash_changes_on_new_file(self, tmp_path):
        (tmp_path / "img.jpg").write_bytes(b"\xff\xd8")
        settings.set_base_dir(tmp_path)
        h1 = multimodal_hash()

        (tmp_path / "img2.png").write_bytes(b"\x89PNG")
        h2 = multimodal_hash()
        assert h1 != h2

    def test_hash_stable(self, tmp_path):
        (tmp_path / "img.jpg").write_bytes(b"\xff\xd8")
        settings.set_base_dir(tmp_path)
        assert multimodal_hash() == multimodal_hash()

    def test_hash_empty_dir(self, tmp_path):
        settings.set_base_dir(tmp_path)
        h = multimodal_hash()
        assert isinstance(h, str)
        assert len(h) == 32
