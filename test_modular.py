#!/usr/bin/env python3
"""
Test script to verify the modular structure works correctly.
This script tests imports and basic functionality without running the GUI.
"""


def test_imports():
    """Test that all modules import correctly."""
    print("Testing imports...")

    try:
        import config

        print("✓ config.py imports successfully")

        import font_analysis

        print("✓ font_analysis.py imports successfully")

        import proof_generation

        print("✓ proof_generation.py imports successfully")

        import ui_interface

        print("✓ ui_interface.py imports successfully")

        print("\nAll modules imported successfully!")
        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_basic_functionality():
    """Test basic functionality of key components."""
    print("\nTesting basic functionality...")

    try:
        # Test config
        from config import Settings, DEFAULT_ON_FEATURES

        settings = Settings()
        print(f"✓ Settings class works (default features: {len(DEFAULT_ON_FEATURES)})")

        # Test font analysis
        from font_analysis import FontManager, categorize

        font_manager = FontManager()
        print("✓ FontManager class instantiated")

        # Test categorization with sample text
        test_charset = "ABCabc123!@#"
        cat_result = categorize(test_charset)
        print(f"✓ Character categorization works (found {len(cat_result)} categories)")

        print("\nBasic functionality tests passed!")
        return True

    except Exception as e:
        print(f"✗ Functionality error: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("MODULAR STRUCTURE TEST")
    print("=" * 50)

    import_success = test_imports()
    func_success = test_basic_functionality()

    print("\n" + "=" * 50)
    if import_success and func_success:
        print("✓ ALL TESTS PASSED - Modular structure is working correctly!")
    else:
        print("✗ SOME TESTS FAILED - Please check the issues above")
    print("=" * 50)
