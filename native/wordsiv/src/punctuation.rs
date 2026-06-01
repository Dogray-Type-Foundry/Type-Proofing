use rand::distributions::WeightedIndex;
use rand::prelude::Distribution;
use rand::seq::SliceRandom;
use rand::Rng;

/// Configuration for how to punctuate generated sentences.
#[derive(Debug, Clone)]
pub struct PunctuationConfig {
    /// (punctuation_string, weight) – inserted between words
    pub insert: Vec<(String, f64)>,
    /// ((prefix, suffix), weight) – wraps the entire sentence
    pub wrap_sent: Vec<((String, String), f64)>,
    /// ((prefix, suffix), weight) – wraps an inner span of words
    pub wrap_inner: Vec<((String, String), f64)>,
}

// ---------------------------------------------------------------------------
// Default punctuation tables (mirrors Python DEFAULT_PUNCTUATION)
// ---------------------------------------------------------------------------

pub fn default_punctuation(lang: &str) -> Option<PunctuationConfig> {
    match lang {
        "en" => Some(PunctuationConfig {
            insert: vec![
                (" ".into(), 0.365),
                (", ".into(), 0.403),
                (": ".into(), 0.088),
                ("; ".into(), 0.058),
                ("–".into(), 0.057),
                ("—".into(), 0.022),
                (" … ".into(), 0.006),
            ],
            wrap_sent: vec![
                (("".into(), ".".into()), 0.923),
                (("".into(), "!".into()), 0.034),
                (("".into(), "?".into()), 0.04),
                (("".into(), "…".into()), 0.003),
            ],
            wrap_inner: vec![
                (("".into(), "".into()), 0.825),
                (("(".into(), ")".into()), 0.133),
                (("\u{2018}".into(), "\u{2019}".into()), 0.013),
                (("\u{201C}".into(), "\u{201D}".into()), 0.028),
            ],
        }),

        "ar" => Some(PunctuationConfig {
            insert: vec![
                (" ".into(), 0.364),
                (": ".into(), 0.108),
                ("، ".into(), 0.463),
                ("؛ ".into(), 0.066),
            ],
            wrap_sent: vec![
                (("".into(), ".".into()), 0.914),
                (("".into(), "؟".into()), 0.052),
                (("".into(), "!".into()), 0.033),
            ],
            wrap_inner: vec![
                (("".into(), "".into()), 0.971),
                (("\u{2018}".into(), "\u{2019}".into()), 0.007),
                (("\u{201C}".into(), "\u{201D}".into()), 0.022),
            ],
        }),

        "fa" => Some(PunctuationConfig {
            insert: vec![
                (" ".into(), 0.364),
                (": ".into(), 0.108),
                ("، ".into(), 0.463),
                ("؛ ".into(), 0.066),
            ],
            wrap_sent: vec![
                (("".into(), ".".into()), 0.914),
                (("".into(), "؟".into()), 0.052),
                (("".into(), "!".into()), 0.033),
            ],
            wrap_inner: vec![
                (("".into(), "".into()), 0.971),
                (("\u{2018}".into(), "\u{2019}".into()), 0.007),
                (("\u{201C}".into(), "\u{201D}".into()), 0.022),
            ],
        }),

        "es" => Some(PunctuationConfig {
            insert: vec![
                (" ".into(), 0.277),
                (", ".into(), 0.49),
                (": ".into(), 0.093),
                ("; ".into(), 0.073),
                ("– ".into(), 0.026),
                ("— ".into(), 0.03),
                ("… ".into(), 0.011),
            ],
            wrap_sent: vec![
                (("".into(), ".".into()), 0.928),
                (("¡".into(), "!".into()), 0.029),
                (("¿".into(), "?".into()), 0.036),
                (("".into(), "…".into()), 0.008),
            ],
            wrap_inner: vec![
                (("".into(), "".into()), 0.814),
                (("(".into(), ")".into()), 0.129),
                (("\u{2018}".into(), "\u{2019}".into()), 0.013),
                (("\u{201C}".into(), "\u{201D}".into()), 0.044),
            ],
        }),

        // -----------------------------------------------------------------
        // Latin-script languages — grouped by quotation style × weight family
        // Insert weight families: default (English-like), romance, slavic
        // Quote styles derived from CLDR delimiter data
        // -----------------------------------------------------------------

        // Default weights + standard quotes \u{201C}…\u{201D} / \u{2018}…\u{2019}
        "af" | "az" | "cy" | "da" | "dag" | "gag" | "gn" | "ha" | "haw"
        | "id" | "ig" | "kr" | "ln" | "mad" | "mi" | "min" | "ms" | "mt"
        | "nah" | "sw" | "tl" | "tr" | "vi" | "xh" | "yo" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_standard(),
        }),

        // Romance weights + standard quotes
        "gl" | "pt" => Some(PunctuationConfig {
            insert: latin_romance_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_standard(),
        }),

        // Slavic weights + standard quotes (CLDR gives \u{201C}/\u{201D} for Latvian)
        "lv" => Some(PunctuationConfig {
            insert: latin_slavic_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_standard(),
        }),

        // Default weights + Finnish quotes (same char open+close)
        // \u{201D}…\u{201D} / \u{2019}…\u{2019}
        "fi" | "se" | "sv" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_finnish(),
        }),

        // Default weights + German low-9 quotes
        // \u{201E}…\u{201C} / \u{201A}…\u{2018}
        "de" | "et" | "is" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_german_low9(),
        }),

        // Slavic weights + German low-9 quotes
        "cs" | "hr" | "sk" | "sl" => Some(PunctuationConfig {
            insert: latin_slavic_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_german_low9(),
        }),

        // Default weights + Fulfulde quotes (low-9 open, right-double close)
        // \u{201E}…\u{201D} / \u{201A}…\u{2019}
        "ff" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_fulfulde(),
        }),

        // Default weights + guillemets primary, curly-double secondary
        // \u{00AB}…\u{00BB} / \u{201C}…\u{201D}
        "bm" | "eu" | "kab" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_guillemet(),
        }),

        // Romance weights + guillemets primary, curly-double secondary
        "ca" | "it" => Some(PunctuationConfig {
            insert: latin_romance_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_guillemet(),
        }),

        // Romance weights + French guillemets (same marks both levels)
        // \u{00AB}…\u{00BB} / \u{00AB}…\u{00BB}
        "fr" => Some(PunctuationConfig {
            insert: latin_romance_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_guillemet_fr(),
        }),

        // Default weights + Norwegian Nynorsk guillemets
        // \u{00AB}…\u{00BB} / \u{2018}…\u{2019}
        "nn" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_guillemet_nn(),
        }),

        // Slavic weights + Polish/Romanian quotes
        // \u{201E}…\u{201D} / \u{00AB}…\u{00BB}
        "pl" => Some(PunctuationConfig {
            insert: latin_slavic_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_polish(),
        }),

        // Romance weights + Polish/Romanian quotes
        "ro" => Some(PunctuationConfig {
            insert: latin_romance_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_polish(),
        }),

        // Default weights + Hungarian quotes (reversed guillemets for secondary)
        // \u{201E}…\u{201D} / \u{00BB}…\u{00AB}
        "hu" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_hungarian(),
        }),

        // Slavic weights + Lithuanian quotes (same low-9 pair for both levels)
        // \u{201E}…\u{201C} / \u{201E}…\u{201C}
        "lt" => Some(PunctuationConfig {
            insert: latin_slavic_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_lithuanian(),
        }),

        // Default weights + Dutch quotes (single curly for both levels)
        // \u{2018}…\u{2019} / \u{201C}…\u{201D}
        "nl" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_dutch(),
        }),

        // Default weights + Esperanto quotes
        // \u{201C}…\u{201D} / \u{00AB}…\u{00BB}
        "eo" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_esperanto(),
        }),

        // Default weights + Uzbek quotes (reversed single for secondary)
        // \u{201C}…\u{201D} / \u{2019}…\u{2018}
        "uz" => Some(PunctuationConfig {
            insert: latin_default_insert(),
            wrap_sent: latin_wrap_sent(),
            wrap_inner: inner_uzbek(),
        }),

        _ => None,
    }
}

// ---------------------------------------------------------------------------
// Latin-script insert-punctuation weight families
// ---------------------------------------------------------------------------

fn latin_default_insert() -> Vec<(String, f64)> {
    vec![
        (" ".into(), 0.365),
        (", ".into(), 0.403),
        (": ".into(), 0.088),
        ("; ".into(), 0.058),
        ("\u{2013} ".into(), 0.057),
        ("\u{2014} ".into(), 0.022),
        ("\u{2026} ".into(), 0.006),
    ]
}

fn latin_romance_insert() -> Vec<(String, f64)> {
    vec![
        (" ".into(), 0.277),
        (", ".into(), 0.49),
        (": ".into(), 0.093),
        ("; ".into(), 0.073),
        ("\u{2013} ".into(), 0.026),
        ("\u{2014} ".into(), 0.03),
        ("\u{2026} ".into(), 0.011),
    ]
}

fn latin_slavic_insert() -> Vec<(String, f64)> {
    vec![
        (" ".into(), 0.32),
        (", ".into(), 0.44),
        (": ".into(), 0.09),
        ("; ".into(), 0.065),
        ("\u{2013} ".into(), 0.04),
        ("\u{2014} ".into(), 0.035),
        ("\u{2026} ".into(), 0.01),
    ]
}

// ---------------------------------------------------------------------------
// Latin-script sentence wrap (shared by all Latin-script languages)
// ---------------------------------------------------------------------------

fn latin_wrap_sent() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), ".".into()), 0.923),
        (("".into(), "!".into()), 0.034),
        (("".into(), "?".into()), 0.04),
        (("".into(), "\u{2026}".into()), 0.003),
    ]
}

// ---------------------------------------------------------------------------
// Inner-wrap (quotation mark) variants — from CLDR delimiter data
// ---------------------------------------------------------------------------

// Standard: \u{201C}…\u{201D} / \u{2018}…\u{2019}
fn inner_standard() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{2018}".into(), "\u{2019}".into()), 0.013),
        (("\u{201C}".into(), "\u{201D}".into()), 0.028),
    ]
}

// Finnish/Swedish/Northern Sami: \u{201D}…\u{201D} / \u{2019}…\u{2019}
fn inner_finnish() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{2019}".into(), "\u{2019}".into()), 0.013),
        (("\u{201D}".into(), "\u{201D}".into()), 0.028),
    ]
}

// German/Czech/Croatian/Estonian/Icelandic/Slovak/Slovenian:
// \u{201E}…\u{201C} / \u{201A}…\u{2018}
fn inner_german_low9() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{201A}".into(), "\u{2018}".into()), 0.013),
        (("\u{201E}".into(), "\u{201C}".into()), 0.028),
    ]
}

// Fulfulde: \u{201E}…\u{201D} / \u{201A}…\u{2019}
fn inner_fulfulde() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{201A}".into(), "\u{2019}".into()), 0.013),
        (("\u{201E}".into(), "\u{201D}".into()), 0.028),
    ]
}

// Guillemets: \u{00AB}…\u{00BB} / \u{201C}…\u{201D}
fn inner_guillemet() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{201C}".into(), "\u{201D}".into()), 0.013),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.028),
    ]
}

// French: \u{00AB}…\u{00BB} for both levels
fn inner_guillemet_fr() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.02),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.02),
    ]
}

// Norwegian Nynorsk: \u{00AB}…\u{00BB} / \u{2018}…\u{2019}
fn inner_guillemet_nn() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{2018}".into(), "\u{2019}".into()), 0.013),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.028),
    ]
}

// Polish/Romanian: \u{201E}…\u{201D} / \u{00AB}…\u{00BB}
fn inner_polish() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.013),
        (("\u{201E}".into(), "\u{201D}".into()), 0.028),
    ]
}

// Hungarian: \u{201E}…\u{201D} / \u{00BB}…\u{00AB} (reversed guillemets)
fn inner_hungarian() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{00BB}".into(), "\u{00AB}".into()), 0.013),
        (("\u{201E}".into(), "\u{201D}".into()), 0.028),
    ]
}

// Lithuanian: \u{201E}…\u{201C} for both levels
fn inner_lithuanian() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{201E}".into(), "\u{201C}".into()), 0.02),
        (("\u{201E}".into(), "\u{201C}".into()), 0.02),
    ]
}

// Dutch: \u{2018}…\u{2019} primary, \u{201C}…\u{201D} secondary
fn inner_dutch() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{201C}".into(), "\u{201D}".into()), 0.013),
        (("\u{2018}".into(), "\u{2019}".into()), 0.028),
    ]
}

// Esperanto: \u{201C}…\u{201D} / \u{00AB}…\u{00BB}
fn inner_esperanto() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{00AB}".into(), "\u{00BB}".into()), 0.013),
        (("\u{201C}".into(), "\u{201D}".into()), 0.028),
    ]
}

// Uzbek: \u{201C}…\u{201D} / \u{2019}…\u{2018} (reversed single quotes)
fn inner_uzbek() -> Vec<((String, String), f64)> {
    vec![
        (("".into(), "".into()), 0.825),
        (("(".into(), ")".into()), 0.133),
        (("\u{2019}".into(), "\u{2018}".into()), 0.013),
        (("\u{201C}".into(), "\u{201D}".into()), 0.028),
    ]
}

// ---------------------------------------------------------------------------
// Weighted random selection helpers
// ---------------------------------------------------------------------------

/// Pick a random insert-punctuation string, filtering by available glyphs.
fn random_insert(
    options: &[(String, f64)],
    glyphs: Option<&str>,
    rng: &mut impl Rng,
    rnd_punc: f64,
) -> Option<String> {
    let available: Vec<(&str, f64)> = options
        .iter()
        .filter(|(punc, _)| match glyphs {
            None => true,
            Some(g) => punc.chars().all(|c| c == ' ' || g.contains(c)),
        })
        .map(|(punc, prob)| (punc.as_str(), (1.0 - rnd_punc) * prob + rnd_punc))
        .collect();

    if available.is_empty() {
        return None;
    }

    let weights: Vec<f64> = available.iter().map(|(_, w)| *w).collect();
    let dist = WeightedIndex::new(&weights).ok()?;
    Some(available[dist.sample(rng)].0.to_string())
}

/// Pick a random wrap pair, filtering by available glyphs.
fn random_wrap(
    options: &[((String, String), f64)],
    glyphs: Option<&str>,
    rng: &mut impl Rng,
    rnd_punc: f64,
) -> Option<(String, String)> {
    let available: Vec<(&(String, String), f64)> = options
        .iter()
        .filter(|((left, right), _)| match glyphs {
            None => true,
            Some(g) => {
                left.chars().all(|c| c == ' ' || g.contains(c))
                    && right.chars().all(|c| c == ' ' || g.contains(c))
            }
        })
        .map(|(pair, prob)| (pair, (1.0 - rnd_punc) * prob + rnd_punc))
        .collect();

    if available.is_empty() {
        return None;
    }

    let weights: Vec<f64> = available.iter().map(|(_, w)| *w).collect();
    let dist = WeightedIndex::new(&weights).ok()?;
    Some(available[dist.sample(rng)].0.clone())
}

// ---------------------------------------------------------------------------
// Public punctuation function
// ---------------------------------------------------------------------------

/// Punctuate a list of words and join into a sentence.
pub fn punctuate(
    config: &PunctuationConfig,
    rng: &mut impl Rng,
    words: &[String],
    glyphs: Option<&str>,
    rnd_punc: f64,
) -> String {
    let insert = random_insert(&config.insert, glyphs, rng, rnd_punc).unwrap_or_default();
    let wrap_sent = random_wrap(&config.wrap_sent, glyphs, rng, rnd_punc)
        .unwrap_or_else(|| (String::new(), String::new()));
    let wrap_inner = random_wrap(&config.wrap_inner, glyphs, rng, rnd_punc)
        .unwrap_or_else(|| (String::new(), String::new()));

    let sent_body = if words.len() > 2 {
        let mut w: Vec<String> = words.to_vec();

        // Inner wrap (parentheses, quotes, …)
        let wrap_left = rng.gen_range(0..w.len() - 1);
        let wrap_right = rng.gen_range(wrap_left..w.len() - 1);
        w[wrap_left] = format!("{}{}", wrap_inner.0, w[wrap_left]);
        w[wrap_right] = format!("{}{}", w[wrap_right], wrap_inner.1);

        // Insert punctuation in place of a space
        let available_indices: Vec<usize> = (1..w.len() - 1).collect();
        let insert_index = if available_indices.is_empty() {
            0
        } else {
            *available_indices.choose(rng).unwrap()
        };

        let mut separators: Vec<&str> = vec![" "; w.len() - 1];
        if !insert.is_empty() && insert_index > 0 {
            separators[insert_index - 1] = &insert;
        }

        let mut s = String::new();
        for i in 0..w.len() - 1 {
            s.push_str(&w[i]);
            s.push_str(separators[i]);
        }
        s.push_str(&w[w.len() - 1]);
        s
    } else {
        words.join(" ")
    };

    format!("{}{}{}", wrap_sent.0, sent_body, wrap_sent.1)
}
