use read_fonts::TableProvider;
use skrifa::raw::tables::os2::SelectionFlags;
use skrifa::{FontRef, MetadataProvider};
use skrifa::string::StringId;

#[derive(Debug, Clone)]
pub struct AxisInfo {
    pub tag: [u8; 4],
    pub min: f64,
    pub default: f64,
    pub max: f64,
}

#[derive(Debug, Clone)]
pub struct NamedInstanceRecord {
    pub name: String,
    pub coordinates: Vec<([u8; 4], f64)>,
}

#[derive(Debug, Clone)]
pub struct FontInfo {
    pub family_name: String,
    pub subfamily_name: String,
    pub weight: u16,
    pub width: u16,
    pub fs_selection: u16,
    pub is_variable: bool,
    pub slant: f64,
    pub optical_size: f64,
    pub axes: Vec<AxisInfo>,
    pub features: Vec<String>,
}

pub fn load_font_info(data: &[u8]) -> Option<FontInfo> {
    let font = FontRef::new(data).ok()?;

    let family_name = font
        .localized_strings(StringId::FAMILY_NAME)
        .english_or_first()
        .map(|s| s.chars().collect::<String>())
        .unwrap_or_default();

    let subfamily_name = font
        .localized_strings(StringId::SUBFAMILY_NAME)
        .english_or_first()
        .map(|s| s.chars().collect::<String>())
        .unwrap_or_default();

    let (weight, width, fs_selection) = font
        .os2()
        .ok()
        .map(|os2| (os2.us_weight_class(), os2.us_width_class(), os2.fs_selection().bits()))
        .unwrap_or((400, 5, 0));

    let is_italic = (fs_selection & SelectionFlags::ITALIC.bits()) != 0;
    let slant = if is_italic { -12.0 } else { 0.0 };

    let (is_variable, axes, optical_size, slant) = match font.fvar() {
        Ok(fvar) => {
            let axis_records = fvar.axes().unwrap_or_default();
            let fvar_axes: Vec<AxisInfo> = axis_records
                .iter()
                .map(|a| AxisInfo {
                    tag: a.axis_tag().to_be_bytes(),
                    min: a.min_value().to_f64(),
                    default: a.default_value().to_f64(),
                    max: a.max_value().to_f64(),
                })
                .collect();

            let opsz = fvar_axes
                .iter()
                .find(|a| &a.tag == b"opsz")
                .map(|a| a.default)
                .unwrap_or(0.0);

            let slant_from_axis = fvar_axes
                .iter()
                .find(|a| &a.tag == b"slnt")
                .map(|a| a.default);
            let final_slant = slant_from_axis.unwrap_or(slant);

            (true, fvar_axes, opsz, final_slant)
        }
        Err(_) => (false, Vec::new(), 0.0, slant),
    };

    let features = extract_features(&font);

    Some(FontInfo {
        family_name,
        subfamily_name,
        weight,
        width,
        fs_selection,
        is_variable,
        slant,
        optical_size,
        axes,
        features,
    })
}

pub fn get_named_instances(data: &[u8]) -> Vec<NamedInstanceRecord> {
    let font = match FontRef::new(data) {
        Ok(f) => f,
        Err(_) => return vec![],
    };

    let axis_tags: Vec<[u8; 4]> = font
        .axes()
        .iter()
        .map(|a| a.tag().to_be_bytes())
        .collect();

    if axis_tags.is_empty() {
        return vec![];
    }

    font.named_instances()
        .iter()
        .map(|instance| {
            let name = font
                .localized_strings(instance.subfamily_name_id())
                .english_or_first()
                .map(|s| s.chars().collect::<String>())
                .unwrap_or_default();

            let coordinates: Vec<([u8; 4], f64)> = axis_tags
                .iter()
                .zip(instance.user_coords())
                .map(|(tag, val)| (*tag, val as f64))
                .collect();

            NamedInstanceRecord { name, coordinates }
        })
        .collect()
}

/// Human-readable UI names for stylistic sets (ss01–ss20), read from each
/// feature's FeatureParams uiNameId via the name table. Returns (tag, name)
/// pairs for features that carry a resolvable name; features without
/// FeatureParams are simply absent.
pub fn get_feature_ui_names(data: &[u8]) -> Vec<(String, String)> {
    use read_fonts::tables::layout::FeatureParams;

    let font = match FontRef::new(data) {
        Ok(f) => f,
        Err(_) => return vec![],
    };
    let gsub = match font.gsub() {
        Ok(g) => g,
        Err(_) => return vec![],
    };
    let feature_list = match gsub.feature_list() {
        Ok(l) => l,
        Err(_) => return vec![],
    };

    let mut seen = std::collections::BTreeSet::new();
    let mut out = Vec::new();
    for record in feature_list.feature_records() {
        let tag = record.feature_tag().to_string();
        let is_stylistic_set = tag.starts_with("ss")
            && matches!(tag[2..].parse::<u8>(), Ok(1..=20));
        if !is_stylistic_set || !seen.insert(tag.clone()) {
            continue;
        }
        let Ok(feature) = record.feature(feature_list.offset_data()) else { continue };
        let Some(Ok(FeatureParams::StylisticSet(params))) = feature.feature_params() else { continue };
        let name = font
            .localized_strings(params.ui_name_id())
            .english_or_first()
            .map(|s| s.chars().collect::<String>())
            .unwrap_or_default();
        if !name.is_empty() {
            out.push((tag, name));
        }
    }
    out
}

fn extract_features(font: &FontRef) -> Vec<String> {
    let mut tags = std::collections::BTreeSet::new();
    if let Ok(gsub) = font.gsub() {
        if let Ok(feature_list) = gsub.feature_list() {
            for record in feature_list.feature_records() {
                tags.insert(record.feature_tag().to_string());
            }
        }
    }
    if let Ok(gpos) = font.gpos() {
        if let Ok(feature_list) = gpos.feature_list() {
            for record in feature_list.feature_records() {
                tags.insert(record.feature_tag().to_string());
            }
        }
    }
    tags.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_static_font() {
        let data = std::fs::read("../../SetsGroteskXS-Regular.ttf").expect("font file");
        let info = load_font_info(&data).expect("parse font");

        assert_eq!(info.family_name, "Sets Grotesk XS");
        assert_eq!(info.subfamily_name, "Regular");
        assert_eq!(info.weight, 400);
        assert!(!info.is_variable);
        assert!(info.axes.is_empty());
        assert!(info.features.contains(&"kern".to_string()));
    }

    #[test]
    fn test_load_sets_grotesk_vf() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        let info = load_font_info(&data).expect("parse font");

        assert_eq!(info.family_name, "Sets Grotesk VF");
        assert_eq!(info.subfamily_name, "Regular");
        assert_eq!(info.weight, 400);
        assert_eq!(info.width, 5);
        assert_eq!(info.fs_selection, 64);
        assert!(info.is_variable);
        assert_eq!(info.slant, 0.0);

        assert_eq!(info.axes.len(), 2);
        let wght = info.axes.iter().find(|a| &a.tag == b"wght").unwrap();
        assert_eq!(wght.min, 100.0);
        assert_eq!(wght.default, 400.0);
        assert_eq!(wght.max, 900.0);

        let opsz = info.axes.iter().find(|a| &a.tag == b"opsz").unwrap();
        assert_eq!(opsz.min, 8.0);
        assert_eq!(opsz.max, 32.0);

        assert_eq!(info.optical_size, opsz.default);

        assert!(info.features.contains(&"kern".to_string()));
        assert!(info.features.contains(&"calt".to_string()));
        assert!(info.features.contains(&"ss01".to_string()));
    }

    #[test]
    fn test_named_instances_vf() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        let instances = get_named_instances(&data);
        assert!(!instances.is_empty(), "should have named instances");
        for inst in &instances {
            assert!(!inst.name.is_empty(), "instance should have a name");
            assert!(!inst.coordinates.is_empty(), "instance should have coordinates");
        }
    }

    #[test]
    fn test_named_instances_static() {
        let data = std::fs::read("../../SetsGroteskXS-Regular.ttf").expect("font file");
        let instances = get_named_instances(&data);
        assert!(instances.is_empty(), "static font should have no named instances");
    }
}
