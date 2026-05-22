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
pub struct AxisInstances {
    pub tag: [u8; 4],
    pub values: Vec<f64>,
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
    pub axis_instances: Vec<AxisInstances>,
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

    let (is_variable, axes, axis_instances, optical_size, slant) = match font.fvar() {
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

            let mut instances_map: std::collections::BTreeMap<[u8; 4], std::collections::BTreeSet<OrderedF64>> =
                std::collections::BTreeMap::new();

            for axis in &fvar_axes {
                instances_map.entry(axis.tag).or_default();
            }

            if let Ok(named_instances) = fvar.instances() {
                let axis_tags: Vec<[u8; 4]> = fvar_axes.iter().map(|a| a.tag).collect();
                for i in 0..named_instances.len() {
                    if let Ok(instance) = named_instances.get(i) {
                        let coords = instance.coordinates;
                        for (j, coord) in coords.iter().enumerate() {
                            if let Some(tag) = axis_tags.get(j) {
                                let val: read_fonts::types::Fixed = coord.get();
                                instances_map
                                    .entry(*tag)
                                    .or_default()
                                    .insert(OrderedF64(val.to_f64()));
                            }
                        }
                    }
                }
            }

            let axis_instances: Vec<AxisInstances> = instances_map
                .into_iter()
                .filter(|(_, vals)| !vals.is_empty())
                .map(|(tag, vals)| AxisInstances {
                    tag,
                    values: vals.into_iter().map(|v| v.0).collect(),
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

            (true, fvar_axes, axis_instances, opsz, final_slant)
        }
        Err(_) => (false, Vec::new(), Vec::new(), 0.0, slant),
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
        axis_instances,
        features,
    })
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

#[derive(Debug, Clone, Copy, PartialEq)]
struct OrderedF64(f64);

impl Eq for OrderedF64 {}

impl PartialOrd for OrderedF64 {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for OrderedF64 {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.0.total_cmp(&other.0)
    }
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
        assert!(info.axis_instances.is_empty());
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

        let wght_inst = info.axis_instances.iter().find(|a| &a.tag == b"wght").unwrap();
        assert_eq!(
            wght_inst.values,
            vec![100.0, 200.0, 300.0, 400.0, 500.0, 600.0, 700.0, 800.0, 900.0]
        );

        let opsz_inst = info.axis_instances.iter().find(|a| &a.tag == b"opsz").unwrap();
        assert_eq!(opsz_inst.values, vec![8.0, 14.0, 22.0, 32.0]);

        assert!(info.features.contains(&"kern".to_string()));
        assert!(info.features.contains(&"calt".to_string()));
        assert!(info.features.contains(&"ss01".to_string()));
    }
}
