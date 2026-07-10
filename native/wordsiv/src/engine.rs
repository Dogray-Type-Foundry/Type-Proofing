use std::collections::HashMap;
use std::sync::{Arc, Mutex, OnceLock};

use rand::distributions::WeightedIndex;
use rand::prelude::Distribution;
use rand::seq::SliceRandom;
use rand::Rng;
use rand::SeedableRng;
use rand_chacha::ChaCha8Rng;

use crate::errors::WordsivError;
use crate::filter::{CaseType, FilterParams};

#[cfg(feature = "semantic")]
use crate::semantic;
use crate::punctuation::{default_punctuation, punctuate, PunctuationConfig};
use crate::vocab::Vocab;

#[cfg(feature = "shaping")]
use crate::shaping;

const DEFAULT_MAX_NUM_LENGTH: usize = 4;
const BIAS_MULTIPLIER: f64 = 15.0;

// ---------------------------------------------------------------------------
// GenParams – a bag of all possible generation parameters
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct GenParams {
    // word-level filter
    pub glyphs: Option<String>,
    pub case: CaseType,
    pub rnd: f64,
    pub top_k: usize,
    pub min_wl: usize,
    pub max_wl: Option<usize>,
    pub wl: Option<usize>,
    pub contains: Vec<String>,
    pub inner: Vec<String>,
    pub startswith: Option<String>,
    pub endswith: Option<String>,
    pub regexp: Option<String>,
    pub raise_errors: bool,
    // character bias (soft weight boost)
    pub bias_chars: Vec<String>,
    pub bias_strength: f64,
    // theme (semantic filtering)
    pub theme: Option<String>,
    pub theme_strength: f64,
    // words-level
    pub vocab: Option<String>,
    pub n_words: Option<usize>,
    pub min_n_words: usize,
    pub max_n_words: usize,
    pub numbers: f64,
    pub cap_first: Option<bool>,
    // sent-level
    pub punc: bool,
    pub rnd_punc: f64,
    // sents-level
    pub min_n_sents: usize,
    pub max_n_sents: usize,
    pub n_sents: Option<usize>,
    // para-level
    pub sent_sep: String,
    // paras-level
    pub n_paras: usize,
    // text-level
    pub para_sep: String,
}

impl Default for GenParams {
    fn default() -> Self {
        Self {
            glyphs: None,
            case: CaseType::Any,
            rnd: 0.0,
            top_k: 0,
            min_wl: 1,
            max_wl: None,
            wl: None,
            contains: vec![],
            inner: vec![],
            startswith: None,
            endswith: None,
            regexp: None,
            raise_errors: false,

            bias_chars: vec![],
            bias_strength: 0.0,

            theme: None,
            theme_strength: 0.5,

            vocab: None,
            n_words: None,
            min_n_words: 10,
            max_n_words: 20,
            numbers: 0.0,
            cap_first: None,

            punc: true,
            rnd_punc: 0.0,

            min_n_sents: 3,
            max_n_sents: 5,
            n_sents: None,

            sent_sep: " ".to_string(),

            n_paras: 3,

            para_sep: "\n\n".to_string(),
        }
    }
}

// ---------------------------------------------------------------------------
// Weighted sampling with cached distribution
// ---------------------------------------------------------------------------

/// Pre-computed sampling distribution for a filtered wordcount + rnd value.
struct SamplingDist {
    words: Vec<String>,
    dist: Option<WeightedIndex<f64>>,
}

impl SamplingDist {
    fn new(wordcount: &[(String, u64)], rnd: f64, bias_chars: &[String], bias_strength: f64) -> Self {
        if wordcount.is_empty() || wordcount.len() == 1 {
            return Self {
                words: wordcount.iter().map(|(w, _)| w.clone()).collect(),
                dist: None,
            };
        }

        let max_count = wordcount
            .iter()
            .map(|(_, c)| *c as f64)
            .fold(0.0f64, f64::max);

        if max_count == 0.0 {
            return Self {
                words: wordcount.iter().map(|(w, _)| w.clone()).collect(),
                dist: None,
            };
        }

        let has_bias = !bias_chars.is_empty() && bias_strength > 0.0;
        let lower_bias: Vec<String> = if has_bias {
            bias_chars.iter().map(|bc| bc.to_lowercase()).collect()
        } else {
            vec![]
        };

        let weights: Vec<f64> = wordcount
            .iter()
            .map(|(word, c)| {
                let base = (1.0 - rnd) * (*c as f64) + rnd * max_count;
                if has_bias {
                    let word_lower = word.to_lowercase();
                    let match_count = lower_bias.iter()
                        .filter(|bc| word_lower.contains(bc.as_str()))
                        .count();
                    if match_count > 0 {
                        base * (1.0 + bias_strength * BIAS_MULTIPLIER * match_count as f64)
                    } else {
                        base
                    }
                } else {
                    base
                }
            })
            .collect();

        Self {
            words: wordcount.iter().map(|(w, _)| w.clone()).collect(),
            dist: WeightedIndex::new(&weights).ok(),
        }
    }

    fn sample(&self, rng: &mut impl Rng) -> String {
        if self.words.is_empty() {
            return String::new();
        }
        if self.words.len() == 1 || self.dist.is_none() {
            return self.words.choose(rng).unwrap().clone();
        }
        self.words[self.dist.as_ref().unwrap().sample(rng)].clone()
    }
}

// ---------------------------------------------------------------------------
// Global caches — shared across all instances (like Python's @lru_cache)
// ---------------------------------------------------------------------------

type FilterCacheKey = (String, FilterParams);
type FilterCacheVal = Arc<Vec<(String, u64)>>;
type SamplingCacheKey = (String, FilterParams, u64, usize, Option<String>, u64, Vec<String>, u64);
type SamplingCacheVal = Arc<SamplingDist>;

static FILTER_CACHE: OnceLock<Mutex<HashMap<FilterCacheKey, FilterCacheVal>>> = OnceLock::new();
static SAMPLING_CACHE: OnceLock<Mutex<HashMap<SamplingCacheKey, SamplingCacheVal>>> = OnceLock::new();

fn global_filter_cache() -> &'static Mutex<HashMap<FilterCacheKey, FilterCacheVal>> {
    FILTER_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

fn global_sampling_cache() -> &'static Mutex<HashMap<SamplingCacheKey, SamplingCacheVal>> {
    SAMPLING_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

// ---------------------------------------------------------------------------
// Default vocabs — parsed once lazily, shared across all instances
// ---------------------------------------------------------------------------

static DEFAULT_VOCAB_DATA: &[(&str, &[u8], &str)] = &[
    ("en", include_bytes!("../data/en_books.tsv.zst"), include_str!("../data/en_books_meta.json")),
    ("ar", include_bytes!("../data/ar_subs.tsv.zst"), include_str!("../data/ar_subs_meta.json")),
    ("es", include_bytes!("../data/es_subs.tsv.zst"), include_str!("../data/es_subs_meta.json")),
    ("fa", include_bytes!("../data/fa_subs.tsv.zst"), include_str!("../data/fa_subs_meta.json")),
    ("af", include_bytes!("../data/af.tsv.zst"), include_str!("../data/af_meta.json")),
    ("az", include_bytes!("../data/az.tsv.zst"), include_str!("../data/az_meta.json")),
    ("bm", include_bytes!("../data/bm.tsv.zst"), include_str!("../data/bm_meta.json")),
    ("ca", include_bytes!("../data/ca.tsv.zst"), include_str!("../data/ca_meta.json")),
    ("cs", include_bytes!("../data/cs.tsv.zst"), include_str!("../data/cs_meta.json")),
    ("cy", include_bytes!("../data/cy.tsv.zst"), include_str!("../data/cy_meta.json")),
    ("da", include_bytes!("../data/da.tsv.zst"), include_str!("../data/da_meta.json")),
    ("dag", include_bytes!("../data/dag.tsv.zst"), include_str!("../data/dag_meta.json")),
    ("de", include_bytes!("../data/de.tsv.zst"), include_str!("../data/de_meta.json")),
    ("eo", include_bytes!("../data/eo.tsv.zst"), include_str!("../data/eo_meta.json")),
    ("et", include_bytes!("../data/et.tsv.zst"), include_str!("../data/et_meta.json")),
    ("eu", include_bytes!("../data/eu.tsv.zst"), include_str!("../data/eu_meta.json")),
    ("ff", include_bytes!("../data/ff.tsv.zst"), include_str!("../data/ff_meta.json")),
    ("fi", include_bytes!("../data/fi.tsv.zst"), include_str!("../data/fi_meta.json")),
    ("fr", include_bytes!("../data/fr.tsv.zst"), include_str!("../data/fr_meta.json")),
    ("gag", include_bytes!("../data/gag.tsv.zst"), include_str!("../data/gag_meta.json")),
    ("gl", include_bytes!("../data/gl.tsv.zst"), include_str!("../data/gl_meta.json")),
    ("gn", include_bytes!("../data/gn.tsv.zst"), include_str!("../data/gn_meta.json")),
    ("ha", include_bytes!("../data/ha.tsv.zst"), include_str!("../data/ha_meta.json")),
    ("haw", include_bytes!("../data/haw.tsv.zst"), include_str!("../data/haw_meta.json")),
    ("hr", include_bytes!("../data/hr.tsv.zst"), include_str!("../data/hr_meta.json")),
    ("hu", include_bytes!("../data/hu.tsv.zst"), include_str!("../data/hu_meta.json")),
    ("id", include_bytes!("../data/id.tsv.zst"), include_str!("../data/id_meta.json")),
    ("ig", include_bytes!("../data/ig.tsv.zst"), include_str!("../data/ig_meta.json")),
    ("is", include_bytes!("../data/is.tsv.zst"), include_str!("../data/is_meta.json")),
    ("it", include_bytes!("../data/it.tsv.zst"), include_str!("../data/it_meta.json")),
    ("kab", include_bytes!("../data/kab.tsv.zst"), include_str!("../data/kab_meta.json")),
    ("kr", include_bytes!("../data/kr.tsv.zst"), include_str!("../data/kr_meta.json")),
    ("ln", include_bytes!("../data/ln.tsv.zst"), include_str!("../data/ln_meta.json")),
    ("lt", include_bytes!("../data/lt.tsv.zst"), include_str!("../data/lt_meta.json")),
    ("lv", include_bytes!("../data/lv.tsv.zst"), include_str!("../data/lv_meta.json")),
    ("mad", include_bytes!("../data/mad.tsv.zst"), include_str!("../data/mad_meta.json")),
    ("mi", include_bytes!("../data/mi.tsv.zst"), include_str!("../data/mi_meta.json")),
    ("min", include_bytes!("../data/min.tsv.zst"), include_str!("../data/min_meta.json")),
    ("ms", include_bytes!("../data/ms.tsv.zst"), include_str!("../data/ms_meta.json")),
    ("mt", include_bytes!("../data/mt.tsv.zst"), include_str!("../data/mt_meta.json")),
    ("nah", include_bytes!("../data/nah.tsv.zst"), include_str!("../data/nah_meta.json")),
    ("nl", include_bytes!("../data/nl.tsv.zst"), include_str!("../data/nl_meta.json")),
    ("nn", include_bytes!("../data/nn.tsv.zst"), include_str!("../data/nn_meta.json")),
    ("pl", include_bytes!("../data/pl.tsv.zst"), include_str!("../data/pl_meta.json")),
    ("pt", include_bytes!("../data/pt.tsv.zst"), include_str!("../data/pt_meta.json")),
    ("ro", include_bytes!("../data/ro.tsv.zst"), include_str!("../data/ro_meta.json")),
    ("se", include_bytes!("../data/se.tsv.zst"), include_str!("../data/se_meta.json")),
    ("sk", include_bytes!("../data/sk.tsv.zst"), include_str!("../data/sk_meta.json")),
    ("sl", include_bytes!("../data/sl.tsv.zst"), include_str!("../data/sl_meta.json")),
    ("sv", include_bytes!("../data/sv.tsv.zst"), include_str!("../data/sv_meta.json")),
    ("sw", include_bytes!("../data/sw.tsv.zst"), include_str!("../data/sw_meta.json")),
    ("tl", include_bytes!("../data/tl.tsv.zst"), include_str!("../data/tl_meta.json")),
    ("tr", include_bytes!("../data/tr.tsv.zst"), include_str!("../data/tr_meta.json")),
    ("uz", include_bytes!("../data/uz.tsv.zst"), include_str!("../data/uz_meta.json")),
    ("vi", include_bytes!("../data/vi.tsv.zst"), include_str!("../data/vi_meta.json")),
    ("xh", include_bytes!("../data/xh.tsv.zst"), include_str!("../data/xh_meta.json")),
    ("yo", include_bytes!("../data/yo.tsv.zst"), include_str!("../data/yo_meta.json")),
];

// Lazily decompressed + parsed default vocabs, cached for the process lifetime.
static VOCAB_CACHE: OnceLock<Mutex<HashMap<String, Arc<Vocab>>>> = OnceLock::new();

fn global_vocab_cache() -> &'static Mutex<HashMap<String, Arc<Vocab>>> {
    VOCAB_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Decompress a zstd-compressed vocab tsv blob into a String.
pub(crate) fn decompress_tsv(bytes: &[u8]) -> Result<String, WordsivError> {
    use std::io::Read;
    let mut decoder = ruzstd::StreamingDecoder::new(bytes)
        .map_err(|e| WordsivError::VocabFormat(format!("zstd init failed: {e}")))?;
    let mut out = Vec::new();
    decoder
        .read_to_end(&mut out)
        .map_err(|e| WordsivError::VocabFormat(format!("zstd decode failed: {e}")))?;
    String::from_utf8(out).map_err(|e| WordsivError::VocabFormat(format!("invalid utf8: {e}")))
}

/// Names of all built-in default vocabs (available without decompressing).
fn default_vocab_names() -> impl Iterator<Item = &'static str> {
    DEFAULT_VOCAB_DATA.iter().map(|&(name, _, _)| name)
}

/// Look up a built-in default vocab by key, decompressing + parsing it on first
/// use and caching it. Returns None if `key` is not a built-in vocab.
fn get_default_vocab(key: &str) -> Option<Arc<Vocab>> {
    // Fast path: already decompressed + parsed.
    {
        let cache = global_vocab_cache().lock().unwrap();
        if let Some(v) = cache.get(key) {
            return Some(Arc::clone(v));
        }
    }
    // Locate the compressed entry for this key.
    let &(_, tsv_zst, meta_json) = DEFAULT_VOCAB_DATA.iter().find(|&&(name, _, _)| name == key)?;
    // Decompress + parse OUTSIDE the lock so first-loads don't serialize.
    let tsv = decompress_tsv(tsv_zst).ok()?;
    let meta: serde_json::Value = serde_json::from_str(meta_json).ok()?;
    let lang = meta["lang"].as_str()?.to_string();
    let bicameral = meta["bicameral"].as_str()? == "True";
    let vocab = Vocab::from_tsv(lang, bicameral, &tsv, None, Some(meta)).ok()?;
    // Re-lock and insert; if another thread won the race, keep its entry.
    let mut cache = global_vocab_cache().lock().unwrap();
    let entry = cache.entry(key.to_string()).or_insert_with(|| Arc::new(vocab));
    Some(Arc::clone(entry))
}

// ---------------------------------------------------------------------------
// WordSiv
// ---------------------------------------------------------------------------

pub struct WordSiv {
    pub vocab_name: Option<String>,
    pub glyphs: Option<String>,
    pub raise_errors: bool,
    use_defaults: bool,
    vocab_lookup: HashMap<String, Arc<Vocab>>,
    rng: ChaCha8Rng,
}

impl WordSiv {
    pub fn new(
        vocab: Option<String>,
        glyphs: Option<String>,
        add_default_vocabs: bool,
        raise_errors: bool,
        seed: Option<u64>,
    ) -> Self {
        let rng = match seed {
            Some(s) => ChaCha8Rng::seed_from_u64(s),
            None => ChaCha8Rng::from_entropy(),
        };

        let ws = WordSiv {
            vocab_name: vocab,
            glyphs,
            raise_errors,
            use_defaults: add_default_vocabs,
            vocab_lookup: HashMap::new(),
            rng,
        };

        // Default vocabs are decompressed + parsed lazily on first request
        // (see get_default_vocab), so construction does no vocab work here.

        ws
    }

    // -- housekeeping -------------------------------------------------------

    pub fn seed(&mut self, seed: u64) {
        self.rng = ChaCha8Rng::seed_from_u64(seed);
    }

    pub fn add_vocab(&mut self, name: String, vocab: Vocab) {
        self.vocab_lookup.insert(name, Arc::new(vocab));
    }

    pub fn get_vocab(&self, name: Option<&str>) -> Result<Arc<Vocab>, WordsivError> {
        let key = name
            .or(self.vocab_name.as_deref())
            .ok_or_else(|| WordsivError::Value("No vocab specified".into()))?;
        // Check instance-level vocabs first, then built-in defaults
        if let Some(v) = self.vocab_lookup.get(key) {
            return Ok(Arc::clone(v));
        }
        if self.use_defaults {
            if let Some(v) = get_default_vocab(key) {
                return Ok(v);
            }
        }
        Err(WordsivError::Value(format!("Vocab '{key}' not found")))
    }

    pub fn list_vocabs(&self) -> Vec<String> {
        let mut keys: Vec<String> = self.vocab_lookup.keys().cloned().collect();
        if self.use_defaults {
            for k in default_vocab_names() {
                if !keys.iter().any(|existing| existing == k) {
                    keys.push(k.to_string());
                }
            }
        }
        keys
    }

    // -- helpers ------------------------------------------------------------

    fn effective_glyphs(&self, params: &GenParams) -> Option<String> {
        params.glyphs.clone().or_else(|| self.glyphs.clone())
    }

    fn effective_raise_errors(&self, params: &GenParams) -> bool {
        params.raise_errors || self.raise_errors
    }

    fn make_filter_params(&self, params: &GenParams, case_override: Option<CaseType>) -> FilterParams {
        FilterParams {
            glyphs: self.effective_glyphs(params),
            case: case_override.unwrap_or(params.case),
            min_wl: params.min_wl,
            max_wl: params.max_wl,
            wl: params.wl,
            contains: params.contains.clone(),
            inner: params.inner.clone(),
            startswith: params.startswith.clone(),
            endswith: params.endswith.clone(),
            regexp: params.regexp.clone(),
        }
    }

    /// Cached vocab filtering — uses global static cache (like Python's @lru_cache)
    fn cached_filter(
        &self,
        params: &GenParams,
        case_override: Option<CaseType>,
    ) -> Result<Arc<Vec<(String, u64)>>, WordsivError> {
        let fp = self.make_filter_params(params, case_override);
        let vocab_name = params
            .vocab
            .as_deref()
            .or(self.vocab_name.as_deref())
            .unwrap_or("")
            .to_string();
        let cache_key = (vocab_name, fp);

        {
            let cache = global_filter_cache().lock().unwrap();
            if let Some(cached) = cache.get(&cache_key) {
                if cached.is_empty() {
                    return Err(WordsivError::Filter(
                        "No words match the given filter parameters".into(),
                    ));
                }
                return Ok(Arc::clone(cached));
            }
        }

        let vocab_obj = self.get_vocab(params.vocab.as_deref())?;
        // Cache both successes AND failures (empty results) so we don't
        // re-scan the entire vocabulary on repeated failed-filter calls.
        let result = match vocab_obj.filter(&cache_key.1) {
            Ok(v) => Arc::new(v),
            Err(_) => Arc::new(vec![]),
        };
        {
            let mut cache = global_filter_cache().lock().unwrap();
            cache.insert(cache_key, Arc::clone(&result));
        }
        if result.is_empty() {
            return Err(WordsivError::Filter(
                "No words match the given filter parameters".into(),
            ));
        }
        Ok(result)
    }

    /// Apply theme-based semantic filtering to a word list.
    /// Returns the original list unchanged if no theme is set.
    #[cfg(feature = "semantic")]
    fn apply_theme_filter(
        &self,
        wc_list: &[(String, u64)],
        params: &GenParams,
    ) -> Vec<(String, u64)> {
        let theme = match &params.theme {
            Some(t) if !t.trim().is_empty() => t.as_str(),
            _ => return wc_list.to_vec(),
        };

        // Determine language from vocab name (default "en")
        let lang = params
            .vocab
            .as_deref()
            .or(self.vocab_name.as_deref())
            .and_then(|v| v.split('_').next())
            .unwrap_or("en");

        let store = match semantic::get_embedding_store(lang) {
            Ok(s) => s,
            Err(e) => {
                eprintln!("[wordsiv] Warning: could not load embeddings: {}", e);
                return wc_list.to_vec();
            }
        };

        semantic::filter_by_theme(&store, theme, params.theme_strength, wc_list)
    }

    /// No-op theme filter when semantic feature is disabled.
    #[cfg(not(feature = "semantic"))]
    fn apply_theme_filter(
        &self,
        wc_list: &[(String, u64)],
        _params: &GenParams,
    ) -> Vec<(String, u64)> {
        wc_list.to_vec()
    }

    /// Get a cached sampling distribution — uses global static cache
    fn cached_sampling_dist(
        &self,
        params: &GenParams,
        case_override: Option<CaseType>,
    ) -> Result<Arc<SamplingDist>, WordsivError> {
        let fp = self.make_filter_params(params, case_override);
        let vocab_name = params
            .vocab
            .as_deref()
            .or(self.vocab_name.as_deref())
            .unwrap_or("")
            .to_string();
        let rnd_bits = params.rnd.to_bits();
        let top_k = params.top_k;
        let theme_key = params.theme.clone();
        let theme_str_bits = params.theme_strength.to_bits();
        let bias_chars_key = params.bias_chars.clone();
        let bias_str_bits = params.bias_strength.to_bits();
        let cache_key = (vocab_name, fp, rnd_bits, top_k, theme_key, theme_str_bits, bias_chars_key, bias_str_bits);

        {
            let cache = global_sampling_cache().lock().unwrap();
            if let Some(cached) = cache.get(&cache_key) {
                return Ok(Arc::clone(cached));
            }
        }

        let wc_list = self.cached_filter(params, case_override)?;

        // Apply theme filtering before top_k and sampling
        let themed_list = self.apply_theme_filter(&wc_list, params);
        let themed_ref: &[(String, u64)] = &themed_list;

        let wc = if top_k > 0 {
            &themed_ref[..top_k.min(themed_ref.len())]
        } else {
            themed_ref
        };
        let dist = Arc::new(SamplingDist::new(wc, params.rnd, &params.bias_chars, params.bias_strength));
        {
            let mut cache = global_sampling_cache().lock().unwrap();
            cache.insert(cache_key, Arc::clone(&dist));
        }
        Ok(dist)
    }

    // -- number -------------------------------------------------------------

    pub fn number(
        &mut self,
        seed: Option<u64>,
        glyphs: Option<&str>,
        wl: Option<usize>,
        min_wl: usize,
        max_wl: usize,
        raise_errors: bool,
    ) -> Result<String, WordsivError> {
        let glyphs = glyphs.or(self.glyphs.as_deref());
        let raise_errors = raise_errors || self.raise_errors;

        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let length = if let Some(w) = wl {
            w
        } else {
            if min_wl > max_wl {
                return Err(WordsivError::Value(
                    "'min_wl' must be less than or equal to 'max_wl'".into(),
                ));
            }
            self.rng.gen_range(min_wl..=max_wl)
        };

        let all_numerals = "0123456789";
        let available: String = if let Some(g) = glyphs {
            all_numerals.chars().filter(|c| g.contains(*c)).collect()
        } else {
            all_numerals.to_string()
        };

        if available.is_empty() {
            if raise_errors {
                return Err(WordsivError::Filter("No numerals available in glyphs".into()));
            } else {
                return Ok(String::new());
            }
        }

        let chars: Vec<char> = available.chars().collect();
        Ok((0..length)
            .map(|_| *chars.choose(&mut self.rng).unwrap())
            .collect())
    }

    // -- word ---------------------------------------------------------------

    pub fn word(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<String, WordsivError> {
        self.word_with_case(seed, params, None)
    }

    fn word_with_case(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
        case_override: Option<CaseType>,
    ) -> Result<String, WordsivError> {
        let raise_errors = self.effective_raise_errors(params);

        if !(0.0..=1.0).contains(&params.rnd) {
            return Err(WordsivError::Value("'rnd' must be between 0 and 1".into()));
        }

        if !(0.0..=1.0).contains(&params.bias_strength) {
            return Err(WordsivError::Value("'bias_strength' must be between 0 and 1".into()));
        }

        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let dist = match self.cached_sampling_dist(params, case_override) {
            Ok(d) => d,
            Err(e) => {
                if raise_errors {
                    return Err(e);
                } else {
                    return Ok(String::new());
                }
            }
        };

        Ok(dist.sample(&mut self.rng))
    }

    // -- top_word -----------------------------------------------------------

    pub fn top_word(
        &mut self,
        seed: Option<u64>,
        idx: usize,
        params: &GenParams,
    ) -> Result<String, WordsivError> {
        let raise_errors = self.effective_raise_errors(params);

        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let wc_list = match self.cached_filter(params, None) {
            Ok(list) => list,
            Err(e) => {
                if raise_errors {
                    return Err(e);
                } else {
                    return Ok(String::new());
                }
            }
        };

        let themed = self.apply_theme_filter(&wc_list, params);
        match themed.get(idx) {
            Some((w, _)) => Ok(w.clone()),
            None => {
                if raise_errors {
                    Err(WordsivError::Filter(format!("No word at index idx='{idx}'")))
                } else {
                    Ok(String::new())
                }
            }
        }
    }

    // -- top_words ----------------------------------------------------------

    pub fn top_words(
        &mut self,
        n_words: usize,
        idx: usize,
        params: &GenParams,
    ) -> Result<Vec<String>, WordsivError> {
        let raise_errors = self.effective_raise_errors(params);

        let wc_list = match self.cached_filter(params, None) {
            Ok(list) => list,
            Err(e) => {
                if raise_errors {
                    return Err(e);
                } else {
                    return Ok(vec![]);
                }
            }
        };

        let themed = self.apply_theme_filter(&wc_list, params);
        let slice = &themed[idx..themed.len().min(idx + n_words)];
        if slice.is_empty() {
            if raise_errors {
                return Err(WordsivError::Filter(format!(
                    "No words found at idx '{idx}'"
                )));
            } else {
                return Ok(vec![]);
            }
        }

        Ok(slice.iter().map(|(w, _)| w.clone()).collect())
    }

    // -- words --------------------------------------------------------------

    pub fn words(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<Vec<String>, WordsivError> {
        let glyphs = self.effective_glyphs(params);

        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let n = params
            .n_words
            .unwrap_or_else(|| self.rng.gen_range(params.min_n_words..=params.max_n_words));

        let cap_first = params.cap_first.unwrap_or_else(|| {
            glyphs
                .as_ref()
                .map(|g| g.chars().any(|c| c.is_uppercase()))
                .unwrap_or(true)
        });

        if !(0.0..=1.0).contains(&params.numbers) {
            return Err(WordsivError::Value(
                "'numbers' must be between 0 and 1".into(),
            ));
        }

        let raise_errors = self.effective_raise_errors(params);

        let mut word_list: Vec<String> = Vec::with_capacity(n);
        let mut last_w: Option<String> = None;

        for i in 0..n {
            let word_case = if cap_first && params.case == CaseType::Any && i == 0 {
                Some(CaseType::Cap)
            } else {
                None
            };

            let is_number = if params.numbers > 0.0 {
                let roll: f64 = self.rng.gen();
                roll < params.numbers
            } else {
                false
            };

            if is_number {
                // The defaulted number length must never sit below min_wl, or
                // number() errors out and nulls the entire words() call.
                let w = self.number(
                    None,
                    glyphs.as_deref(),
                    params.wl,
                    params.min_wl,
                    params.max_wl.unwrap_or(DEFAULT_MAX_NUM_LENGTH.max(params.min_wl)),
                    raise_errors,
                )?;
                if !w.is_empty() {
                    last_w = Some(w.clone());
                    word_list.push(w);
                }
            } else {
                let mut w = self.word_with_case(None, params, word_case)?;
                // Retry once to avoid consecutive repeats
                if Some(&w) == last_w.as_ref() {
                    w = self.word_with_case(None, params, word_case)?;
                }
                if !w.is_empty() {
                    last_w = Some(w.clone());
                    word_list.push(w);
                }
            }
        }

        Ok(word_list)
    }

    // -- sent ---------------------------------------------------------------

    pub fn sent(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<String, WordsivError> {
        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let word_list = self.words(None, params)?;

        if params.punc {
            if !(0.0..=1.0).contains(&params.rnd_punc) {
                return Err(WordsivError::Value(
                    "'rnd_punc' must be between 0 and 1".into(),
                ));
            }

            // Determine punctuation config
            let punc_config: Option<PunctuationConfig> = {
                let vocab_obj = self.get_vocab(params.vocab.as_deref())?;
                if let Some(ref p) = vocab_obj.punctuation {
                    Some(p.clone())
                } else {
                    default_punctuation(&vocab_obj.lang)
                }
            };

            if let Some(config) = punc_config {
                let glyphs = self.effective_glyphs(params);
                return Ok(punctuate(
                    &config,
                    &mut self.rng,
                    &word_list,
                    glyphs.as_deref(),
                    params.rnd_punc,
                ));
            }
        }

        Ok(word_list.join(" "))
    }

    // -- sents --------------------------------------------------------------

    pub fn sents(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<Vec<String>, WordsivError> {
        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let n = params
            .n_sents
            .unwrap_or_else(|| self.rng.gen_range(params.min_n_sents..=params.max_n_sents));

        (0..n).map(|_| self.sent(None, params)).collect()
    }

    // -- para ---------------------------------------------------------------

    pub fn para(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<String, WordsivError> {
        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let sentences = self.sents(None, params)?;
        Ok(sentences.join(&params.sent_sep))
    }

    // -- paras --------------------------------------------------------------

    pub fn paras(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<Vec<String>, WordsivError> {
        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        (0..params.n_paras)
            .map(|_| self.para(None, params))
            .collect()
    }

    // -- text ---------------------------------------------------------------

    pub fn text(
        &mut self,
        seed: Option<u64>,
        params: &GenParams,
    ) -> Result<String, WordsivError> {
        if let Some(s) = seed {
            self.rng = ChaCha8Rng::seed_from_u64(s);
        }

        let paragraphs = self.paras(None, params)?;
        Ok(paragraphs.join(&params.para_sep))
    }

    // -- same_width_words ---------------------------------------------------

    /// Find words (and optionally phrases) from the vocabulary whose advance
    /// width when set in the given font matches `target_width` (in font design
    /// units) within `tolerance`.
    ///
    /// Uses harfrust for accurate OpenType text shaping, including kerning,
    /// ligatures, and complex script support. Supports variable fonts via
    /// `variations` and OpenType feature selection via `features`.
    ///
    /// Results are cached by font (hashed), filter params, features, and
    /// variation settings so that subsequent calls with different
    /// `target_width` / `tolerance` values are near-instant.
    #[cfg(feature = "shaping")]
    pub fn same_width_words(
        &mut self,
        font_data: &[u8],
        target_width: i32,
        n: usize,
        tolerance: i32,
        features: &[harfrust::Feature],
        variations: &[harfrust::Variation],
        phrases: bool,
        max_retries: usize,
        fast_measure: Option<bool>,
        params: &GenParams,
    ) -> Result<Vec<String>, WordsivError> {
        let raise_errors = self.effective_raise_errors(params);

        // 1. Get filtered word list from vocab
        let wc_list = match self.cached_filter(params, None) {
            Ok(list) => list,
            Err(e) => {
                if raise_errors {
                    return Err(e);
                } else {
                    return Ok(vec![]);
                }
            }
        };

        // 1b. Apply theme filtering
        let themed_list = self.apply_theme_filter(&wc_list, params);

        // 2. Build cache key (include theme in filter_key so different themes
        //    produce separate MeasuredVocab entries)
        let fast = match fast_measure {
            Some(true) => true,
            Some(false) => false,
            None => shaping::should_use_fast_measure(&themed_list, features),
        };
        let font_hash = shaping::hash_font_data(font_data);
        let fp = self.make_filter_params(params, None);
        let filter_key = format!(
            "{:?}|theme={:?}|ts={}",
            fp,
            params.theme,
            params.theme_strength
        );
        let cache_key =
            shaping::make_shaping_cache_key(font_hash, &filter_key, features, variations, fast);

        // 3. Get or compute MeasuredVocab from themed list
        let measured = shaping::cached_measure(
            font_data, &themed_list, features, variations, &cache_key,
        )?;

        // 4. Find single words
        let mut results = measured.find_words(target_width, tolerance, n, max_retries);

        // 5. If phrases enabled and we need more results, find phrases
        //    Exclude words already selected as singles so they don't repeat.
        if phrases && results.len() < n {
            let exclude: std::collections::HashSet<String> =
                results.iter().cloned().collect();
            let remaining = n - results.len();
            let phrase_results =
                measured.find_phrases(target_width, tolerance, remaining, &exclude);
            results.extend(phrase_results);
        }

        results.truncate(n);

        // 6. Sort results by theme relevance so the most on-theme
        //    words/phrases appear first.
        #[cfg(feature = "semantic")]
        {
            if let Some(ref theme) = params.theme {
                if !theme.trim().is_empty() {
                    let lang = params
                        .vocab
                        .as_deref()
                        .or(self.vocab_name.as_deref())
                        .and_then(|v| v.split('_').next())
                        .unwrap_or("en");
                    if let Ok(store) = semantic::get_embedding_store(lang) {
                        if let Some(query_vec) = semantic::theme_vector(&store, theme) {
                            results.sort_by(|a, b| {
                                let sa = semantic::score_text(&store, &query_vec, a);
                                let sb = semantic::score_text(&store, &query_vec, b);
                                sb.partial_cmp(&sa).unwrap_or(std::cmp::Ordering::Equal)
                            });
                        }
                    }
                }
            }
        }

        // 7. Stable sort by bias_chars match count so words containing
        //    more bias characters appear first.
        if !params.bias_chars.is_empty() && params.bias_strength > 0.0 {
            let lower_bias: Vec<String> = params.bias_chars.iter()
                .map(|bc| bc.to_lowercase()).collect();
            results.sort_by(|a, b| {
                let ca = lower_bias.iter().filter(|bc| a.to_lowercase().contains(bc.as_str())).count();
                let cb = lower_bias.iter().filter(|bc| b.to_lowercase().contains(bc.as_str())).count();
                cb.cmp(&ca)
            });
        }

        Ok(results)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// SC3 — decompressing + parsing an embedded (zstd) vocab is lossless and
    /// matches the known source data for `de`.
    #[test]
    fn zstd_decompress_roundtrip_de() {
        let &(_, zst, meta_json) = DEFAULT_VOCAB_DATA
            .iter()
            .find(|&&(name, _, _)| name == "de")
            .expect("de vocab present");
        let tsv = decompress_tsv(zst).expect("de decompresses");
        let wc = crate::vocab::parse_tsv_data(&tsv).expect("de parses");
        // Golden values from the source data/de.tsv.
        assert_eq!(wc.len(), 59743);
        assert_eq!(wc[0], ("der".to_string(), 49880));
        assert_eq!(wc[1], ("und".to_string(), 41804));
        assert_eq!(wc[2], ("die".to_string(), 38310));
        let meta: serde_json::Value = serde_json::from_str(meta_json).unwrap();
        assert_eq!(meta["lang"].as_str().unwrap(), "de");
        assert_eq!(meta["bicameral"].as_str().unwrap(), "True");
    }

    /// SC4 — default vocabs load lazily: constructing WordSiv loads nothing, and
    /// requesting one language loads only that language (and caches it).
    #[test]
    fn default_vocabs_are_lazy() {
        // "haw" is requested by no other test, so it is only ever in the global
        // cache if this test puts it there.
        const LANG: &str = "haw";
        let ws = WordSiv::new(None, None, true, false, Some(0));
        assert!(
            !global_vocab_cache().lock().unwrap().contains_key(LANG),
            "constructing WordSiv must not eagerly decompress '{LANG}'"
        );
        let v = ws.get_vocab(Some(LANG)).expect("haw is a default vocab");
        assert_eq!(v.lang, LANG);
        assert!(
            global_vocab_cache().lock().unwrap().contains_key(LANG),
            "requested vocab should now be cached"
        );
        // A repeat request returns the same cached Arc (no re-decompress/parse).
        let v2 = ws.get_vocab(Some(LANG)).unwrap();
        assert!(Arc::ptr_eq(&v, &v2), "cached vocab should be reused");
    }
}
