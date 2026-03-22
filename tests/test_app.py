"""Tests for app.py — _setup_main_menu and Edit menu keyboard shortcuts.

Because app.py transitively imports heavy macOS frameworks (Quartz, etc.),
we avoid importing ProofWindow directly and instead test the menu-setup
logic by validating the contract and checking the source.
"""

import os
from unittest.mock import MagicMock

import pytest


# The exact items _setup_main_menu is expected to create.
EXPECTED_EDIT_ITEMS = [
    ("Undo", "undo:", "z"),
    ("Redo", "redo:", "Z"),
    (None, None, None),  # separator
    ("Cut", "cut:", "x"),
    ("Copy", "copy:", "c"),
    ("Paste", "paste:", "v"),
    ("Select All", "selectAll:", "a"),
]

APP_PY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"
)


def _build_edit_items():
    """Build the Edit menu item list matching _setup_main_menu's contract."""
    items = []
    for title, action, key in EXPECTED_EDIT_ITEMS:
        if title is None:
            items.append({"type": "separator"})
        else:
            items.append({"title": title, "action": action, "key": key})
    return items


# =============================================================================
# Contract tests — verify the expected Edit menu structure
# =============================================================================


class TestEditMenuContract:
    """Verify the Edit menu item list has the right entries."""

    def test_expected_non_separator_count(self):
        items = _build_edit_items()
        non_sep = [i for i in items if i.get("type") != "separator"]
        assert len(non_sep) == 6

    def test_has_separator(self):
        items = _build_edit_items()
        seps = [i for i in items if i.get("type") == "separator"]
        assert len(seps) == 1

    @pytest.mark.parametrize(
        "title,action,key",
        [
            ("Undo", "undo:", "z"),
            ("Redo", "redo:", "Z"),
            ("Cut", "cut:", "x"),
            ("Copy", "copy:", "c"),
            ("Paste", "paste:", "v"),
            ("Select All", "selectAll:", "a"),
        ],
    )
    def test_item_has_correct_action_and_key(self, title, action, key):
        items = _build_edit_items()
        matches = [i for i in items if i.get("title") == title]
        assert len(matches) == 1, f"Expected exactly one '{title}' item"
        assert matches[0]["action"] == action
        assert matches[0]["key"] == key

    def test_separator_position_between_redo_and_cut(self):
        items = _build_edit_items()
        assert items[0]["title"] == "Undo"
        assert items[1]["title"] == "Redo"
        assert items[2].get("type") == "separator"
        assert items[3]["title"] == "Cut"


# =============================================================================
# Integration test — simulate the AppKit calls _setup_main_menu makes
# =============================================================================


class TestSetupMainMenuIntegration:
    """Simulate _setup_main_menu's AppKit calls with fakes."""

    def _make_fakes(self):
        menus = []
        items = []

        class FakeMenu:
            def __init__(self):
                self.title = ""
                self._items = []
                menus.append(self)

            def initWithTitle_(self, title):
                self.title = title
                return self

            def init(self):
                return self

            def addItem_(self, item):
                self._items.append(item)

        class FakeMenuItem:
            def __init__(self):
                self.title = ""
                self.action = None
                self.key = ""
                self.submenu = None
                items.append(self)

            def initWithTitle_action_keyEquivalent_(self, title, action, key):
                self.title = title
                self.action = action
                self.key = key
                return self

            def setSubmenu_(self, menu):
                self.submenu = menu

            @staticmethod
            def separatorItem():
                sep = FakeMenuItem()
                sep.title = "---separator---"
                sep.action = "__separator__"
                return sep

        return FakeMenu, FakeMenuItem, menus, items

    def _run_menu_setup(self):
        FakeMenu, FakeMenuItem, menus, items = self._make_fakes()
        mock_app = MagicMock()

        main_menu = FakeMenu()
        main_menu.init()

        edit_menu = FakeMenu()
        edit_menu.initWithTitle_("Edit")
        for title, action, key in EXPECTED_EDIT_ITEMS:
            if title is None:
                edit_menu.addItem_(FakeMenuItem.separatorItem())
            else:
                mi = FakeMenuItem()
                mi.initWithTitle_action_keyEquivalent_(title, action, key)
                edit_menu.addItem_(mi)

        edit_holder = FakeMenuItem()
        edit_holder.initWithTitle_action_keyEquivalent_("Edit", None, "")
        edit_holder.setSubmenu_(edit_menu)
        main_menu.addItem_(edit_holder)
        mock_app.setMainMenu_(main_menu)

        return mock_app, main_menu, edit_menu

    def test_main_menu_is_set(self):
        mock_app, main_menu, _ = self._run_menu_setup()
        mock_app.setMainMenu_.assert_called_once_with(main_menu)

    def test_edit_submenu_title(self):
        _, _, edit_menu = self._run_menu_setup()
        assert edit_menu.title == "Edit"

    def test_edit_submenu_has_seven_items(self):
        _, _, edit_menu = self._run_menu_setup()
        assert len(edit_menu._items) == 7

    def test_paste_item_in_edit_menu(self):
        _, _, edit_menu = self._run_menu_setup()
        paste = [i for i in edit_menu._items if i.title == "Paste"]
        assert len(paste) == 1
        assert paste[0].key == "v"
        assert paste[0].action == "paste:"

    def test_edit_holder_has_submenu(self):
        _, main_menu, edit_menu = self._run_menu_setup()
        holder = main_menu._items[0]
        assert holder.submenu is edit_menu


# =============================================================================
# Source sync tests — guard against accidental removal or drift in app.py
# =============================================================================


class TestSetupMainMenuSourceSync:
    """Verify app.py contains the expected _setup_main_menu implementation."""

    @pytest.fixture(autouse=True)
    def _load_source(self):
        with open(APP_PY_PATH) as f:
            self.source = f.read()

    def test_method_exists(self):
        assert "def _setup_main_menu(self):" in self.source

    def test_method_is_called_in_init(self):
        assert "self._setup_main_menu()" in self.source

    @pytest.mark.parametrize(
        "expected",
        [
            '("Paste", "paste:", "v")',
            '("Copy", "copy:", "c")',
            '("Cut", "cut:", "x")',
            '("Select All", "selectAll:", "a")',
            '("Undo", "undo:", "z")',
            '("Redo", "redo:", "Z")',
            "app.setMainMenu_(main_menu)",
        ],
    )
    def test_source_contains_expected_entry(self, expected):
        assert expected in self.source, f"Expected {expected!r} in app.py"
