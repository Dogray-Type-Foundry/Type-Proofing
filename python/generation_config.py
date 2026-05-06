"""Typed generation configuration parsed from the Swift bridge dictionary."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from config import PROOF_REGISTRY


@dataclass(frozen=True)
class ProofOptionConfig:
    name: str
    enabled: bool
    base_type: str

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProofOptionConfig":
        name = str(raw.get("Option", ""))
        return cls(
            name=name,
            enabled=bool(raw.get("Enabled", False)),
            base_type=str(raw.get("_original_option", name)),
        )


@dataclass(frozen=True)
class ProofSettingsConfig:
    """Wrapper around the current flat settings dict.

    This is the migration layer: call sites can move to typed accessors without
    breaking existing handlers that still consume the flat dictionary.
    """

    flat: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.flat.get(key, default)

    def enabled_features_for(self, settings_key: str) -> dict[str, bool]:
        prefix = f"otf_{settings_key}_"
        return {
            key[len(prefix) :]: bool(value)
            for key, value in self.flat.items()
            if key.startswith(prefix)
        }

    def enabled_substitution_features_for(self, settings_key: str) -> dict[str, bool]:
        prefix = f"{settings_key}_sub_"
        return {
            key[len(prefix) :]: bool(value)
            for key, value in self.flat.items()
            if key.startswith(prefix)
        }


@dataclass(frozen=True)
class GenerationConfig:
    font_paths: list[str]
    axis_values_by_font: dict[str, dict[str, list[float]]]
    proof_options: list[ProofOptionConfig]
    proof_settings: ProofSettingsConfig
    page_format: str = "A4Landscape"
    output_dir: str = ""
    show_baselines: bool = False
    debug_mode: bool = False
    preview_mode: bool = False
    target_proof_name: str = ""
    target_proof_base_type: str = ""
    fragment_output_dir: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "GenerationConfig":
        return cls(
            font_paths=[str(path) for path in raw.get("font_paths", [])],
            axis_values_by_font=_coerce_axes(raw.get("axis_values_by_font", {})),
            proof_options=[
                ProofOptionConfig.from_dict(item)
                for item in raw.get("proof_options", [])
                if isinstance(item, dict)
            ],
            proof_settings=ProofSettingsConfig(dict(raw.get("proof_settings", {}))),
            page_format=str(raw.get("page_format", "A4Landscape")),
            output_dir=str(raw.get("output_dir", "")),
            show_baselines=bool(raw.get("show_baselines", False)),
            debug_mode=bool(raw.get("debug_mode", False)),
            preview_mode=bool(raw.get("preview_mode", False)),
            target_proof_name=str(raw.get("target_proof_name", "")),
            target_proof_base_type=str(raw.get("target_proof_base_type", "")),
            fragment_output_dir=str(raw.get("fragment_output_dir", "")),
        )

    @property
    def enabled_proofs(self) -> list[ProofOptionConfig]:
        return [option for option in self.proof_options if option.enabled]

    @property
    def resolved_output_dir(self) -> str:
        if self.preview_mode and self.fragment_output_dir:
            return self.fragment_output_dir
        if self.output_dir:
            return self.output_dir
        if self.font_paths:
            return os.path.dirname(os.path.abspath(self.font_paths[0]))
        return ""

    def estimate_axis_instance_count_for_font(self, font_path: str) -> int:
        axes = self.axis_values_by_font.get(font_path, {})
        if not axes:
            return 1
        count = 1
        for values in axes.values():
            count *= max(1, len(values))
        return count

    def build_summary(self) -> dict[str, Any]:
        enabled_proofs = self.enabled_proofs
        axis_counts = {
            path: self.estimate_axis_instance_count_for_font(path)
            for path in self.font_paths
        }
        total_axis_instances = sum(axis_counts.values())
        work_items = len(enabled_proofs) * max(1, total_axis_instances)
        warnings = []
        if total_axis_instances >= 40:
            warnings.append(
                f"Variable font settings will generate {total_axis_instances} font instances."
            )
        if len(enabled_proofs) >= 12:
            warnings.append(f"{len(enabled_proofs)} proof sections are enabled.")
        if not self.resolved_output_dir:
            warnings.append("No output directory is available.")

        return {
            "font_count": len(self.font_paths),
            "enabled_proof_count": len(enabled_proofs),
            "enabled_proofs": [option.name for option in enabled_proofs],
            "axis_instance_counts": axis_counts,
            "total_axis_instances": total_axis_instances,
            "estimated_work_items": work_items,
            "page_format": self.page_format,
            "output_dir": self.resolved_output_dir,
            "show_baselines": self.show_baselines,
            "warnings": warnings,
        }


def _coerce_axes(raw: Any) -> dict[str, dict[str, list[float]]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, list[float]]] = {}
    for font_path, axes in raw.items():
        if not isinstance(axes, dict):
            continue
        result[str(font_path)] = {}
        for tag, values in axes.items():
            if isinstance(values, (list, tuple)):
                result[str(font_path)][str(tag)] = [float(value) for value in values]
    return result


def validate_generation_config(config: GenerationConfig) -> list[str]:
    """Return non-fatal validation warnings."""
    warnings: list[str] = []
    if not config.font_paths:
        warnings.append("No fonts are enabled.")
    if not config.enabled_proofs:
        warnings.append("No proofs are enabled.")
    for option in config.enabled_proofs:
        if option.base_type not in PROOF_REGISTRY:
            warnings.append(f"Unknown proof type: {option.base_type}")
    return warnings
