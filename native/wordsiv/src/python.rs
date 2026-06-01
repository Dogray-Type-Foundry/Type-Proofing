use pyo3::prelude::*;
use pyo3::types::PyDict;

use crate::engine::{GenParams, WordSiv};
use crate::errors::WordsivError;
use crate::filter::CaseType;
use crate::punctuation::PunctuationConfig;
use crate::vocab::{parse_tsv_data, Vocab};

#[cfg(feature = "shaping")]
use crate::shaping;

// ---------------------------------------------------------------------------
// Custom Python exceptions
// ---------------------------------------------------------------------------

pyo3::create_exception!(wordsiv, FilterError, pyo3::exceptions::PyException);
pyo3::create_exception!(wordsiv, VocabFormatError, pyo3::exceptions::PyException);
pyo3::create_exception!(wordsiv, VocabEmptyError, pyo3::exceptions::PyException);

impl From<WordsivError> for PyErr {
    fn from(e: WordsivError) -> PyErr {
        match e {
            WordsivError::Filter(msg) => FilterError::new_err(msg),
            WordsivError::VocabEmpty(msg) => VocabEmptyError::new_err(msg),
            WordsivError::VocabFormat(msg) => VocabFormatError::new_err(msg),
            WordsivError::Value(msg) => pyo3::exceptions::PyValueError::new_err(msg),
            WordsivError::Index(msg) => pyo3::exceptions::PyIndexError::new_err(msg),
        }
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn extract_string_or_vec(obj: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
    match obj {
        None => Ok(vec![]),
        Some(o) => {
            if o.is_none() {
                return Ok(vec![]);
            }
            if let Ok(s) = o.extract::<String>() {
                Ok(vec![s])
            } else {
                o.extract::<Vec<String>>()
            }
        }
    }
}

fn extract_punctuation(obj: &Bound<'_, PyAny>) -> PyResult<PunctuationConfig> {
    let dict: &Bound<'_, PyDict> = obj.downcast()?;

    // insert: {str: float}
    let insert_obj = dict
        .get_item("insert")?
        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("missing 'insert'"))?;
    let insert_dict: &Bound<'_, PyDict> = insert_obj.downcast()?;
    let insert: Vec<(String, f64)> = insert_dict
        .iter()
        .map(|(k, v)| Ok((k.extract::<String>()?, v.extract::<f64>()?)))
        .collect::<PyResult<_>>()?;

    // wrap_sent: {(str, str): float}
    let ws_obj = dict
        .get_item("wrap_sent")?
        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("missing 'wrap_sent'"))?;
    let ws_dict: &Bound<'_, PyDict> = ws_obj.downcast()?;
    let wrap_sent: Vec<((String, String), f64)> = ws_dict
        .iter()
        .map(|(k, v)| {
            let pair = k.extract::<(String, String)>()?;
            let w = v.extract::<f64>()?;
            Ok((pair, w))
        })
        .collect::<PyResult<_>>()?;

    // wrap_inner: {(str, str): float}
    let wi_obj = dict
        .get_item("wrap_inner")?
        .ok_or_else(|| pyo3::exceptions::PyKeyError::new_err("missing 'wrap_inner'"))?;
    let wi_dict: &Bound<'_, PyDict> = wi_obj.downcast()?;
    let wrap_inner: Vec<((String, String), f64)> = wi_dict
        .iter()
        .map(|(k, v)| {
            let pair = k.extract::<(String, String)>()?;
            let w = v.extract::<f64>()?;
            Ok((pair, w))
        })
        .collect::<PyResult<_>>()?;

    Ok(PunctuationConfig {
        insert,
        wrap_sent,
        wrap_inner,
    })
}

fn pyobj_to_json(obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        Ok(serde_json::Value::Null)
    } else if let Ok(b) = obj.extract::<bool>() {
        Ok(serde_json::Value::Bool(b))
    } else if let Ok(i) = obj.extract::<i64>() {
        Ok(serde_json::json!(i))
    } else if let Ok(f) = obj.extract::<f64>() {
        Ok(serde_json::json!(f))
    } else if let Ok(s) = obj.extract::<String>() {
        Ok(serde_json::Value::String(s))
    } else if let Ok(dict) = obj.downcast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in dict.iter() {
            let key: String = k.extract()?;
            map.insert(key, pyobj_to_json(&v)?);
        }
        Ok(serde_json::Value::Object(map))
    } else if let Ok(list) = obj.downcast::<pyo3::types::PyList>() {
        let arr: Vec<serde_json::Value> = list
            .iter()
            .map(|item| pyobj_to_json(&item))
            .collect::<PyResult<_>>()?;
        Ok(serde_json::Value::Array(arr))
    } else {
        Ok(serde_json::Value::String(obj.str()?.to_string()))
    }
}

/// Build a GenParams from common keyword arguments coming from Python methods.
fn build_gen_params(
    ws: &PyWordSiv,
    vocab: Option<String>,
    glyphs: Option<String>,
    case: &str,
    rnd: f64,
    top_k: usize,
    min_wl: usize,
    max_wl: Option<usize>,
    wl: Option<usize>,
    contains: Option<&Bound<'_, PyAny>>,
    inner: Option<&Bound<'_, PyAny>>,
    startswith: Option<String>,
    endswith: Option<String>,
    regexp: Option<String>,
    raise_errors: Option<bool>,
    n_words: Option<usize>,
    min_n_words: usize,
    max_n_words: usize,
    numbers: f64,
    cap_first: Option<bool>,
    punc: bool,
    rnd_punc: f64,
    min_n_sents: usize,
    max_n_sents: usize,
    n_sents: Option<usize>,
    sent_sep: &str,
    n_paras: usize,
    para_sep: &str,
    theme: Option<String>,
    theme_strength: f64,
    bias_chars: Option<&Bound<'_, PyAny>>,
    bias_strength: f64,
) -> PyResult<GenParams> {
    Ok(GenParams {
        glyphs: glyphs.or_else(|| ws.inner.glyphs.clone()),
        case: CaseType::from_str(case).map_err(PyErr::from)?,
        rnd,
        top_k,
        min_wl,
        max_wl,
        wl,
        contains: extract_string_or_vec(contains)?,
        inner: extract_string_or_vec(inner)?,
        startswith,
        endswith,
        regexp,
        raise_errors: raise_errors.unwrap_or(ws.inner.raise_errors),
        bias_chars: extract_string_or_vec(bias_chars)?,
        bias_strength,
        vocab: vocab.or_else(|| ws.inner.vocab_name.clone()),
        n_words,
        min_n_words,
        max_n_words,
        numbers,
        cap_first,
        punc,
        rnd_punc,
        min_n_sents,
        max_n_sents,
        n_sents,
        sent_sep: sent_sep.to_string(),
        n_paras,
        para_sep: para_sep.to_string(),
        theme,
        theme_strength,
    })
}

// ---------------------------------------------------------------------------
// PyVocab
// ---------------------------------------------------------------------------

#[pyclass(name = "Vocab")]
#[derive(Clone)]
pub struct PyVocab {
    pub(crate) inner: Vocab,
}

#[pymethods]
impl PyVocab {
    #[new]
    #[pyo3(signature = (lang, bicameral, punctuation=None, data=None, data_file=None, meta=None))]
    fn new(
        lang: String,
        bicameral: bool,
        punctuation: Option<&Bound<'_, PyAny>>,
        data: Option<String>,
        data_file: Option<String>,
        meta: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let punc_config = match punctuation {
            Some(p) => Some(extract_punctuation(p)?),
            None => None,
        };

        let meta_val = match meta {
            Some(m) => Some(pyobj_to_json(m)?),
            None => None,
        };

        let raw_data = if let Some(d) = data {
            if data_file.is_some() {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Cannot specify both 'data' and 'data_file'",
                ));
            }
            d
        } else if let Some(f) = data_file {
            std::fs::read_to_string(&f)
                .map_err(|e| VocabEmptyError::new_err(format!("Error reading file: {e}")))?
        } else {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Must specify either 'data' or 'data_file'",
            ));
        };

        let wordcount = parse_tsv_data(&raw_data).map_err(PyErr::from)?;
        let vocab = Vocab::new(lang, bicameral, wordcount, punc_config, meta_val);

        Ok(PyVocab { inner: vocab })
    }

    #[getter]
    fn lang(&self) -> &str {
        &self.inner.lang
    }

    #[getter]
    fn bicameral(&self) -> bool {
        self.inner.bicameral
    }
}

// ---------------------------------------------------------------------------
// PyWordSiv
// ---------------------------------------------------------------------------

#[pyclass(name = "WordSiv")]
pub struct PyWordSiv {
    inner: WordSiv,
}

#[pymethods]
impl PyWordSiv {
    #[new]
    #[pyo3(signature = (vocab=None, glyphs=None, add_default_vocabs=true, raise_errors=false, seed=None))]
    fn new(
        vocab: Option<String>,
        glyphs: Option<String>,
        add_default_vocabs: bool,
        raise_errors: bool,
        seed: Option<u64>,
    ) -> Self {
        PyWordSiv {
            inner: WordSiv::new(vocab, glyphs, add_default_vocabs, raise_errors, seed),
        }
    }

    fn seed(&mut self, seed: u64) {
        self.inner.seed(seed);
    }

    fn add_vocab(&mut self, vocab_name: String, vocab: &PyVocab) {
        self.inner.add_vocab(vocab_name, vocab.inner.clone());
    }

    fn list_vocabs(&self) -> Vec<String> {
        self.inner.list_vocabs()
    }

    // -- number ---------------------------------------------------------

    #[pyo3(signature = (*, seed=None, glyphs=None, wl=None, min_wl=1, max_wl=4, raise_errors=None))]
    fn number(
        &mut self,
        seed: Option<u64>,
        glyphs: Option<String>,
        wl: Option<usize>,
        min_wl: usize,
        max_wl: usize,
        raise_errors: Option<bool>,
    ) -> PyResult<String> {
        let g = glyphs.or_else(|| self.inner.glyphs.clone());
        let re = raise_errors.unwrap_or(self.inner.raise_errors);
        self.inner
            .number(seed, g.as_deref(), wl, min_wl, max_wl, re)
            .map_err(PyErr::from)
    }

    // -- word -----------------------------------------------------------

    #[pyo3(signature = (*, vocab=None, glyphs=None, seed=None, rnd=0.0,
                        case="any", top_k=0, min_wl=1, max_wl=None, wl=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, raise_errors=None,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn word(
        &mut self,
        vocab: Option<String>,
        glyphs: Option<String>,
        seed: Option<u64>,
        rnd: f64,
        case: &str,
        top_k: usize,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        raise_errors: Option<bool>,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<String> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            None, 10, 20, 0.0, None, true, 0.0, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.word(seed, &p).map_err(PyErr::from)
    }

    // -- top_word -------------------------------------------------------

    #[pyo3(signature = (*, vocab=None, glyphs=None, seed=None, idx=0,
                        case="any", min_wl=2, max_wl=None, wl=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, raise_errors=None,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn top_word(
        &mut self,
        vocab: Option<String>,
        glyphs: Option<String>,
        seed: Option<u64>,
        idx: usize,
        case: &str,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        raise_errors: Option<bool>,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<String> {
        let p = build_gen_params(
            self, vocab, glyphs, case, 0.0, 0, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            None, 10, 20, 0.0, None, true, 0.0, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.top_word(seed, idx, &p).map_err(PyErr::from)
    }

    // -- top_words ------------------------------------------------------

    #[pyo3(signature = (*, glyphs=None, vocab=None, n_words=10, idx=0,
                        case="any", min_wl=1, max_wl=None, wl=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, raise_errors=None,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn top_words(
        &mut self,
        glyphs: Option<String>,
        vocab: Option<String>,
        n_words: usize,
        idx: usize,
        case: &str,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        raise_errors: Option<bool>,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<Vec<String>> {
        let p = build_gen_params(
            self, vocab, glyphs, case, 0.0, 0, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            None, 10, 20, 0.0, None, true, 0.0, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.top_words(n_words, idx, &p).map_err(PyErr::from)
    }

    // -- words ----------------------------------------------------------

    #[pyo3(signature = (*, vocab=None, glyphs=None, seed=None,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn words(
        &mut self,
        vocab: Option<String>,
        glyphs: Option<String>,
        seed: Option<u64>,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<Vec<String>> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            true, 0.0, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.words(seed, &p).map_err(PyErr::from)
    }

    // -- sent -----------------------------------------------------------

    #[pyo3(signature = (*, vocab=None, glyphs=None, seed=None, punc=true, rnd_punc=0.0,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn sent(
        &mut self,
        vocab: Option<String>,
        glyphs: Option<String>,
        seed: Option<u64>,
        punc: bool,
        rnd_punc: f64,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<String> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            punc, rnd_punc, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.sent(seed, &p).map_err(PyErr::from)
    }

    // -- sents ----------------------------------------------------------

    #[pyo3(signature = (*, seed=None, min_n_sents=3, max_n_sents=5, n_sents=None,
                        vocab=None, glyphs=None, punc=true, rnd_punc=0.0,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn sents(
        &mut self,
        seed: Option<u64>,
        min_n_sents: usize,
        max_n_sents: usize,
        n_sents: Option<usize>,
        vocab: Option<String>,
        glyphs: Option<String>,
        punc: bool,
        rnd_punc: f64,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<Vec<String>> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            punc, rnd_punc, min_n_sents, max_n_sents, n_sents, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.sents(seed, &p).map_err(PyErr::from)
    }

    // -- para -----------------------------------------------------------

    #[pyo3(signature = (*, seed=None, sent_sep=" ",
                        min_n_sents=3, max_n_sents=5, n_sents=None,
                        vocab=None, glyphs=None, punc=true, rnd_punc=0.0,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn para(
        &mut self,
        seed: Option<u64>,
        sent_sep: &str,
        min_n_sents: usize,
        max_n_sents: usize,
        n_sents: Option<usize>,
        vocab: Option<String>,
        glyphs: Option<String>,
        punc: bool,
        rnd_punc: f64,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<String> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            punc, rnd_punc, min_n_sents, max_n_sents, n_sents, sent_sep, 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.para(seed, &p).map_err(PyErr::from)
    }

    // -- paras ----------------------------------------------------------

    #[pyo3(signature = (*, seed=None, n_paras=3, sent_sep=" ",
                        min_n_sents=3, max_n_sents=5, n_sents=None,
                        vocab=None, glyphs=None, punc=true, rnd_punc=0.0,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn paras(
        &mut self,
        seed: Option<u64>,
        n_paras: usize,
        sent_sep: &str,
        min_n_sents: usize,
        max_n_sents: usize,
        n_sents: Option<usize>,
        vocab: Option<String>,
        glyphs: Option<String>,
        punc: bool,
        rnd_punc: f64,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<Vec<String>> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            punc, rnd_punc, min_n_sents, max_n_sents, n_sents, sent_sep, n_paras, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.paras(seed, &p).map_err(PyErr::from)
    }

    // -- text -----------------------------------------------------------

    #[pyo3(signature = (*, seed=None, para_sep="\n\n", n_paras=3, sent_sep=" ",
                        min_n_sents=3, max_n_sents=5, n_sents=None,
                        vocab=None, glyphs=None, punc=true, rnd_punc=0.0,
                        n_words=None, min_n_words=10, max_n_words=20, numbers=0.0,
                        cap_first=None, case="any", rnd=0.0,
                        min_wl=1, max_wl=None, wl=None, raise_errors=None,
                        contains=None, inner=None, startswith=None, endswith=None,
                        regexp=None, top_k=0,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn text(
        &mut self,
        seed: Option<u64>,
        para_sep: &str,
        n_paras: usize,
        sent_sep: &str,
        min_n_sents: usize,
        max_n_sents: usize,
        n_sents: Option<usize>,
        vocab: Option<String>,
        glyphs: Option<String>,
        punc: bool,
        rnd_punc: f64,
        n_words: Option<usize>,
        min_n_words: usize,
        max_n_words: usize,
        numbers: f64,
        cap_first: Option<bool>,
        case: &str,
        rnd: f64,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        raise_errors: Option<bool>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        top_k: usize,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<String> {
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl, contains, inner,
            startswith, endswith, regexp, raise_errors,
            n_words, min_n_words, max_n_words, numbers, cap_first,
            punc, rnd_punc, min_n_sents, max_n_sents, n_sents, sent_sep, n_paras, para_sep,
            theme, theme_strength, bias_chars, bias_strength,
        )?;
        self.inner.text(seed, &p).map_err(PyErr::from)
    }

    // -- same_width_words -----------------------------------------------

    /// Find words (and optionally phrases) whose advance width when set in
    /// the given font matches `target_width` (in font design units) within
    /// `tolerance`.
    #[cfg(feature = "shaping")]
    #[pyo3(signature = (*, font_path, target_width, n=10, tolerance=10,
                        features=None, variations=None, phrases=true,
                        max_retries=5, fast_measure=None,
                        vocab=None, glyphs=None, case="any", rnd=0.0,
                        top_k=0, min_wl=1, max_wl=None, wl=None,
                        contains=None, inner=None, startswith=None,
                        endswith=None, regexp=None, raise_errors=None,
                        theme=None, theme_strength=0.5,
                        bias_chars=None, bias_strength=0.0))]
    #[allow(clippy::too_many_arguments)]
    fn same_width_words(
        &mut self,
        font_path: String,
        target_width: i32,
        n: usize,
        tolerance: i32,
        features: Option<Vec<String>>,
        variations: Option<&Bound<'_, PyDict>>,
        phrases: bool,
        max_retries: usize,
        fast_measure: Option<bool>,
        vocab: Option<String>,
        glyphs: Option<String>,
        case: &str,
        rnd: f64,
        top_k: usize,
        min_wl: usize,
        max_wl: Option<usize>,
        wl: Option<usize>,
        contains: Option<&Bound<'_, PyAny>>,
        inner: Option<&Bound<'_, PyAny>>,
        startswith: Option<String>,
        endswith: Option<String>,
        regexp: Option<String>,
        raise_errors: Option<bool>,
        theme: Option<String>,
        theme_strength: f64,
        bias_chars: Option<&Bound<'_, PyAny>>,
        bias_strength: f64,
    ) -> PyResult<Vec<String>> {
        // Read font file
        let font_data = std::fs::read(&font_path).map_err(|e| {
            pyo3::exceptions::PyIOError::new_err(format!(
                "Failed to read font file '{}': {}",
                font_path, e
            ))
        })?;

        // Convert features
        let hb_features = match features {
            Some(ref tags) => shaping::features_from_strings(tags),
            None => vec![],
        };

        // Convert variations
        let variation_pairs: Vec<(String, f32)> = match variations {
            Some(dict) => dict
                .iter()
                .map(|(k, v)| {
                    let tag: String = k.extract()?;
                    let val: f32 = v.extract()?;
                    Ok((tag, val))
                })
                .collect::<PyResult<_>>()?,
            None => vec![],
        };
        let hb_variations = shaping::variations_from_pairs(&variation_pairs);

        // Build GenParams (reuse existing helper)
        let p = build_gen_params(
            self, vocab, glyphs, case, rnd, top_k, min_wl, max_wl, wl,
            contains, inner, startswith, endswith, regexp, raise_errors,
            None, 10, 20, 0.0, None, true, 0.0, 3, 5, None, " ", 3, "\n\n",
            theme, theme_strength, bias_chars, bias_strength,
        )?;

        self.inner
            .same_width_words(
                &font_data,
                target_width,
                n,
                tolerance,
                &hb_features,
                &hb_variations,
                phrases,
                max_retries,
                fast_measure,
                &p,
            )
            .map_err(PyErr::from)
    }


    // -- semantic embeddings --------------------------------------------

    /// Download word embeddings for semantic theme support.
    /// Currently only "en" (English) is supported.
    #[cfg(feature = "semantic")]
    #[staticmethod]
    #[pyo3(signature = (lang=None))]
    fn download_embeddings(lang: Option<String>) -> PyResult<String> {
        let lang = lang.as_deref().unwrap_or("en");
        crate::semantic::download_embeddings(lang)
            .map(|p| p.to_string_lossy().into_owned())
            .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e.to_string()))
    }

    /// Check whether word embeddings are available locally for the given
    /// language.  Returns the path to the binary file if found, or None.
    #[cfg(feature = "semantic")]
    #[staticmethod]
    #[pyo3(signature = (lang=None))]
    fn has_embeddings(lang: Option<String>) -> Option<String> {
        let lang = lang.as_deref().unwrap_or("en");
        let dir = dirs::data_dir()
            .unwrap_or_else(|| std::path::PathBuf::from("."))
            .join("wordsiv");
        let path = dir.join(format!("{}_glove_100d.bin", lang));
        if path.exists() {
            Some(path.to_string_lossy().into_owned())
        } else {
            None
        }
    }

    // -- clear_shaping_cache --------------------------------------------

    /// Clear the global shaping cache to free memory.
    #[cfg(feature = "shaping")]
    #[staticmethod]
    fn clear_shaping_cache() {
        shaping::clear_shaping_cache();
    }
}

// ---------------------------------------------------------------------------
// Module registration
// ---------------------------------------------------------------------------

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyWordSiv>()?;
    m.add_class::<PyVocab>()?;
    m.add("FilterError", m.py().get_type_bound::<FilterError>())?;
    m.add("VocabFormatError", m.py().get_type_bound::<VocabFormatError>())?;
    m.add("VocabEmptyError", m.py().get_type_bound::<VocabEmptyError>())?;
    Ok(())
}
