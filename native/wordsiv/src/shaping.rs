//! Text shaping and width measurement using harfrust.
//!
//! Provides functionality to measure the advance width of words when set in a
//! given font, and to find words (or phrases) matching a target width.

use std::collections::{BTreeMap, HashMap};
use std::sync::{Arc, Mutex, OnceLock};

use harfrust::{Direction, Feature, FontRef, GlyphBuffer, Language, Script, ShapePlan, Shaper, ShaperData, ShaperInstance, Tag, UnicodeBuffer, Variation};
use read_fonts::TableProvider;

use crate::errors::WordsivError;

// ---------------------------------------------------------------------------
// MeasuredVocab — words bucketed by advance width for O(1) lookup
// ---------------------------------------------------------------------------

/// Pre-measured vocabulary with words bucketed by their advance width in font
/// design units. Enables fast lookup of words matching a target width.
#[derive(Debug, Clone)]
pub struct MeasuredVocab {
    /// Words bucketed by advance width (integer key in font units).
    buckets: BTreeMap<i32, Vec<String>>,
    /// Advance width of a space character (for phrase composition).
    space_width: i32,
    /// Minimum measured width across all words.
    min_width: i32,
    /// Maximum measured width across all words.
    max_width: i32,
    /// Total number of words measured.
    word_count: usize,
}

impl MeasuredVocab {
    /// Find up to `n` single words whose advance width is within `tolerance`
    /// of `target_width`. If fewer than `n` are found
    /// tolerance is auto-widened up to `max_retries` times (multiplied by 1.25
    /// each iteration).
    pub fn find_words(
        &self,
        target_width: i32,
        tolerance: i32,
        n: usize,
        max_retries: usize,
    ) -> Vec<String> {
        let mut tol = tolerance;
        for _ in 0..=max_retries {
            let results = self.query_range(target_width, tol, n);
            if results.len() >= n {
                return results;
            }
            tol = ((tol as f64) * 1.25).ceil() as i32;
        }
        // Return whatever we got after all retries
        self.query_range(target_width, tol, n)
    }

    /// Find up to `n` multi-word phrases whose total advance width (including
    /// inter-word spaces) is within `tolerance` of `target_width`.
    ///
    /// Produces natural-looking, **varied** results:
    /// - Tries 4, 3, and 2-word compositions, interleaved rather than
    ///   exhausting one word-count before moving to the next.
    /// - Each phrase uses a different split-ratio profile so word lengths
    ///   vary across lines (some short-long-medium, some long-short, etc.)
    ///
    /// Words present in `exclude` will not appear in any phrase.  Once a word
    /// is used it is excluded from all subsequent phrases.
    pub fn find_phrases(
        &self,
        target_width: i32,
        tolerance: i32,
        n: usize,
        exclude: &std::collections::HashSet<String>,
    ) -> Vec<String> {
        use std::collections::HashSet;
        let mut phrases: Vec<String> = Vec::new();
        let mut used: HashSet<String> = exclude.clone();

        // Interleaved word-count schedule so we get variety across lines.
        // Repeat pattern: 4, 3, 2, 3, 4, 2, 3, ...
        let schedule = [4usize, 3, 2, 3, 4, 2, 3];
        let mut sched_idx = 0;
        let mut stalls = 0; // consecutive failures

        while phrases.len() < n && stalls < schedule.len() * 2 {
            let num_words = schedule[sched_idx % schedule.len()];
            let profile_idx = phrases.len(); // each phrase gets a different profile

            match self.compose_phrase(target_width, num_words, tolerance, &used, profile_idx) {
                Some((phrase, words_in_phrase)) => {
                    for w in &words_in_phrase {
                        used.insert(w.clone());
                    }
                    phrases.push(phrase);
                    stalls = 0;
                }
                None => {
                    stalls += 1;
                }
            }
            sched_idx += 1;
        }

        phrases.truncate(n);
        phrases
    }

    // Split-ratio profiles per word count.
    // Each profile is a slice of target fractions for non-last words;
    // the last word gets whatever remains and must land within tolerance.
    //
    // Designed for natural-looking variety: some front-heavy, some
    // back-heavy, some with a very short word mixed in.

    const PROFILES_4: &'static [[f64; 3]] = &[
        [0.15, 0.30, 0.25],  // short  medium medium  long
        [0.35, 0.15, 0.25],  // long   short  medium  medium
        [0.20, 0.40, 0.15],  // medium long   short   medium
        [0.25, 0.20, 0.35],  // medium medium long    short
        [0.30, 0.25, 0.20],  // medium medium medium  medium
        [0.18, 0.22, 0.40],  // short  medium long    short
    ];

    const PROFILES_3: &'static [[f64; 2]] = &[
        [0.20, 0.40],  // short  long   medium
        [0.40, 0.25],  // long   medium short
        [0.30, 0.45],  // medium long   short
        [0.50, 0.20],  // long   short  medium
        [0.25, 0.30],  // medium medium medium
        [0.15, 0.50],  // short  long   medium
    ];

    const PROFILES_2: &'static [f64] = &[
        0.35,  // short  long
        0.55,  // long   short
        0.45,  // medium medium
        0.30,  // short  long
        0.60,  // long   short
        0.40,  // medium medium
    ];

    /// Try to build a single phrase of exactly `num_words` words whose total
    /// advance width (with spaces) hits `target_width ± tolerance`.
    ///
    /// Uses a split-ratio profile (selected by `profile_idx`) to set a target
    /// width for each non-last word, with a ±35 % search window for variety.
    /// The last word must land within `tolerance` of the remaining width.
    fn compose_phrase(
        &self,
        target_width: i32,
        num_words: usize,
        tolerance: i32,
        used: &std::collections::HashSet<String>,
        profile_idx: usize,
    ) -> Option<(String, Vec<String>)> {
        if num_words < 2 {
            return None;
        }
        let total_spaces = (num_words as i32 - 1) * self.space_width;
        let text_width = target_width - total_spaces;
        if text_width <= 0 {
            return None;
        }

        let mut phrase_words: Vec<String> = Vec::new();
        let mut local_used: std::collections::HashSet<String> =
            std::collections::HashSet::new();
        let mut remaining = text_width;

        for i in 0..num_words {
            let is_last = i == num_words - 1;

            let target_w = if is_last {
                remaining
            } else {
                // Look up the fraction for this position from the profile.
                let frac = match num_words {
                    4 => {
                        let p = &Self::PROFILES_4[profile_idx % Self::PROFILES_4.len()];
                        p[i]
                    }
                    3 => {
                        let p = &Self::PROFILES_3[profile_idx % Self::PROFILES_3.len()];
                        p[i]
                    }
                    _ => {
                        // 2 words — only position 0 is non-last
                        Self::PROFILES_2[profile_idx % Self::PROFILES_2.len()]
                    }
                };
                (text_width as f64 * frac).round() as i32
            };

            // Search window: last word is tight; others get ±35 % for variety.
            let search_tol = if is_last {
                tolerance
            } else {
                ((target_w as f64).abs() * 0.35).ceil().max(30.0) as i32
            };

            let lo = (target_w - search_tol).max(self.min_width);
            let hi = (target_w + search_tol).min(self.max_width);

            if lo > hi {
                return None;
            }

            // Pick the first available unused word closest to target_w.
            let mut best: Option<(i32, i32, String)> = None; // (dist, width, word)
            for (&w, bucket) in self.buckets.range(lo..=hi) {
                let dist = (w - target_w).abs();
                if let Some((bd, _, _)) = &best {
                    if dist >= *bd {
                        continue;
                    }
                }
                for word in bucket {
                    if !used.contains(word) && !local_used.contains(word) {
                        best = Some((dist, w, word.clone()));
                        break;
                    }
                }
            }

            match best {
                Some((_, w, word)) => {
                    remaining -= w;
                    local_used.insert(word.clone());
                    phrase_words.push(word);
                }
                None => return None,
            }
        }

        if remaining.abs() <= tolerance {
            Some((phrase_words.join(" "), phrase_words))
        } else {
            None
        }
    }

    /// BTreeMap range query: collect up to `n` words within `tolerance` of
    /// `target`.
    fn query_range(&self, target: i32, tolerance: i32, n: usize) -> Vec<String> {
        let lo = target - tolerance;
        let hi = target + tolerance;
        let mut results: Vec<String> = Vec::new();
        for (_, words) in self.buckets.range(lo..=hi) {
            for w in words {
                results.push(w.clone());
                if results.len() >= n {
                    return results;
                }
            }
        }
        results
    }

    /// Returns the advance width of a space character in this font.
    pub fn space_width(&self) -> i32 {
        self.space_width
    }

    /// Total number of words that were measured.
    pub fn word_count(&self) -> usize {
        self.word_count
    }

    /// Minimum advance width across all measured words.
    pub fn min_width(&self) -> i32 {
        self.min_width
    }

    /// Maximum advance width across all measured words.
    pub fn max_width(&self) -> i32 {
        self.max_width
    }
}

// ---------------------------------------------------------------------------
// Word measurement
// ---------------------------------------------------------------------------

/// Measure the advance width of a single string using harfrust.
/// The buffer must have its direction, script, and language set to match the
/// ShapePlan before calling this function.
fn measure_text(
    shaper: &Shaper,
    plan: &ShapePlan,
    text: &str,
    features: &[Feature],
    mut buffer: UnicodeBuffer,
    direction: Direction,
    script: Script,
    language: Option<&Language>,
) -> (i32, GlyphBuffer) {
    buffer.push_str(text);
    buffer.set_direction(direction);
    buffer.set_script(script);
    if let Some(lang) = language {
        buffer.set_language(lang.clone());
    }

    let glyph_buf = shaper.shape_with_plan(plan, buffer, features);
    let width: i32 = glyph_buf
        .glyph_positions()
        .iter()
        .map(|p| p.x_advance)
        .sum();

    (width, glyph_buf)
}

/// Build a `Vec<Feature>` from string tag names like `["liga", "ss01"]`.
pub fn features_from_strings(tags: &[String]) -> Vec<Feature> {
    tags.iter()
        .filter_map(|s| {
            if s.len() != 4 {
                return None;
            }
            let bytes: [u8; 4] = s.as_bytes().try_into().ok()?;
            Some(Feature::new(Tag::new(&bytes), 1, ..))
        })
        .collect()
}

/// Build a `Vec<Variation>` from `(tag_string, value)` pairs.
pub fn variations_from_pairs(pairs: &[(String, f32)]) -> Vec<Variation> {
    pairs
        .iter()
        .filter_map(|(s, val)| {
            if s.len() != 4 {
                return None;
            }
            let bytes: [u8; 4] = s.as_bytes().try_into().ok()?;
            Some(Variation {
                tag: Tag::new(&bytes),
                value: *val,
            })
        })
        .collect()
}

/// Measure all words in a vocabulary and return a `MeasuredVocab` with words
/// bucketed by advance width.
///
/// Uses a single `ShapePlan` and reuses buffers for performance.
pub fn measure_all_words(
    font_data: &[u8],
    words: &[(String, u64)],
    features: &[Feature],
    variations: &[Variation],
) -> Result<MeasuredVocab, WordsivError> {
    let font_ref = FontRef::new(font_data)
        .map_err(|_| WordsivError::Value("Failed to parse font data".into()))?;

    // ShaperData is the expensive init — done once per font.
    let shaper_data = ShaperData::new(&font_ref);

    // Variable font instance (if any variations specified).
    let instance = if variations.is_empty() {
        None
    } else {
        Some(ShaperInstance::from_variations(
            &font_ref,
            variations.iter().copied(),
        ))
    };

    let shaper = shaper_data
        .shaper(&font_ref)
        .instance(instance.as_ref())
        .build();

    // Create a ShapePlan once — reused for all words.
    // Use a representative buffer to derive plan properties.
    let (plan, plan_direction, plan_script, plan_language) = {
        let mut probe_buf = UnicodeBuffer::new();
        probe_buf.push_str("a");
        probe_buf.guess_segment_properties();
        let dir = probe_buf.direction();
        let scr = probe_buf.script();
        let lang = probe_buf.language();
        let p = ShapePlan::new(
            &shaper,
            dir,
            Some(scr),
            lang.as_ref(),
            features,
        );
        (p, dir, scr, lang)
    };

    // Measure space width
    let space_width = {
        let buf = UnicodeBuffer::new();
        let (w, _) = measure_text(
            &shaper, &plan, " ", features, buf,
            plan_direction, plan_script, plan_language.as_ref(),
        );
        w
    };

    // Measure all words, bucketed by width
    let mut buckets: BTreeMap<i32, Vec<String>> = BTreeMap::new();
    let mut min_width = i32::MAX;
    let mut max_width = i32::MIN;
    let mut count = 0usize;

    // Reuse buffers across iterations
    let mut unicode_buf = UnicodeBuffer::new();

    for (word, _count) in words {
        let (width, glyph_buf) = measure_text(
            &shaper, &plan, word, features, unicode_buf,
            plan_direction, plan_script, plan_language.as_ref(),
        );
        // Reclaim the UnicodeBuffer from the GlyphBuffer for reuse
        unicode_buf = glyph_buf.clear();

        if width > 0 {
            if width < min_width {
                min_width = width;
            }
            if width > max_width {
                max_width = width;
            }
            buckets.entry(width).or_default().push(word.clone());
            count += 1;
        }
    }

    if count == 0 {
        min_width = 0;
        max_width = 0;
    }

    Ok(MeasuredVocab {
        buckets,
        space_width,
        min_width,
        max_width,
        word_count: count,
    })
}

// ---------------------------------------------------------------------------
// SimpleMetrics — fast per-character advance width lookup via hmtx
// ---------------------------------------------------------------------------

struct SimpleMetrics {
    advances: HashMap<char, i32>,
    space_width: i32,
}

impl SimpleMetrics {
    fn from_font(font_data: &[u8], charset: &[char]) -> Option<Self> {
        let font = FontRef::new(font_data).ok()?;
        let cmap = font.cmap().ok()?;
        let hmtx = font.hmtx().ok()?;

        let mut advances = HashMap::new();
        for &c in charset {
            let gid = cmap.map_codepoint(c as u32)?;
            let advance = hmtx.advance(gid)? as i32;
            advances.insert(c, advance);
        }

        let space_gid = cmap.map_codepoint(' ' as u32)?;
        let space_width = hmtx.advance(space_gid)? as i32;

        Some(SimpleMetrics {
            advances,
            space_width,
        })
    }

    fn estimate_width(&self, word: &str) -> Option<i32> {
        let mut width = 0i32;
        for c in word.chars() {
            width += *self.advances.get(&c)?;
        }
        Some(width)
    }
}

/// Collect unique characters from a word list.
fn unique_chars(words: &[(String, u64)]) -> Vec<char> {
    let mut seen = std::collections::HashSet::new();
    for (word, _) in words {
        for c in word.chars() {
            seen.insert(c);
        }
    }
    seen.into_iter().collect()
}

/// Fast word measurement: estimate widths using hmtx advances (no shaping).
///
/// Falls back to full shaping if SimpleMetrics can't be built (e.g., a char
/// has no cmap entry) or if `variations` are specified (need HVAR table).
pub fn measure_all_words_fast(
    font_data: &[u8],
    words: &[(String, u64)],
    features: &[Feature],
    variations: &[Variation],
) -> Result<MeasuredVocab, WordsivError> {
    if !variations.is_empty() {
        return measure_all_words(font_data, words, features, variations);
    }

    let charset = unique_chars(words);
    let simple = match SimpleMetrics::from_font(font_data, &charset) {
        Some(s) => s,
        None => return measure_all_words(font_data, words, features, variations),
    };

    let mut buckets: BTreeMap<i32, Vec<String>> = BTreeMap::new();
    let mut min_width = i32::MAX;
    let mut max_width = i32::MIN;
    let mut count = 0usize;

    for (word, _) in words {
        match simple.estimate_width(word) {
            Some(w) if w > 0 => {
                min_width = min_width.min(w);
                max_width = max_width.max(w);
                buckets.entry(w).or_default().push(word.clone());
                count += 1;
            }
            _ => {
                // Skip words that can't be estimated (shouldn't happen
                // since we validated all chars in from_font)
            }
        }
    }

    if count == 0 {
        min_width = 0;
        max_width = 0;
    }

    Ok(MeasuredVocab {
        buckets,
        space_width: simple.space_width,
        min_width,
        max_width,
        word_count: count,
    })
}

/// Check whether fast measurement is appropriate for a word list.
/// Returns true if all characters are Latin (U+0000–U+00FF) and no
/// features are requested.
pub fn should_use_fast_measure(words: &[(String, u64)], features: &[Feature]) -> bool {
    if !features.is_empty() {
        return false;
    }
    words.iter().all(|(word, _)| word.chars().all(|c| c as u32 <= 0x00FF))
}

// ---------------------------------------------------------------------------
// Global shaping cache
// ---------------------------------------------------------------------------

/// Cache key for pre-measured vocabularies. Keyed on:
/// - xxh3 hash of font file bytes
/// - a string representation of filter params (derived from FilterParams hash)
/// - feature tags
/// - variation axis settings
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct ShapingCacheKey {
    pub font_hash: u64,
    pub filter_key: String,
    pub features: Vec<String>,
    pub variations: Vec<(String, i32)>, // tag + value*1000 as int for hashing
    pub fast: bool,
}

type ShapingCacheVal = Arc<MeasuredVocab>;

static SHAPING_CACHE: OnceLock<Mutex<HashMap<ShapingCacheKey, ShapingCacheVal>>> = OnceLock::new();

fn global_shaping_cache() -> &'static Mutex<HashMap<ShapingCacheKey, ShapingCacheVal>> {
    SHAPING_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Compute a fast hash of font data using xxh3.
pub fn hash_font_data(font_data: &[u8]) -> u64 {
    xxhash_rust::xxh3::xxh3_64(font_data)
}

/// Build a cache key from the components.
pub fn make_shaping_cache_key(
    font_hash: u64,
    filter_key: &str,
    features: &[Feature],
    variations: &[Variation],
    fast: bool,
) -> ShapingCacheKey {
    ShapingCacheKey {
        font_hash,
        filter_key: filter_key.to_string(),
        features: features
            .iter()
            .map(|f| format!("{:?}:{}", f.tag, f.value))
            .collect(),
        variations: variations
            .iter()
            .map(|v| {
                let tag_str = format!("{:?}", v.tag);
                let val_int = (v.value * 1000.0) as i32;
                (tag_str, val_int)
            })
            .collect(),
        fast,
    }
}

/// Look up or compute a `MeasuredVocab` in the global cache.
pub fn cached_measure(
    font_data: &[u8],
    words: &[(String, u64)],
    features: &[Feature],
    variations: &[Variation],
    cache_key: &ShapingCacheKey,
) -> Result<Arc<MeasuredVocab>, WordsivError> {
    // Check cache first
    {
        let cache = global_shaping_cache().lock().unwrap();
        if let Some(cached) = cache.get(cache_key) {
            return Ok(Arc::clone(cached));
        }
    }

    // Cache miss — measure all words
    let measured = if cache_key.fast {
        measure_all_words_fast(font_data, words, features, variations)?
    } else {
        measure_all_words(font_data, words, features, variations)?
    };
    let arc = Arc::new(measured);

    {
        let mut cache = global_shaping_cache().lock().unwrap();
        // Bounded like the engine's filter/sampling caches: each entry holds a
        // fully measured vocabulary, so unbounded growth is real memory.
        if cache.len() >= 16 {
            cache.clear();
        }
        cache.insert(cache_key.clone(), Arc::clone(&arc));
    }

    Ok(arc)
}

/// Clear the global shaping cache (useful for memory management).
pub fn clear_shaping_cache() {
    let cache = global_shaping_cache().lock().unwrap();
    // Use interior mutability — we have the lock
    drop(cache);
    let mut cache = global_shaping_cache().lock().unwrap();
    cache.clear();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_features_from_strings() {
        let tags = vec!["liga".to_string(), "ss01".to_string()];
        let features = features_from_strings(&tags);
        assert_eq!(features.len(), 2);
    }

    #[test]
    fn test_variations_from_pairs() {
        let pairs = vec![("wght".to_string(), 700.0f32), ("wdth".to_string(), 75.0f32)];
        let variations = variations_from_pairs(&pairs);
        assert_eq!(variations.len(), 2);
    }

    #[test]
    fn test_measured_vocab_find_words() {
        // Create a synthetic MeasuredVocab
        let mut buckets = BTreeMap::new();
        buckets.insert(100, vec!["hi".to_string()]);
        buckets.insert(200, vec!["hello".to_string(), "world".to_string()]);
        buckets.insert(205, vec!["there".to_string()]);
        buckets.insert(300, vec!["alphabet".to_string()]);

        let mv = MeasuredVocab {
            buckets,
            space_width: 50,
            min_width: 100,
            max_width: 300,
            word_count: 5,
        };

        // Exact match
        let results = mv.find_words(200, 0, 10, 0);
        assert_eq!(results, vec!["hello", "world"]);

        // With tolerance
        let results = mv.find_words(200, 10, 10, 0);
        assert!(results.contains(&"hello".to_string()));
        assert!(results.contains(&"world".to_string()));
        assert!(results.contains(&"there".to_string()));

        // Auto-widen tolerance
        let results = mv.find_words(200, 1, 5, 10);
        assert!(results.len() >= 3); // should widen to find more
    }

    #[test]
    fn test_measured_vocab_find_phrases() {
        let mut buckets = BTreeMap::new();
        buckets.insert(100, vec!["hi".to_string(), "me".to_string()]);
        buckets.insert(150, vec!["you".to_string()]);
        buckets.insert(200, vec!["hello".to_string()]);

        let mv = MeasuredVocab {
            buckets,
            space_width: 50,
            min_width: 100,
            max_width: 200,
            word_count: 4,
        };

        // Target = 300 = 100 + 50 (space) + 150
        let no_exclude = std::collections::HashSet::new();
        let phrases = mv.find_phrases(300, 5, 10, &no_exclude);
        assert!(!phrases.is_empty());
        // Should find a phrase combining words at widths 100 + 150 = 250 text + 50 space = 300
        // Word order may vary depending on which gets picked first.
        let has_valid = phrases.iter().any(|p| {
            let words: Vec<&str> = p.split_whitespace().collect();
            let mut sorted = words.clone();
            sorted.sort();
            // Valid pairs: {hi, you} or {me, you} — either order
            sorted == vec!["hi", "you"] || sorted == vec!["me", "you"]
        });
        assert!(has_valid, "Expected phrase combining 100+50+150=300, got: {:?}", phrases);

        // With "hi" excluded, "hi" must not appear in any phrase
        let mut exclude_hi = std::collections::HashSet::new();
        exclude_hi.insert("hi".to_string());
        let phrases2 = mv.find_phrases(300, 5, 10, &exclude_hi);
        assert!(phrases2.iter().all(|p| !p.split_whitespace().any(|w| w == "hi")),
            "Excluded word 'hi' appeared in phrases: {:?}", phrases2);
    }

    #[test]
    fn test_find_phrases_varied_composition() {
        // Wider spread of word widths — simulates a real vocab.
        let mut buckets = BTreeMap::new();
        // Short words (~150-200)
        buckets.insert(150, vec!["the".to_string(), "and".to_string(), "for".to_string()]);
        buckets.insert(180, vec!["with".to_string(), "from".to_string()]);
        buckets.insert(200, vec!["their".to_string(), "about".to_string()]);
        // Medium words (~250-350)
        buckets.insert(250, vec!["before".to_string(), "family".to_string()]);
        buckets.insert(300, vec!["between".to_string(), "morning".to_string()]);
        buckets.insert(350, vec!["together".to_string(), "hospital".to_string()]);
        // Longer words (~400-500)
        buckets.insert(400, vec!["something".to_string(), "important".to_string()]);
        buckets.insert(450, vec!["everything".to_string(), "understand".to_string()]);
        buckets.insert(500, vec!["information".to_string(), "development".to_string()]);

        let mv = MeasuredVocab {
            buckets,
            space_width: 50,
            min_width: 150,
            max_width: 500,
            word_count: 18,
        };

        // Target 800: could be 2, 3, or 4 words depending on profile
        let no_exclude = std::collections::HashSet::new();
        let phrases = mv.find_phrases(800, 30, 4, &no_exclude);
        assert!(!phrases.is_empty(), "Should find phrases for target 800");

        // Multiple phrases should exist with different word counts
        let word_counts: Vec<usize> = phrases.iter()
            .map(|p| p.split_whitespace().count())
            .collect();
        // At least one multi-word phrase
        assert!(word_counts.iter().all(|&c| c >= 2),
            "All phrases should have 2+ words, got: {:?}", phrases);
    }

    #[test]
    fn test_find_phrases_no_word_repeats() {
        let mut buckets = BTreeMap::new();
        buckets.insert(200, vec!["alpha".to_string(), "bravo".to_string(),
                                  "delta".to_string(), "gamma".to_string()]);
        buckets.insert(210, vec!["hotel".to_string(), "india".to_string()]);

        let mv = MeasuredVocab {
            buckets,
            space_width: 50,
            min_width: 200,
            max_width: 210,
            word_count: 6,
        };

        // Target 450 = 200 + 50 + 200 (two balanced words)
        let no_exclude = std::collections::HashSet::new();
        let phrases = mv.find_phrases(450, 15, 3, &no_exclude);
        // Collect all individual words used across all phrases
        let mut seen = std::collections::HashSet::new();
        for phrase in &phrases {
            for word in phrase.split_whitespace() {
                assert!(!seen.contains(word),
                    "Word '{}' repeated across phrases: {:?}", word, phrases);
                seen.insert(word.to_string());
            }
        }
    }

    #[test]
    fn test_measure_all_words_with_real_font() {
        // Use a system font if available (macOS)
        let font_path = "/Library/Fonts/Arial Unicode.ttf";
        let font_data = match std::fs::read(font_path) {
            Ok(d) => d,
            Err(_) => {
                eprintln!("Skipping real font test: {} not found", font_path);
                return;
            }
        };

        let words = vec![
            ("hello".to_string(), 100u64),
            ("world".to_string(), 100),
            ("the".to_string(), 200),
            ("a".to_string(), 300),
            ("international".to_string(), 50),
        ];

        let measured = measure_all_words(&font_data, &words, &[], &[]).unwrap();

        // All words should be measured
        assert_eq!(measured.word_count(), 5);
        assert!(measured.min_width() > 0);
        assert!(measured.max_width() > measured.min_width());
        assert!(measured.space_width() > 0);

        // "international" should be wider than "a"
        // (we can't assert exact widths, but verify the structure is sane)
        let narrow = measured.find_words(measured.min_width(), 0, 1, 0);
        assert!(!narrow.is_empty());
    }

    #[test]
    fn test_cache_hit() {
        let mut buckets = BTreeMap::new();
        buckets.insert(100, vec!["test".to_string()]);
        let mv = MeasuredVocab {
            buckets,
            space_width: 50,
            min_width: 100,
            max_width: 100,
            word_count: 1,
        };

        let key = ShapingCacheKey {
            font_hash: 999999,
            filter_key: "test_cache".to_string(),
            features: vec![],
            variations: vec![],
            fast: false,
        };

        // Insert into cache
        {
            let mut cache = global_shaping_cache().lock().unwrap();
            cache.insert(key.clone(), Arc::new(mv));
        }

        // Look up from cache
        {
            let cache = global_shaping_cache().lock().unwrap();
            let cached = cache.get(&key);
            assert!(cached.is_some());
            assert_eq!(cached.unwrap().word_count(), 1);
        }
    }

    #[test]
    fn test_simple_metrics_from_real_font() {
        let font_path = "/Library/Fonts/Arial Unicode.ttf";
        let font_data = match std::fs::read(font_path) {
            Ok(d) => d,
            Err(_) => {
                eprintln!("Skipping: {} not found", font_path);
                return;
            }
        };

        let charset: Vec<char> = "Hello world".chars().collect();
        let sm = SimpleMetrics::from_font(&font_data, &charset).unwrap();
        assert!(sm.space_width > 0);
        assert!(sm.estimate_width("Hello").unwrap() > 0);
        assert!(sm.estimate_width("H").unwrap() < sm.estimate_width("Hello").unwrap());
    }

    #[test]
    fn test_fast_measure_latin_vocab() {
        let font_path = "/Library/Fonts/Arial Unicode.ttf";
        let font_data = match std::fs::read(font_path) {
            Ok(d) => d,
            Err(_) => {
                eprintln!("Skipping: {} not found", font_path);
                return;
            }
        };

        let words = vec![
            ("hello".to_string(), 100u64),
            ("world".to_string(), 100),
            ("the".to_string(), 200),
            ("a".to_string(), 300),
        ];

        let fast = measure_all_words_fast(&font_data, &words, &[], &[]).unwrap();
        let full = measure_all_words(&font_data, &words, &[], &[]).unwrap();

        assert_eq!(fast.word_count(), full.word_count());
        assert!(fast.space_width() > 0);
        assert!(fast.min_width() > 0);
    }

    #[test]
    fn test_should_use_fast_measure() {
        let latin_words = vec![("hello".to_string(), 1u64), ("world".to_string(), 1)];
        assert!(should_use_fast_measure(&latin_words, &[]));

        let arabic_words = vec![("\u{0639}\u{0631}\u{0628}".to_string(), 1u64)];
        assert!(!should_use_fast_measure(&arabic_words, &[]));

        let features = vec![Feature::new(Tag::new(b"liga"), 1, ..)];
        assert!(!should_use_fast_measure(&latin_words, &features));
    }

    #[test]
    fn test_fast_vs_full_cache_keys_differ() {
        let key_fast = make_shaping_cache_key(123, "test", &[], &[], true);
        let key_full = make_shaping_cache_key(123, "test", &[], &[], false);
        assert_ne!(key_fast, key_full);
    }
}
