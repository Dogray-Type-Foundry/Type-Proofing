"""Tests for typed generation configuration parsing and summaries."""

from generation_config import GenerationConfig, validate_generation_config


def test_generation_config_parses_current_bridge_shape():
    raw = {
        "font_paths": ["/tmp/Font-Regular.otf"],
        "axis_values_by_font": {
            "/tmp/Font-Regular.otf": {
                "wght": [100, 400, 900],
                "wdth": [75, 100],
            }
        },
        "proof_options": [
            {
                "Option": "Character Overview",
                "Enabled": True,
                "_original_option": "filtered_character_set",
            },
            {
                "Option": "Spacing Test",
                "Enabled": False,
                "_original_option": "spacing_proof",
            },
        ],
        "proof_settings": {
            "filtered_character_set_fontSize": 72,
            "otf_filtered_character_set_kern": True,
        },
        "page_format": "A4Landscape",
        "output_dir": "/tmp",
        "show_baselines": True,
        "debug_mode": True,
        "preview_mode": True,
        "target_proof_name": "Character Overview",
        "target_proof_base_type": "filtered_character_set",
        "fragment_output_dir": "/tmp/fragments",
    }

    config = GenerationConfig.from_dict(raw)

    assert config.font_paths == ["/tmp/Font-Regular.otf"]
    assert len(config.enabled_proofs) == 1
    assert config.enabled_proofs[0].base_type == "filtered_character_set"
    assert config.estimate_axis_instance_count_for_font("/tmp/Font-Regular.otf") == 6
    assert config.proof_settings.get("filtered_character_set_fontSize") == 72
    assert config.proof_settings.enabled_features_for("filtered_character_set") == {
        "kern": True
    }
    assert config.debug_mode is True
    assert config.preview_mode is True
    assert config.target_proof_name == "Character Overview"
    assert config.target_proof_base_type == "filtered_character_set"
    assert config.resolved_output_dir == "/tmp/fragments"


def test_generation_summary_flags_large_variable_runs():
    raw = {
        "font_paths": ["/tmp/FontVF.otf"],
        "axis_values_by_font": {
            "/tmp/FontVF.otf": {
                "wght": list(range(10)),
                "wdth": list(range(5)),
            }
        },
        "proof_options": [
            {
                "Option": "Character Overview",
                "Enabled": True,
                "_original_option": "filtered_character_set",
            }
        ],
        "proof_settings": {},
    }

    summary = GenerationConfig.from_dict(raw).build_summary()

    assert summary["font_count"] == 1
    assert summary["enabled_proof_count"] == 1
    assert summary["total_axis_instances"] == 50
    assert summary["estimated_work_items"] == 50
    assert summary["warnings"]


def test_generation_config_validation_warns_on_empty_run():
    config = GenerationConfig.from_dict({"font_paths": [], "proof_options": []})

    assert "No fonts are enabled." in validate_generation_config(config)
    assert "No proofs are enabled." in validate_generation_config(config)
