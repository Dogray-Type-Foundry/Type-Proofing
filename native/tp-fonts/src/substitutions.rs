use read_fonts::types::GlyphId16;
use read_fonts::TableProvider;
use skrifa::FontRef;
use std::collections::{BTreeMap, BTreeSet, HashMap};

static SKIPPED_FEATURES: &[&str] = &[
    "init", "medi", "med2", "fina", "fin2", "fin3", "isol", "curs", "aalt", "rand",
];

#[derive(Debug, Clone)]
pub struct SubstitutionEntry {
    pub feature_tag: String,
    pub kind: &'static str,
    pub input_glyphs: Vec<u16>,
    pub output_glyphs: Vec<u16>,
    pub input_text: String,
    pub output_glyph_names: Vec<String>,
}

#[derive(Debug, Clone)]
pub struct SubstitutionFeature {
    pub feature_tag: String,
    pub entries: Vec<SubstitutionEntry>,
    pub output_glyphs: Vec<String>,
}

pub fn get_font_substitutions(data: &[u8]) -> Vec<SubstitutionFeature> {
    let font = match FontRef::new(data) {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };

    let gsub = match font.gsub() {
        Ok(g) => g,
        Err(_) => return Vec::new(),
    };

    let feature_list = match gsub.feature_list() {
        Ok(f) => f,
        Err(_) => return Vec::new(),
    };

    let lookup_list = match gsub.lookup_list() {
        Ok(l) => l,
        Err(_) => return Vec::new(),
    };

    let glyph_to_char = build_glyph_to_char(&font);
    let glyph_to_name = build_glyph_to_name(&font);

    let mut entries_by_tag: BTreeMap<String, Vec<SubstitutionEntry>> = BTreeMap::new();

    let fl_data = feature_list.offset_data();
    for record in feature_list.feature_records() {
        let tag = record.feature_tag().to_string();
        if SKIPPED_FEATURES.contains(&tag.as_str()) {
            continue;
        }

        let feature = match record.feature(fl_data) {
            Ok(f) => f,
            Err(_) => continue,
        };

        for idx_be in feature.lookup_list_indices() {
            let idx = idx_be.get() as usize;
            if let Ok(lookup) = lookup_list.lookups().get(idx) {
                let new_entries = extract_lookup_entries(
                    &lookup,
                    &tag,
                    &lookup_list,
                    idx,
                    &glyph_to_char,
                    &glyph_to_name,
                );
                entries_by_tag
                    .entry(tag.clone())
                    .or_default()
                    .extend(new_entries);
            }
        }
    }

    entries_by_tag
        .into_iter()
        .filter_map(|(tag, entries)| {
            let entries = dedupe_entries(entries);
            if entries.is_empty() {
                return None;
            }
            let mut output_glyphs: BTreeSet<String> = BTreeSet::new();
            for entry in &entries {
                output_glyphs.extend(entry.output_glyph_names.iter().cloned());
            }
            Some(SubstitutionFeature {
                feature_tag: tag,
                entries,
                output_glyphs: output_glyphs.into_iter().collect(),
            })
        })
        .collect()
}

fn extract_lookup_entries(
    lookup: &read_fonts::tables::gsub::SubstitutionLookup,
    tag: &str,
    lookup_list: &read_fonts::tables::gsub::SubstitutionLookupList,
    source_index: usize,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
) -> Vec<SubstitutionEntry> {
    use read_fonts::tables::gsub::SubstitutionSubtables;
    let mut entries = Vec::new();

    let subtables = match lookup.subtables() {
        Ok(s) => s,
        Err(_) => return entries,
    };

    match subtables {
        SubstitutionSubtables::Single(subs) => {
            for subtable in subs.iter() {
                if let Ok(single) = subtable {
                    extract_single(&single, tag, glyph_to_char, glyph_to_name, &mut entries);
                }
            }
        }
        SubstitutionSubtables::Ligature(subs) => {
            for subtable in subs.iter() {
                if let Ok(lig) = subtable {
                    extract_ligature(&lig, tag, glyph_to_char, glyph_to_name, &mut entries);
                }
            }
        }
        SubstitutionSubtables::ChainContextual(subs) => {
            for subtable in subs.iter() {
                if let Ok(chain) = subtable {
                    extract_chain_context(
                        &chain, tag, lookup_list, source_index,
                        glyph_to_char, glyph_to_name, &mut entries,
                    );
                }
            }
        }
        _ => {}
    }

    entries
}

fn extract_chain_context(
    chain: &read_fonts::tables::layout::ChainedSequenceContext,
    tag: &str,
    lookup_list: &read_fonts::tables::gsub::SubstitutionLookupList,
    source_index: usize,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
    entries: &mut Vec<SubstitutionEntry>,
) {
    use read_fonts::tables::layout::ChainedSequenceContext;

    match chain {
        ChainedSequenceContext::Format1(f) => {
            extract_chain_format1_records(f, lookup_list, tag, source_index, glyph_to_char, glyph_to_name, entries);
        }
        ChainedSequenceContext::Format2(_) => {}
        ChainedSequenceContext::Format3(f) => {
            collect_nested_entries(
                f.seq_lookup_records(), tag, lookup_list, source_index,
                glyph_to_char, glyph_to_name, entries,
            );
        }
    }
}

fn collect_nested_entries(
    records: &[read_fonts::tables::layout::SequenceLookupRecord],
    tag: &str,
    lookup_list: &read_fonts::tables::gsub::SubstitutionLookupList,
    source_index: usize,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
    entries: &mut Vec<SubstitutionEntry>,
) {
    for record in records {
        let nested_idx = record.lookup_list_index() as usize;
        if nested_idx == source_index {
            continue;
        }
        if let Ok(nested_lookup) = lookup_list.lookups().get(nested_idx) {
            let nested = extract_lookup_entries(
                &nested_lookup, tag, lookup_list, nested_idx,
                glyph_to_char, glyph_to_name,
            );
            for mut e in nested {
                e.kind = match e.kind {
                    "single" => "contextual_single",
                    "ligature" => "contextual_ligature",
                    other => other,
                };
                entries.push(e);
            }
        }
    }
}

fn extract_chain_format1_records(
    f1: &read_fonts::tables::layout::ChainedSequenceContextFormat1,
    lookup_list: &read_fonts::tables::gsub::SubstitutionLookupList,
    tag: &str,
    source_index: usize,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
    entries: &mut Vec<SubstitutionEntry>,
) {
    for rule_set_opt in f1.chained_seq_rule_sets().iter() {
        let rule_set = match rule_set_opt {
            Some(Ok(rs)) => rs,
            _ => continue,
        };
        for rule_result in rule_set.chained_seq_rules().iter() {
            let rule: read_fonts::tables::layout::ChainedSequenceRule = match rule_result {
                Ok(r) => r,
                Err(_) => continue,
            };
            collect_nested_entries(
                rule.seq_lookup_records(), tag, lookup_list, source_index,
                glyph_to_char, glyph_to_name, entries,
            );
        }
    }
}

fn extract_single(
    single: &read_fonts::tables::gsub::SingleSubst,
    tag: &str,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
    entries: &mut Vec<SubstitutionEntry>,
) {
    use read_fonts::tables::gsub::SingleSubst;

    match single {
        SingleSubst::Format1(fmt1) => {
            if let Ok(coverage) = fmt1.coverage() {
                let delta = fmt1.delta_glyph_id();
                for input_gid in coverage.iter() {
                    let input_raw = input_gid.to_u32() as u16;
                    let output_raw = (input_raw as i32 + delta as i32) as u16;
                    entries.push(make_entry(
                        tag, "single",
                        vec![input_raw], vec![output_raw],
                        glyph_to_char, glyph_to_name,
                    ));
                }
            }
        }
        SingleSubst::Format2(fmt2) => {
            if let Ok(coverage) = fmt2.coverage() {
                let subs = fmt2.substitute_glyph_ids();
                for (input_gid, output_be) in coverage.iter().zip(subs.iter()) {
                    let input_raw = input_gid.to_u32() as u16;
                    let output_raw = output_be.get().to_u32() as u16;
                    entries.push(make_entry(
                        tag, "single",
                        vec![input_raw], vec![output_raw],
                        glyph_to_char, glyph_to_name,
                    ));
                }
            }
        }
    }
}

fn extract_ligature(
    lig_subst: &read_fonts::tables::gsub::LigatureSubstFormat1,
    tag: &str,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
    entries: &mut Vec<SubstitutionEntry>,
) {
    let Ok(coverage) = lig_subst.coverage() else {
        return;
    };

    for (first_gid, lig_set_result) in coverage.iter().zip(lig_subst.ligature_sets().iter()) {
        let Ok(lig_set) = lig_set_result else {
            continue;
        };

        let first_raw = first_gid.to_u32() as u16;

        for lig_result in lig_set.ligatures().iter() {
            let Ok(ligature) = lig_result else {
                continue;
            };

            let mut input_glyphs = vec![first_raw];
            for comp in ligature.component_glyph_ids() {
                input_glyphs.push(comp.get().to_u32() as u16);
            }

            let output_raw = ligature.ligature_glyph().to_u32() as u16;

            entries.push(make_entry(
                tag, "ligature",
                input_glyphs, vec![output_raw],
                glyph_to_char, glyph_to_name,
            ));
        }
    }
}

fn make_entry(
    tag: &str,
    kind: &'static str,
    input_glyphs: Vec<u16>,
    output_glyphs: Vec<u16>,
    glyph_to_char: &HashMap<u16, char>,
    glyph_to_name: &HashMap<u16, String>,
) -> SubstitutionEntry {
    let input_text: String = input_glyphs
        .iter()
        .filter_map(|gid| glyph_to_char.get(gid))
        .collect();

    let output_glyph_names: Vec<String> = output_glyphs
        .iter()
        .map(|gid| {
            glyph_to_name
                .get(gid)
                .cloned()
                .unwrap_or_else(|| format!("gid{}", gid))
        })
        .collect();

    SubstitutionEntry {
        feature_tag: tag.to_string(),
        kind,
        input_glyphs,
        output_glyphs,
        input_text,
        output_glyph_names,
    }
}

fn dedupe_entries(entries: Vec<SubstitutionEntry>) -> Vec<SubstitutionEntry> {
    let mut seen = BTreeSet::new();
    let mut result = Vec::new();
    for entry in entries {
        let key = (
            entry.feature_tag.clone(),
            entry.kind,
            entry.input_glyphs.clone(),
            entry.output_glyphs.clone(),
        );
        if seen.insert(key) {
            result.push(entry);
        }
    }
    result
}

fn build_glyph_to_char(font: &FontRef) -> HashMap<u16, char> {
    let mut map = HashMap::new();
    if let Ok(cmap) = font.cmap() {
        if let Some((_, _, subtable)) = cmap.best_subtable() {
            for (codepoint, glyph_id) in subtable.iter() {
                let gid = glyph_id.to_u32() as u16;
                map.entry(gid).or_insert_with(|| {
                    char::from_u32(codepoint).unwrap_or('\0')
                });
            }
        }
    }
    map
}

fn build_glyph_to_name(font: &FontRef) -> HashMap<u16, String> {
    let mut map = HashMap::new();
    if let Ok(post) = font.post() {
        let glyph_count = font.maxp().map(|m| m.num_glyphs()).unwrap_or(0);
        for gid in 0..glyph_count {
            if let Some(name) = post.glyph_name(GlyphId16::new(gid)) {
                map.insert(gid, name.to_string());
            }
        }
    }
    map
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_substitutions_sets_grotesk_vf() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        let subs = get_font_substitutions(&data);

        assert!(!subs.is_empty());

        let tags: Vec<&str> = subs.iter().map(|s| s.feature_tag.as_str()).collect();
        assert!(tags.contains(&"calt"), "missing calt, got: {:?}", tags);
        assert!(tags.contains(&"case"), "missing case");
        assert!(tags.contains(&"ss01"), "missing ss01");
        assert!(tags.contains(&"tnum"), "missing tnum");

        // aalt should be skipped
        assert!(!tags.contains(&"aalt"), "aalt should be skipped");

        // Check counts match Python baseline approximately
        let case_feat = subs.iter().find(|s| s.feature_tag == "case").unwrap();
        assert_eq!(case_feat.entries.len(), 24, "case entries: {}", case_feat.entries.len());

        let tnum_feat = subs.iter().find(|s| s.feature_tag == "tnum").unwrap();
        assert_eq!(tnum_feat.entries.len(), 24, "tnum entries: {}", tnum_feat.entries.len());

        eprintln!("features: {}", subs.len());
        for feat in &subs {
            eprintln!("  {}: {} entries, {} output glyphs",
                feat.feature_tag, feat.entries.len(), feat.output_glyphs.len());
        }
    }
}
