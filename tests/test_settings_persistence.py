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


# =============================================================================
# _persist_proof_settings (app.py contract)
# =============================================================================


class TestDebouncedSaveContract:
    """Verify the debounced save architecture in app.py source code.

    Callbacks should call _schedule_persist (debounced), not _persist_proof_settings
    (immediate). The immediate method is only used inside _schedule_persist's timer
    and _flush_pending_save.
    """

    @pytest.fixture(autouse=True)
    def _read_source(self):
        import os

        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"
        )
        with open(src_path, "r") as f:
            self.source = f.read()

    def _get_method_body(self, method_name):
        """Extract the full body of a class method."""
        idx = self.source.index(f"def {method_name}")
        rest = self.source[idx:]
        lines = rest.split("\n")
        method_lines = [lines[0]]
        for line in lines[1:]:
            if line.startswith("    def ") and not line.startswith("        "):
                break
            method_lines.append(line)
        return "\n".join(method_lines)

    # -- Debounce infrastructure --

    def test_schedule_persist_method_exists(self):
        assert "def _schedule_persist(self):" in self.source

    def test_schedule_persist_uses_threading_timer(self):
        body = self._get_method_body("_schedule_persist")
        assert "threading.Timer" in body

    def test_schedule_persist_delay_is_6_seconds(self):
        body = self._get_method_body("_schedule_persist")
        assert "6.0" in body

    def test_schedule_persist_cancels_previous_timer(self):
        body = self._get_method_body("_schedule_persist")
        assert ".cancel()" in body

    def test_schedule_persist_sets_daemon(self):
        body = self._get_method_body("_schedule_persist")
        assert ".daemon = True" in body

    def test_flush_pending_save_exists(self):
        assert "def _flush_pending_save(self):" in self.source

    def test_flush_pending_save_calls_persist_immediately(self):
        body = self._get_method_body("_flush_pending_save")
        assert "_persist_proof_settings()" in body

    def test_flush_pending_save_cancels_timer(self):
        body = self._get_method_body("_flush_pending_save")
        assert ".cancel()" in body

    def test_cleanup_calls_flush(self):
        body = self._get_method_body("_perform_cleanup_and_exit")
        assert "_flush_pending_save" in body

    def test_persist_method_still_exists(self):
        assert "def _persist_proof_settings(self):" in self.source

    def test_persist_calls_set_proof_settings(self):
        assert "self.settings.set_proof_settings(self.proof_settings)" in self.source

    # -- Callbacks use _schedule_persist (debounced) --

    def _assert_callback_uses_schedule(self, method_name):
        body = self._get_method_body(method_name)
        assert (
            "_schedule_persist" in body
        ), f"{method_name} does not call _schedule_persist"

    def test_character_category_callback_debounced(self):
        self._assert_callback_uses_schedule("characterCategoryCallback")

    def test_custom_text_callback_debounced(self):
        self._assert_callback_uses_schedule("customTextEditCallback")

    def test_markup_toggle_callback_debounced(self):
        self._assert_callback_uses_schedule("markupToggleCallback")

    def test_generate_once_callback_debounced(self):
        self._assert_callback_uses_schedule("generateOnceToggleCallback")

    def test_align_callback_debounced(self):
        self._assert_callback_uses_schedule("alignPopUpCallback")

    def test_stepper_change_callback_debounced(self):
        self._assert_callback_uses_schedule("stepperChangeCallback")

    def test_features_edit_callback_debounced(self):
        self._assert_callback_uses_schedule("featuresEditCallback")

    def test_styles_edit_callback_debounced(self):
        self._assert_callback_uses_schedule("stylesEditCallback")

    def test_default_font_popup_callback_debounced(self):
        self._assert_callback_uses_schedule("defaultFontPopupCallback")

    def test_validate_and_update_settings_debounced(self):
        self._assert_callback_uses_schedule("_validate_and_update_settings")


# =============================================================================
# Font order persistence in FilesTab (ui.py contract)
# =============================================================================


class TestFontOrderPersistenceContract:
    """Verify _update_backend_from_table calls settings.set_fonts."""

    @pytest.fixture(autouse=True)
    def _read_source(self):
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui.py"
        )
        with open(src_path, "r") as f:
            self.source = f.read()

    def test_update_backend_persists_font_order(self):
        idx = self.source.index("def _update_backend_from_table")
        snippet = self.source[idx : idx + 500]
        assert "settings.set_fonts" in snippet


# =============================================================================
# Loop order contract (app.py — proofs-first, fonts-second)
# =============================================================================


class TestProofLoopOrderContract:
    """Verify run_proof iterates proofs on the outside, fonts on the inside."""

    @pytest.fixture(autouse=True)
    def _read_source(self):
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"
        )
        with open(src_path, "r") as f:
            self.source = f.read()

    def test_proof_loop_before_font_loop(self):
        """The 'for item in proof_options_items' loop must appear before
        'for indFont in self.font_manager.fonts' inside run_proof."""
        idx_run_proof = self.source.index("def run_proof(")
        run_proof_body = self.source[idx_run_proof:]

        idx_proof_loop = run_proof_body.index("for item in proof_options_items:")
        idx_font_loop = run_proof_body.index("for indFont in self.font_manager.fonts:")

        assert (
            idx_proof_loop < idx_font_loop
        ), "Proof loop should be the outer loop (proofs-first, fonts-second)"
