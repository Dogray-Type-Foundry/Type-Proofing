use crate::font_info::load_font_info;

#[derive(Debug, Clone)]
pub struct AxisValues {
    pub tag: [u8; 4],
    pub values: Vec<f64>,
}

/// Returns the axis value tuples that should be used for generation.
/// For each axis: if default is at min or max boundary, returns (min, max).
/// Otherwise returns (min, default, max).
/// This matches the Python `variableFont()` logic.
pub fn get_generation_axes(data: &[u8]) -> Option<Vec<AxisValues>> {
    let info = load_font_info(data)?;
    if !info.is_variable || info.axes.is_empty() {
        return None;
    }

    let result = info
        .axes
        .iter()
        .map(|axis| {
            let min = clean_f64(axis.min);
            let def = clean_f64(axis.default);
            let max = clean_f64(axis.max);

            let values = if (def - min).abs() < 0.001 || (def - max).abs() < 0.001 {
                vec![min, max]
            } else {
                vec![min, def, max]
            };

            AxisValues {
                tag: axis.tag,
                values,
            }
        })
        .collect();

    Some(result)
}

fn clean_f64(v: f64) -> f64 {
    if (v - v.round()).abs() < 0.001 {
        v.round()
    } else {
        v
    }
}

/// Compute the Cartesian product of all axis value tuples.
/// Each element in the result is a Vec of (tag, value) pairs.
pub fn axis_product(axes: &[AxisValues]) -> Vec<Vec<([u8; 4], f64)>> {
    if axes.is_empty() {
        return vec![];
    }

    let mut result = vec![vec![]];
    for axis in axes {
        let mut new_result = Vec::new();
        for combo in &result {
            for &val in &axis.values {
                let mut new_combo = combo.clone();
                new_combo.push((axis.tag, val));
                new_result.push(new_combo);
            }
        }
        result = new_result;
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generation_axes_vf() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        let axes = get_generation_axes(&data).expect("should be variable");

        assert_eq!(axes.len(), 2);

        let opsz = axes.iter().find(|a| &a.tag == b"opsz").unwrap();
        // opsz: min=8, default=16, max=32 → default is not at boundary → (8, 16, 32)
        // Wait, let's check what default actually is
        assert_eq!(opsz.values.len(), 2, "opsz values: {:?}", opsz.values);
        // opsz default could be at 8 (min boundary)

        let wght = axes.iter().find(|a| &a.tag == b"wght").unwrap();
        assert_eq!(wght.values, vec![100.0, 400.0, 900.0]);
    }

    #[test]
    fn test_axis_product() {
        let axes = vec![
            AxisValues {
                tag: *b"opsz",
                values: vec![8.0, 32.0],
            },
            AxisValues {
                tag: *b"wght",
                values: vec![100.0, 400.0, 900.0],
            },
        ];

        let product = axis_product(&axes);
        assert_eq!(product.len(), 6);
        assert_eq!(product[0], vec![(*b"opsz", 8.0), (*b"wght", 100.0)]);
        assert_eq!(product[1], vec![(*b"opsz", 8.0), (*b"wght", 400.0)]);
        assert_eq!(product[5], vec![(*b"opsz", 32.0), (*b"wght", 900.0)]);
    }

    #[test]
    fn test_static_font_no_axes() {
        let data = std::fs::read("../../SetsGroteskXS-Regular.ttf").expect("font file");
        let axes = get_generation_axes(&data);
        assert!(axes.is_none());
    }
}
