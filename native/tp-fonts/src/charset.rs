use read_fonts::types::{GlyphId, GlyphId16};
use read_fonts::TableProvider;
use skrifa::{FontRef, MetadataProvider};
use std::collections::BTreeSet;

pub fn filtered_charset(data: &[u8]) -> String {
    let font = match FontRef::new(data) {
        Ok(f) => f,
        Err(_) => return String::new(),
    };

    let has_outlines = build_outline_set(&font);
    let mut chars = Vec::new();
    let mut seen = BTreeSet::new();

    // Primary path: iterate best cmap subtable sorted by codepoint
    if let Ok(cmap) = font.cmap() {
        if let Some((_, _, subtable)) = cmap.best_subtable() {
            let mut mappings: Vec<(u32, GlyphId)> = Vec::new();
            for (cp, gid) in subtable.iter() {
                mappings.push((cp, gid));
            }
            mappings.sort_by_key(|(cp, _)| *cp);

            for (codepoint, glyph_id) in &mappings {
                if !has_outlines.contains(&glyph_id.to_u32()) {
                    continue;
                }
                if let Some(ch) = char::from_u32(*codepoint) {
                    if seen.insert(ch) {
                        chars.push(ch);
                    }
                }
            }
        }
    }

    // Fallback: AGL name-based lookup if cmap yielded nothing
    if chars.is_empty() {
        if let Ok(post) = font.post() {
            for gid in &has_outlines {
                if let Some(name) = post.glyph_name(GlyphId16::new(*gid as u16)) {
                    if let Some(ch) = crate::agl::agl_to_unicode(name) {
                        if seen.insert(ch) {
                            chars.push(ch);
                        }
                    }
                }
            }
        }
    }

    chars.into_iter().collect()
}

fn build_outline_set(font: &FontRef) -> BTreeSet<u32> {
    let mut result = BTreeSet::new();
    let glyph_count = font.maxp().map(|m| m.num_glyphs()).unwrap_or(0);

    let post = font.post().ok();
    let skip_dot = |gid: u16| -> bool {
        if let Some(ref post) = post {
            if let Some(name) = post.glyph_name(GlyphId16::new(gid)) {
                return name.contains('.');
            }
        }
        false
    };

    if let Ok(glyf) = font.glyf() {
        if let Ok(loca) = font.loca(None) {
            for gid in 0..glyph_count {
                if skip_dot(gid) {
                    continue;
                }
                if let Ok(Some(glyph)) = loca.get_glyf(GlyphId::new(gid as u32), &glyf) {
                    if glyph.number_of_contours() != 0 {
                        result.insert(gid as u32);
                    }
                }
            }
        }
    } else if font.cff().is_ok() || font.cff2().is_ok() {
        let outline_glyphs = font.outline_glyphs();
        for gid in 0..glyph_count {
            if skip_dot(gid) {
                continue;
            }
            if outline_glyphs.get(skrifa::GlyphId::new(gid as u32)).is_some() {
                result.insert(gid as u32);
            }
        }
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_charset_sets_grotesk_vf() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        let charset = filtered_charset(&data);

        assert!(!charset.is_empty());
        let char_count = charset.chars().count();
        assert_eq!(char_count, 475, "charset char count mismatch: got {}", char_count);
        assert!(charset.contains('A'));
        assert!(charset.contains('z'));
        assert!(charset.contains('À'));
        assert!(charset.contains('€'));
        assert_eq!(charset.chars().next(), Some('!'));
    }
}
