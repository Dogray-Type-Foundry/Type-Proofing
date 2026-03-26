"""Tests for settings persistence robustness.

Covers:
- Atomic JSON save (temp file + fsync + rename)
- Proof settings auto-persistence from callbacks
- Font order persistence after reordering
"""

import json
import os
import tempfile

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from settings import (
    Settings,
    safe_json_save,
    safe_json_load,
    ProofSettingsManager,
    make_settings_key,
    validate_setting_value,
)


# =============================================================================
# Atomic save (safe_json_save)
# =============================================================================


class TestAtomicSave:
    """safe_json_save should write atomically via temp+fsync+rename."""

    def test_basic_save_creates_file(self, tmp_path):
        path = str(tmp_path / "test.json")
        result = safe_json_save({"key": "value"}, path)
        assert result is True
        assert os.path.exists(path)

    def test_saved_content_is_valid_json(self, tmp_path):
        path = str(tmp_path / "test.json")
        data = {"hello": "world", "number": 42}
        safe_json_save(data, path)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_overwrites_existing_file(self, tmp_path):
        path = str(tmp_path / "test.json")
        safe_json_save({"v": 1}, path)
        safe_json_save({"v": 2}, path)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == {"v": 2}

    def test_no_temp_files_left_on_success(self, tmp_path):
        path = str(tmp_path / "test.json")
        safe_json_save({"key": "value"}, path)
        files = os.listdir(tmp_path)
        assert files == ["test.json"]

    def test_no_temp_files_left_on_failure(self, tmp_path):
        path = str(tmp_path / "test.json")
        # Write initial valid data
        safe_json_save({"ok": True}, path)

        # Force a failure during json.dump by passing unserializable data
        result = safe_json_save({"bad": object()}, path)
        assert result is False

        # Original file should still be intact
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == {"ok": True}

        # No stale temp files
        files = os.listdir(tmp_path)
        assert files == ["test.json"]

    def test_creates_parent_directory(self, tmp_path):
        path = str(tmp_path / "subdir" / "deep" / "test.json")
        result = safe_json_save({"nested": True}, path)
        assert result is True
        assert os.path.exists(path)

    def test_unicode_content(self, tmp_path):
        path = str(tmp_path / "test.json")
        data = {"text": "Héllo wörld — ñ"}
        safe_json_save(data, path)
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_preserves_original_on_serialization_error(self, tmp_path):
        """If the new data can't be serialized, the old file is untouched."""
        path = str(tmp_path / "test.json")
        safe_json_save({"version": 1}, path)

        # Try to save unserializable data
        result = safe_json_save({"func": lambda: None}, path)
        assert result is False

        # Original still valid
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == {"version": 1}


# =============================================================================
# safe_json_load
# =============================================================================


class TestSafeJsonLoad:
    def test_load_valid_file(self, tmp_path):
        path = str(tmp_path / "test.json")
        with open(path, "w") as f:
            json.dump({"key": "value"}, f)
        result = safe_json_load(path)
        assert result == {"key": "value"}

    def test_load_missing_file_returns_default(self, tmp_path):
        path = str(tmp_path / "missing.json")
        result = safe_json_load(path, default={"fallback": True})
        assert result == {"fallback": True}

    def test_load_corrupted_file_returns_default(self, tmp_path):
        path = str(tmp_path / "bad.json")
        with open(path, "w") as f:
            f.write("{not valid json!!!")
        result = safe_json_load(path, default={"fallback": True})
        assert result == {"fallback": True}

    def test_load_missing_no_default_returns_empty_dict(self, tmp_path):
        path = str(tmp_path / "missing.json")
        result = safe_json_load(path)
        assert result == {}


# =============================================================================
# Settings round-trip with atomic save
# =============================================================================


class TestSettingsAtomicRoundTrip:
    def test_set_proof_settings_persists(self, tmp_settings_path):
        """set_proof_settings should auto-save (via _set_nested_value)."""
        s = Settings(settings_path=tmp_settings_path)
        s.set_proof_settings({"custom_key": 42})

        # Reload from disk
        s2 = Settings(settings_path=tmp_settings_path)
        assert s2.get_proof_settings() == {"custom_key": 42}

    def test_set_fonts_persists(self, tmp_settings_path, tmp_path):
        # Create real font files so Settings doesn't strip them on reload
        font_a = str(tmp_path / "a.otf")
        font_b = str(tmp_path / "b.otf")
        for p in (font_a, font_b):
            with open(p, "w") as f:
                f.write("fake")

        s = Settings(settings_path=tmp_settings_path)
        s.set_fonts([font_a, font_b])

        s2 = Settings(settings_path=tmp_settings_path)
        assert s2.get_fonts() == [font_a, font_b]

    def test_font_order_preserved(self, tmp_settings_path, tmp_path):
        """Font order should survive a save/load cycle."""
        fonts = []
        for name in ("z.otf", "a.otf", "m.otf"):
            p = str(tmp_path / name)
            with open(p, "w") as f:
                f.write("fake")
            fonts.append(p)

        s = Settings(settings_path=tmp_settings_path)
        s.set_fonts(fonts)

        s2 = Settings(settings_path=tmp_settings_path)
        assert s2.get_fonts() == fonts

    def test_proof_settings_merge_on_reload(self, tmp_settings_path):
        """Proof settings saved to disk should survive re-initialization."""
        s = Settings(settings_path=tmp_settings_path)
        s.set_proof_settings({"my_key": "my_value"})

        s2 = Settings(settings_path=tmp_settings_path)
        ps = s2.get_proof_settings()
        assert ps["my_key"] == "my_value"


# =============================================================================
# ProofSettingsManager persistence
# =============================================================================


class TestProofSettingsManagerPersistence:
    def test_initialize_preserves_existing_settings(self, tmp_settings_path):
        """initialize_proof_settings must not overwrite user-customized values."""
        s = Settings(settings_path=tmp_settings_path)
        # Pre-seed a custom font size setting
        custom_key = make_settings_key("filtered_character_set", "fontSize")
        s.set_proof_settings({custom_key: 999})

        fm = MagicMock()
        fm.fonts = tuple()
        psm = ProofSettingsManager(s, fm)
        psm.initialize_proof_settings()

        assert psm.proof_settings[custom_key] == 999

    def test_save_all_settings_writes_to_disk(self, tmp_settings_path):
        s = Settings(settings_path=tmp_settings_path)
        fm = MagicMock()
        fm.fonts = tuple()
        psm = ProofSettingsManager(s, fm)
        psm.initialize_proof_settings()

        # Modify a setting in memory
        key = make_settings_key("filtered_character_set", "fontSize")
        psm.proof_settings[key] = 777

        # Simulate proof options items for save_all_settings
        proof_options_items = [
            {"Option": "Filtered Character Set", "Enabled": True},
        ]
        psm.save_all_settings(proof_options_items)

        # Reload and verify
        s2 = Settings(settings_path=tmp_settings_path)
        ps = s2.get_proof_settings()
        assert ps[key] == 777
