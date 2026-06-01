use crate::errors::WordsivError;
use regex::Regex;
use std::collections::HashSet;

// ---------------------------------------------------------------------------
// CaseType
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum CaseType {
    Any,
    AnyOg,
    Lc,
    LcForce,
    Cap,
    CapOg,
    CapForce,
    Uc,
    UcOg,
    UcForce,
}

impl CaseType {
    pub fn from_str(s: &str) -> Result<Self, WordsivError> {
        match s {
            "any" => Ok(Self::Any),
            "any_og" => Ok(Self::AnyOg),
            "lc" => Ok(Self::Lc),
            "lc_force" => Ok(Self::LcForce),
            "cap" => Ok(Self::Cap),
            "cap_og" => Ok(Self::CapOg),
            "cap_force" => Ok(Self::CapForce),
            "uc" => Ok(Self::Uc),
            "uc_og" => Ok(Self::UcOg),
            "uc_force" => Ok(Self::UcForce),
            _ => Err(WordsivError::Value(format!("Invalid case option: {s}"))),
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Any => "any",
            Self::AnyOg => "any_og",
            Self::Lc => "lc",
            Self::LcForce => "lc_force",
            Self::Cap => "cap",
            Self::CapOg => "cap_og",
            Self::CapForce => "cap_force",
            Self::Uc => "uc",
            Self::UcOg => "uc_og",
            Self::UcForce => "uc_force",
        }
    }
}

impl Default for CaseType {
    fn default() -> Self {
        Self::Any
    }
}

// ---------------------------------------------------------------------------
// FilterParams
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Default, PartialEq, Eq, Hash)]
pub struct FilterParams {
    pub glyphs: Option<String>,
    pub case: CaseType,
    pub min_wl: usize,
    pub max_wl: Option<usize>,
    pub wl: Option<usize>,
    pub contains: Vec<String>,
    pub inner: Vec<String>,
    pub startswith: Option<String>,
    pub endswith: Option<String>,
    pub regexp: Option<String>,
}

// ---------------------------------------------------------------------------
// Bitmask glyph data
// ---------------------------------------------------------------------------

pub struct GlyphBitmasks {
    pub all: [u64; 2],
    pub lc: [u64; 2],
    pub uc: [u64; 2],
}

// ---------------------------------------------------------------------------
// Glyph helpers
// ---------------------------------------------------------------------------

struct GlyphSet {
    all: HashSet<char>,
    uc: HashSet<char>,
    lc: HashSet<char>,
}

impl GlyphSet {
    fn from_str(glyphs: &str) -> Self {
        Self {
            all: glyphs.chars().collect(),
            uc: glyphs.chars().filter(|c| c.is_uppercase()).collect(),
            lc: glyphs.chars().filter(|c| c.is_lowercase()).collect(),
        }
    }
}

// ---------------------------------------------------------------------------
// Char helpers
// ---------------------------------------------------------------------------

fn char_lower(c: char) -> char {
    c.to_lowercase().next().unwrap_or(c)
}

fn char_upper(c: char) -> char {
    c.to_uppercase().next().unwrap_or(c)
}

fn capitalize(s: &str) -> String {
    let mut chars = s.chars();
    match chars.next() {
        None => String::new(),
        Some(first) => {
            let upper: String = first.to_uppercase().collect();
            let rest: String = chars.flat_map(|c| c.to_lowercase()).collect();
            format!("{upper}{rest}")
        }
    }
}

fn is_camel_case(word: &str) -> bool {
    let chars: Vec<char> = word.chars().collect();
    for i in 0..chars.len().saturating_sub(1) {
        if chars[i].is_lowercase() && chars[i + 1].is_uppercase() {
            return true;
        }
    }
    false
}

fn has_double_upper_lower(word: &str) -> bool {
    let chars: Vec<char> = word.chars().collect();
    let mut uc_run = 0usize;
    for &c in &chars {
        if c.is_uppercase() {
            uc_run += 1;
        } else if c.is_lowercase() && uc_run >= 2 {
            return true;
        } else {
            uc_run = 0;
        }
    }
    false
}

// ---------------------------------------------------------------------------
// Public entry point
// ---------------------------------------------------------------------------

pub fn filter_wordcount(
    wordcount: &[(String, u64)],
    bicameral: bool,
    params: &FilterParams,
    word_masks: Option<&[[u64; 2]]>,
    glyph_masks: Option<&GlyphBitmasks>,
) -> Result<Vec<(String, u64)>, WordsivError> {
    let case = params.case;

    if bicameral && params.glyphs.is_some() && case == CaseType::Any {
        // try any_og → cap → uc
        let mut p = params.clone();
        p.case = CaseType::AnyOg;
        if let Ok(r) = filter_all_params(wordcount, bicameral, &p, word_masks, glyph_masks) {
            return Ok(r);
        }
        p.case = CaseType::Cap;
        if let Ok(r) = filter_all_params(wordcount, bicameral, &p, word_masks, glyph_masks) {
            return Ok(r);
        }
        p.case = CaseType::Uc;
        filter_all_params(wordcount, bicameral, &p, word_masks, glyph_masks)
    } else if case == CaseType::Any {
        let mut p = params.clone();
        p.case = CaseType::AnyOg;
        filter_all_params(wordcount, bicameral, &p, word_masks, glyph_masks)
    } else {
        filter_all_params(wordcount, bicameral, params, word_masks, glyph_masks)
    }
}

// ---------------------------------------------------------------------------
// Internal filtering pipeline
// ---------------------------------------------------------------------------

fn filter_all_params(
    wordcount: &[(String, u64)],
    bicameral: bool,
    params: &FilterParams,
    word_masks: Option<&[[u64; 2]]>,
    glyph_masks: Option<&GlyphBitmasks>,
) -> Result<Vec<(String, u64)>, WordsivError> {
    let glyphset = params.glyphs.as_ref().map(|g| GlyphSet::from_str(g));

    // Step 1 – case (and glyph) filter
    let cased = filter_case(
        wordcount,
        params.case,
        glyphset.as_ref(),
        bicameral,
        word_masks,
        glyph_masks,
    )?;
    if cased.is_empty() {
        return Err(WordsivError::Filter(format!(
            "No words for case='{}', glyphs='{}'",
            params.case.as_str(),
            params.glyphs.as_deref().unwrap_or("None")
        )));
    }

    // Step 2 – word-length / substring / regexp filter
    let compiled_re = match &params.regexp {
        Some(re_str) => Some(
            Regex::new(&format!("^(?:{re_str})"))
                .map_err(|e| WordsivError::Value(format!("Invalid regexp: {e}")))?,
        ),
        None => None,
    };

    let filtered: Vec<(String, u64)> = cased
        .into_iter()
        .filter(|(word, _)| {
            matches_wl_substr(
                word,
                params.min_wl,
                params.max_wl,
                params.wl,
                &params.contains,
                &params.inner,
                params.startswith.as_deref(),
                params.endswith.as_deref(),
                compiled_re.as_ref(),
            )
        })
        .collect();

    if filtered.is_empty() {
        return Err(WordsivError::Filter(format!(
            "No words for min_wl='{}', max_wl='{:?}', wl='{:?}', contains='{:?}', \
             inner='{:?}', startswith='{:?}', endswith='{:?}', regexp='{:?}'",
            params.min_wl,
            params.max_wl,
            params.wl,
            params.contains,
            params.inner,
            params.startswith,
            params.endswith,
            params.regexp,
        )));
    }

    Ok(filtered)
}

// ---------------------------------------------------------------------------
// Case filter
// ---------------------------------------------------------------------------

fn filter_case(
    wordcount: &[(String, u64)],
    case: CaseType,
    glyphs: Option<&GlyphSet>,
    bicameral: bool,
    word_masks: Option<&[[u64; 2]]>,
    glyph_masks: Option<&GlyphBitmasks>,
) -> Result<Vec<(String, u64)>, WordsivError> {
    // Glyph-availability checks for cases that need them
    if let Some(gs) = glyphs {
        let needs_lc = matches!(
            case,
            CaseType::Lc
                | CaseType::LcForce
                | CaseType::Cap
                | CaseType::CapOg
                | CaseType::CapForce
        );
        let needs_uc = matches!(
            case,
            CaseType::Cap
                | CaseType::CapOg
                | CaseType::CapForce
                | CaseType::Uc
                | CaseType::UcOg
                | CaseType::UcForce
        );
        if needs_lc && gs.lc.is_empty() {
            return Err(WordsivError::Filter(format!(
                "case='{}' but no lowercase glyphs found",
                case.as_str()
            )));
        }
        if needs_uc && gs.uc.is_empty() {
            return Err(WordsivError::Filter(format!(
                "case='{}' but no uppercase glyphs found",
                case.as_str()
            )));
        }
    }

    // Bitmask fast path: select the appropriate glyph mask for this case type.
    // - Non-bicameral: all cases just check gs.all → use glyph_masks.all
    // - Bicameral Any/AnyOg: check gs.all → use glyph_masks.all
    // - Bicameral Lc: check gs.lc → use glyph_masks.lc (subsumes is_lowercase check)
    // - Bicameral UcOg: check gs.uc → use glyph_masks.uc (subsumes is_uppercase check)
    let effective_mask: Option<&[u64; 2]> =
        glyph_masks.and_then(|gm| {
            if !bicameral {
                Some(&gm.all)
            } else {
                match case {
                    CaseType::Any | CaseType::AnyOg => Some(&gm.all),
                    CaseType::Lc => Some(&gm.lc),
                    CaseType::UcOg => Some(&gm.uc),
                    _ => None,
                }
            }
        });

    if let (Some(gm), Some(wm)) = (effective_mask, word_masks) {
        if glyphs.is_some() {
            let result: Vec<(String, u64)> = wordcount
                .iter()
                .zip(wm.iter())
                .filter(|(_, wm)| wm[0] & !gm[0] == 0 && wm[1] & !gm[1] == 0)
                .map(|((word, count), _)| (word.clone(), *count))
                .collect();

            return Ok(result);
        }
    }

    let result: Vec<(String, u64)> = wordcount
        .iter()
        .filter_map(|(word, count)| {
            match_case(word, case, glyphs, bicameral).map(|w| (w, *count))
        })
        .collect();

    Ok(result)
}

fn match_case(
    word: &str,
    case: CaseType,
    glyphs: Option<&GlyphSet>,
    bicameral: bool,
) -> Option<String> {
    if !bicameral {
        // Non-bicameral scripts (Arabic, Persian, …)
        return if let Some(gs) = glyphs {
            if word.chars().all(|c| gs.all.contains(&c)) {
                Some(word.to_string())
            } else {
                None
            }
        } else {
            Some(word.to_string())
        };
    }

    // Bicameral scripts
    match case {
        CaseType::Any | CaseType::AnyOg => {
            if let Some(gs) = glyphs {
                if word.chars().all(|c| gs.all.contains(&c)) {
                    Some(word.to_string())
                } else {
                    None
                }
            } else {
                Some(word.to_string())
            }
        }

        CaseType::Lc => {
            if !word.chars().all(|c| c.is_lowercase()) {
                return None;
            }
            if let Some(gs) = glyphs {
                if word.chars().all(|c| gs.lc.contains(&c)) {
                    Some(word.to_string())
                } else {
                    None
                }
            } else {
                Some(word.to_string())
            }
        }

        CaseType::LcForce => {
            if let Some(gs) = glyphs {
                if word.chars().all(|c| gs.lc.contains(&char_lower(c))) {
                    Some(word.to_lowercase())
                } else {
                    None
                }
            } else {
                Some(word.to_lowercase())
            }
        }

        CaseType::Cap => {
            // Only words that are already lowercase or capitalised
            let chars: Vec<char> = word.chars().collect();
            if chars.is_empty() {
                return None;
            }
            if !chars[1..].iter().all(|c| c.is_lowercase()) {
                return None;
            }
            if let Some(gs) = glyphs {
                if !gs.uc.contains(&char_upper(chars[0])) {
                    return None;
                }
                if !chars[1..].iter().all(|c| gs.lc.contains(c)) {
                    return None;
                }
            }
            Some(capitalize(word))
        }

        CaseType::CapOg => {
            let chars: Vec<char> = word.chars().collect();
            if chars.is_empty() {
                return None;
            }
            if !chars[0].is_uppercase() {
                return None;
            }
            if !chars[1..].iter().all(|c| c.is_lowercase()) {
                return None;
            }
            if let Some(gs) = glyphs {
                if !gs.uc.contains(&chars[0]) {
                    return None;
                }
                if !chars[1..].iter().all(|c| gs.lc.contains(c)) {
                    return None;
                }
            }
            Some(word.to_string())
        }

        CaseType::CapForce => {
            let chars: Vec<char> = word.chars().collect();
            if chars.is_empty() {
                return None;
            }
            if let Some(gs) = glyphs {
                if !gs.uc.contains(&char_upper(chars[0])) {
                    return None;
                }
                if !chars[1..].iter().all(|c| gs.lc.contains(&char_lower(*c))) {
                    return None;
                }
            }
            Some(capitalize(word))
        }

        CaseType::Uc => {
            if is_camel_case(word) || has_double_upper_lower(word) {
                return None;
            }
            if let Some(gs) = glyphs {
                if !word.chars().all(|c| gs.uc.contains(&char_upper(c))) {
                    return None;
                }
            }
            Some(word.to_uppercase())
        }

        CaseType::UcOg => {
            if !word.chars().all(|c| c.is_uppercase()) {
                return None;
            }
            if let Some(gs) = glyphs {
                if !word.chars().all(|c| gs.uc.contains(&c)) {
                    return None;
                }
            }
            Some(word.to_string())
        }

        CaseType::UcForce => {
            if let Some(gs) = glyphs {
                if !word.chars().all(|c| gs.uc.contains(&char_upper(c))) {
                    return None;
                }
            }
            Some(word.to_uppercase())
        }
    }
}

// ---------------------------------------------------------------------------
// Word-length / substring / regexp filter
// ---------------------------------------------------------------------------

fn matches_wl_substr(
    word: &str,
    min_wl: usize,
    max_wl: Option<usize>,
    wl: Option<usize>,
    contains: &[String],
    inner: &[String],
    startswith: Option<&str>,
    endswith: Option<&str>,
    regexp: Option<&Regex>,
) -> bool {
    let len = word.chars().count();

    // Word-length
    if let Some(exact) = wl {
        if len != exact {
            return false;
        }
    } else {
        if len < min_wl {
            return false;
        }
        if let Some(max) = max_wl {
            if len > max {
                return false;
            }
        }
    }

    // Starts-with
    if let Some(prefix) = startswith {
        if !word.starts_with(prefix) {
            return false;
        }
    }

    // Ends-with
    if let Some(suffix) = endswith {
        if !word.ends_with(suffix) {
            return false;
        }
    }

    // Contains
    for c in contains {
        if !word.contains(c.as_str()) {
            return false;
        }
    }

    // Inner (must appear with ≥1 char before and after)
    for inner_str in inner {
        let chars: Vec<char> = word.chars().collect();
        if chars.len() < inner_str.chars().count() + 2 {
            return false;
        }
        // Strip first and last character, check if remainder contains inner_str
        let trimmed: String = chars[1..chars.len() - 1].iter().collect();
        if !trimmed.contains(inner_str.as_str()) {
            return false;
        }
    }

    // Regexp (anchored at start of word)
    if let Some(re) = regexp {
        if !re.is_match(word) {
            return false;
        }
    }

    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::vocab::Vocab;

    fn make_vocab(words: &[(&str, u64)], bicameral: bool) -> Vocab {
        let wc: Vec<(String, u64)> = words.iter().map(|(w, c)| (w.to_string(), *c)).collect();
        Vocab::new("en".into(), bicameral, wc, None, None)
    }

    #[test]
    fn test_bitmask_exact_match() {
        let vocab = make_vocab(&[("cat", 1), ("dog", 1)], true);
        let params = FilterParams {
            glyphs: Some("catdog".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_bitmask_superset_passes() {
        let vocab = make_vocab(&[("cat", 1)], true);
        let params = FilterParams {
            glyphs: Some("catch".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "cat");
    }

    #[test]
    fn test_bitmask_subset_fails() {
        let vocab = make_vocab(&[("cat", 1)], true);
        let params = FilterParams {
            glyphs: Some("ca".into()),
            ..Default::default()
        };
        assert!(vocab.filter(&params).is_err());
    }

    #[test]
    fn test_bitmask_unicode_arabic() {
        let vocab = make_vocab(&[("\u{0639}\u{0631}\u{0628}", 1)], false);
        let params = FilterParams {
            glyphs: Some("\u{0639}\u{0631}\u{0628}\u{064A}".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn test_bitmask_irrelevant_chars_in_glyphs() {
        let vocab = make_vocab(&[("cat", 1)], true);
        let params = FilterParams {
            glyphs: Some("cat123$%".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].0, "cat");
    }

    #[test]
    fn test_bitmask_preserves_order() {
        let vocab = make_vocab(
            &[("the", 100), ("be", 80), ("to", 60), ("of", 40), ("and", 20)],
            true,
        );
        let params = FilterParams {
            glyphs: Some("theband of".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        let words: Vec<&str> = result.iter().map(|(w, _)| w.as_str()).collect();
        assert_eq!(words, vec!["the", "be", "to", "of", "and"]);
    }

    #[test]
    fn test_bitmask_non_bicameral() {
        let vocab = make_vocab(&[("\u{0639}\u{0631}\u{0628}", 1)], false);
        let params = FilterParams {
            glyphs: Some("\u{0639}\u{0631}\u{0628}".into()),
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn test_no_glyphs_passes_all() {
        let vocab = make_vocab(&[("cat", 1), ("dog", 1)], true);
        let params = FilterParams::default();
        let result = vocab.filter(&params).unwrap();
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_case_force_variants_still_work() {
        let vocab = make_vocab(&[("hello", 5), ("World", 3)], true);
        let params = FilterParams {
            glyphs: Some("HELLOhello".into()),
            case: CaseType::UcForce,
            ..Default::default()
        };
        let result = vocab.filter(&params).unwrap();
        assert!(result.iter().all(|(w, _)| w == &w.to_uppercase()));
    }

    #[test]
    fn bench_bitmask_vs_hashset() {
        use std::time::{Duration, Instant};
        use crate::vocab::Vocab;

        let iters = 200;

        fn run_bench(
            label: &str,
            vocab: &Vocab,
            params: &FilterParams,
            iters: usize,
        ) {
            // Warmup
            for _ in 0..10 {
                let _ = filter_wordcount(
                    vocab.wordcount(), vocab.bicameral, params, None, None,
                );
                let _ = vocab.filter(params);
            }

            // HashSet path
            let start = Instant::now();
            for _ in 0..iters {
                let _ = filter_wordcount(
                    vocab.wordcount(), vocab.bicameral, params, None, None,
                );
            }
            let hashset_dur = start.elapsed();

            // Bitmask path
            let start = Instant::now();
            for _ in 0..iters {
                let _ = vocab.filter(params);
            }
            let bitmask_dur = start.elapsed();

            // Verify identical results
            let hashset_result = filter_wordcount(
                vocab.wordcount(), vocab.bicameral, params, None, None,
            );
            let bitmask_result = vocab.filter(params);

            fn result_len(r: &Result<Vec<(String, u64)>, crate::errors::WordsivError>) -> usize {
                match r {
                    Ok(v) => v.len(),
                    Err(_) => 0,
                }
            }
            assert_eq!(result_len(&hashset_result), result_len(&bitmask_result));

            let ms = |d: Duration| d.as_secs_f64() * 1000.0 / iters as f64;
            let speedup = hashset_dur.as_secs_f64() / bitmask_dur.as_secs_f64();

            eprintln!(
                "  {:<48} {:>8.3}ms  {:>8.3}ms  {:>6.1}x  ({} → {} words)",
                label,
                ms(hashset_dur),
                ms(bitmask_dur),
                speedup,
                vocab.wordcount().len(),
                result_len(&hashset_result),
            );
        }

        let en_tsv = crate::engine::decompress_tsv(include_bytes!("../data/en_books.tsv.zst")).unwrap();
        let ar_tsv = crate::engine::decompress_tsv(include_bytes!("../data/ar_subs.tsv.zst")).unwrap();
        let fa_tsv = crate::engine::decompress_tsv(include_bytes!("../data/fa_subs.tsv.zst")).unwrap();
        let en = Vocab::from_tsv(
            "en".into(), true,
            &en_tsv, None, None,
        ).unwrap();
        let ar = Vocab::from_tsv(
            "ar".into(), false,
            &ar_tsv, None, None,
        ).unwrap();
        let fa = Vocab::from_tsv(
            "fa".into(), false,
            &fa_tsv, None, None,
        ).unwrap();

        eprintln!("\n  {:<48} {:>10}  {:>10}  {:>7}  {}",
            "Scenario", "HashSet", "Bitmask", "Speedup", "Vocab");
        eprintln!("  {}", "-".repeat(105));

        // ── hflr-proof.py style: English, limited glyph set ────────
        run_bench(
            "EN hflr-proof  glyphs=\"HAMBUGERFONTSIVhambu...\"",
            &en,
            &FilterParams {
                glyphs: Some("HAMBUGERFONTSIVhambugerfontsiv.,".into()),
                ..Default::default()
            },
            iters,
        );

        // Same with case=lc (regexp/case combos used in hflr)
        run_bench(
            "EN hflr lc     case=lc, min_wl=5",
            &en,
            &FilterParams {
                glyphs: Some("HAMBUGERFONTSIVhambugerfontsiv.,".into()),
                case: CaseType::Lc,
                min_wl: 5,
                ..Default::default()
            },
            iters,
        );

        // hflr uc path
        run_bench(
            "EN hflr uc     case=uc, min_wl=5",
            &en,
            &FilterParams {
                glyphs: Some("HAMBUGERFONTSIVhambugerfontsiv.,".into()),
                case: CaseType::Uc,
                min_wl: 5,
                ..Default::default()
            },
            iters,
        );

        // hflr cap path
        run_bench(
            "EN hflr cap    case=cap, min_wl=5",
            &en,
            &FilterParams {
                glyphs: Some("HAMBUGERFONTSIVhambugerfontsiv.,".into()),
                case: CaseType::Cap,
                min_wl: 5,
                ..Default::default()
            },
            iters,
        );

        // hflr with regex (tests bitmask + regex combined)
        run_bench(
            "EN hflr regex  case=lc, regexp=\"h[cdeoq].*\"",
            &en,
            &FilterParams {
                glyphs: Some("HAMBUGERFONTSIVhambugerfontsiv.,".into()),
                case: CaseType::Lc,
                min_wl: 5,
                regexp: Some("h[cdeoq].*".into()),
                ..Default::default()
            },
            iters,
        );

        // ── init-medi-fina.py style: Arabic, full glyph set ───────
        let ar_glyphs = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغء";
        run_bench(
            "AR init-medi-fina  full glyphs",
            &ar,
            &FilterParams {
                glyphs: Some(ar_glyphs.into()),
                ..Default::default()
            },
            iters,
        );

        run_bench(
            "AR startswith=ب min_wl=5 max_wl=14",
            &ar,
            &FilterParams {
                glyphs: Some(ar_glyphs.into()),
                min_wl: 5,
                max_wl: Some(14),
                startswith: Some("ب".into()),
                ..Default::default()
            },
            iters,
        );

        run_bench(
            "AR endswith=ن min_wl=5 max_wl=14",
            &ar,
            &FilterParams {
                glyphs: Some(ar_glyphs.into()),
                min_wl: 5,
                max_wl: Some(14),
                endswith: Some("ن".into()),
                ..Default::default()
            },
            iters,
        );

        // ── Farsi ──────────────────────────────────────────────────
        let fa_glyphs = "یهونملگکقفغعظطضصشسژزرذدخحچجثتپباء";
        run_bench(
            "FA init-medi-fina  full glyphs",
            &fa,
            &FilterParams {
                glyphs: Some(fa_glyphs.into()),
                ..Default::default()
            },
            iters,
        );

        run_bench(
            "FA inner=ک min_wl=5 max_wl=14",
            &fa,
            &FilterParams {
                glyphs: Some(fa_glyphs.into()),
                min_wl: 5,
                max_wl: Some(14),
                inner: vec!["ک".into()],
                ..Default::default()
            },
            iters,
        );

        // ── same_width_words.py style: full English alphabet ───────
        run_bench(
            "EN full alphabet (sww baseline filter)",
            &en,
            &FilterParams {
                glyphs: Some(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".into()
                ),
                ..Default::default()
            },
            iters,
        );

        // Lc with full alphabet — now uses bitmask via glyph_lc_mask
        run_bench(
            "EN lc full alphabet (NEW bitmask path)",
            &en,
            &FilterParams {
                glyphs: Some(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".into()
                ),
                case: CaseType::Lc,
                ..Default::default()
            },
            iters,
        );

        // UcOg with full alphabet — now uses bitmask via glyph_uc_mask
        run_bench(
            "EN uc_og full alphabet (NEW bitmask path)",
            &en,
            &FilterParams {
                glyphs: Some(
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ".into()
                ),
                case: CaseType::UcOg,
                ..Default::default()
            },
            iters,
        );

        // Narrow glyph set — forces many rejections
        run_bench(
            "EN narrow glyphs=\"aeiou\" (most words rejected)",
            &en,
            &FilterParams {
                glyphs: Some("aeiou".into()),
                case: CaseType::Lc,
                ..Default::default()
            },
            iters,
        );

        eprintln!();
    }
}
