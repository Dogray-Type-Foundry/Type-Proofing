use std::collections::HashMap;

use crate::errors::WordsivError;
use crate::filter::FilterParams;
use crate::punctuation::PunctuationConfig;

// ---------------------------------------------------------------------------
// CharMap — maps each unique vocab character to a bit position (0..127)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct CharMap {
    char_to_bit: HashMap<char, u8>,
}

impl CharMap {
    pub fn build(wordcount: &[(String, u64)]) -> Option<Self> {
        let mut char_to_bit: HashMap<char, u8> = HashMap::new();
        for (word, _) in wordcount {
            for c in word.chars() {
                if !char_to_bit.contains_key(&c) {
                    let idx = char_to_bit.len();
                    if idx >= 128 {
                        return None;
                    }
                    char_to_bit.insert(c, idx as u8);
                }
            }
        }
        Some(CharMap { char_to_bit })
    }

    pub fn bit_for(&self, c: char) -> Option<u8> {
        self.char_to_bit.get(&c).copied()
    }

    pub fn len(&self) -> usize {
        self.char_to_bit.len()
    }

    pub fn is_empty(&self) -> bool {
        self.char_to_bit.is_empty()
    }
}

// ---------------------------------------------------------------------------
// Vocab
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct Vocab {
    pub lang: String,
    pub bicameral: bool,
    pub punctuation: Option<PunctuationConfig>,
    pub meta: Option<serde_json::Value>,
    wordcount: Vec<(String, u64)>,
    char_map: Option<CharMap>,
    word_masks: Option<Vec<[u64; 2]>>,
}

impl Vocab {
    pub fn new(
        lang: String,
        bicameral: bool,
        wordcount: Vec<(String, u64)>,
        punctuation: Option<PunctuationConfig>,
        meta: Option<serde_json::Value>,
    ) -> Self {
        let char_map = CharMap::build(&wordcount);
        let word_masks = char_map.as_ref().map(|cm| {
            wordcount
                .iter()
                .map(|(word, _)| {
                    let mut mask = [0u64; 2];
                    for c in word.chars() {
                        if let Some(bit) = cm.bit_for(c) {
                            mask[(bit / 64) as usize] |= 1u64 << (bit % 64);
                        }
                    }
                    mask
                })
                .collect()
        });

        Self {
            lang,
            bicameral,
            wordcount,
            punctuation,
            meta,
            char_map,
            word_masks,
        }
    }

    pub fn from_tsv(
        lang: String,
        bicameral: bool,
        data: &str,
        punctuation: Option<PunctuationConfig>,
        meta: Option<serde_json::Value>,
    ) -> Result<Self, WordsivError> {
        let wordcount = parse_tsv_data(data)?;
        Ok(Self::new(lang, bicameral, wordcount, punctuation, meta))
    }

    pub fn wordcount(&self) -> &[(String, u64)] {
        &self.wordcount
    }

    pub fn filter(
        &self,
        params: &FilterParams,
    ) -> Result<Vec<(String, u64)>, WordsivError> {
        let glyph_masks: Option<crate::filter::GlyphBitmasks> =
            params.glyphs.as_ref().and_then(|glyphs| {
                self.char_map.as_ref().map(|cm| {
                    let mut all = [0u64; 2];
                    let mut lc = [0u64; 2];
                    let mut uc = [0u64; 2];
                    for c in glyphs.chars() {
                        if let Some(bit) = cm.bit_for(c) {
                            let idx = (bit / 64) as usize;
                            let flag = 1u64 << (bit % 64);
                            all[idx] |= flag;
                            if c.is_lowercase() {
                                lc[idx] |= flag;
                            }
                            if c.is_uppercase() {
                                uc[idx] |= flag;
                            }
                        }
                    }
                    crate::filter::GlyphBitmasks { all, lc, uc }
                })
            });

        crate::filter::filter_wordcount(
            &self.wordcount,
            self.bicameral,
            params,
            self.word_masks.as_deref(),
            glyph_masks.as_ref(),
        )
    }
}

/// Parse TSV data ("word\tcount" per line) or plain word list into (word, count) pairs.
pub fn parse_tsv_data(data: &str) -> Result<Vec<(String, u64)>, WordsivError> {
    if data.trim().is_empty() {
        return Err(WordsivError::VocabEmpty("No data found".into()));
    }

    let first_line = data.lines().next().unwrap_or("");

    if first_line.contains('\t') {
        // TSV: word\tcount
        let mut result = Vec::new();
        for line in data.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            let mut parts = line.splitn(2, '\t');
            let word = parts
                .next()
                .ok_or_else(|| WordsivError::VocabFormat("Missing word column".into()))?
                .to_string();
            let count_str = parts
                .next()
                .ok_or_else(|| WordsivError::VocabFormat("Missing count column".into()))?;
            let count: u64 = count_str
                .trim()
                .parse()
                .map_err(|_| WordsivError::VocabFormat(format!("Invalid count: {count_str}")))?;
            result.push((word, count));
        }
        Ok(result)
    } else {
        // Plain word list – assign count of 1
        Ok(data
            .lines()
            .map(|l| l.trim())
            .filter(|l| !l.is_empty())
            .map(|l| (l.to_string(), 1u64))
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_charmap_build_basic() {
        let wc = vec![
            ("apple".to_string(), 3),
            ("banana".to_string(), 2),
        ];
        let cm = CharMap::build(&wc).unwrap();
        // "apple" → {a, p, l, e}, "banana" → {b, n} (a already seen) → 6 unique
        assert_eq!(cm.len(), 6);
        assert!(cm.bit_for('a').is_some());
        assert!(cm.bit_for('z').is_none());
    }

    #[test]
    fn test_charmap_build_overflow_returns_none() {
        let wc: Vec<(String, u64)> = (0..129u32)
            .map(|i| (char::from_u32(0x4E00 + i).unwrap().to_string(), 1))
            .collect();
        assert!(CharMap::build(&wc).is_none());
    }

    #[test]
    fn test_charmap_build_exactly_128() {
        let wc: Vec<(String, u64)> = (0..128u32)
            .map(|i| (char::from_u32(0x4E00 + i).unwrap().to_string(), 1))
            .collect();
        assert!(CharMap::build(&wc).is_some());
    }

    #[test]
    fn test_vocab_new_builds_masks() {
        let wc = vec![
            ("ab".to_string(), 1),
            ("bc".to_string(), 1),
            ("ac".to_string(), 1),
        ];
        let vocab = Vocab::new("en".into(), true, wc, None, None);
        assert!(vocab.char_map.is_some());
        assert!(vocab.word_masks.is_some());
        let masks = vocab.word_masks.as_ref().unwrap();
        assert_eq!(masks.len(), 3);
    }

    #[test]
    fn test_vocab_overflow_has_no_masks() {
        let wc: Vec<(String, u64)> = (0..129u32)
            .map(|i| (char::from_u32(0x4E00 + i).unwrap().to_string(), 1))
            .collect();
        let vocab = Vocab::new("zh".into(), false, wc, None, None);
        assert!(vocab.char_map.is_none());
        assert!(vocab.word_masks.is_none());
    }

    #[test]
    fn test_word_mask_subset_check() {
        let wc = vec![
            ("cat".to_string(), 1),
            ("bat".to_string(), 1),
        ];
        let vocab = Vocab::new("en".into(), true, wc, None, None);
        let cm = vocab.char_map.as_ref().unwrap();
        let masks = vocab.word_masks.as_ref().unwrap();

        // Build glyph mask for "cat"
        let mut glyph_mask = [0u64; 2];
        for c in "cat".chars() {
            if let Some(bit) = cm.bit_for(c) {
                glyph_mask[(bit / 64) as usize] |= 1u64 << (bit % 64);
            }
        }

        // "cat" is a subset of "cat" glyphs → passes
        let m_cat = masks[0];
        assert_eq!(m_cat[0] & !glyph_mask[0], 0);
        assert_eq!(m_cat[1] & !glyph_mask[1], 0);

        // "bat" needs 'b' which is not in "cat" → fails
        let m_bat = masks[1];
        assert!(m_bat[0] & !glyph_mask[0] != 0 || m_bat[1] & !glyph_mask[1] != 0);
    }
}
