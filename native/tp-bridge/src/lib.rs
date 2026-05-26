use std::ffi::{c_char, CStr, CString};
use std::ptr;

use wordsiv::engine::{GenParams, WordSiv};
use wordsiv::filter::CaseType;

// ---------------------------------------------------------------------------
// WordSiv lifecycle
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn wsv_create(seed: u64) -> *mut WordSiv {
    let wsv = WordSiv::new(None, None, true, false, Some(seed));
    Box::into_raw(Box::new(wsv))
}

#[no_mangle]
pub unsafe extern "C" fn wsv_free(ptr: *mut WordSiv) {
    if !ptr.is_null() {
        drop(Box::from_raw(ptr));
    }
}

#[no_mangle]
pub unsafe extern "C" fn wsv_free_string(ptr: *mut c_char) {
    if !ptr.is_null() {
        drop(CString::from_raw(ptr));
    }
}

// ---------------------------------------------------------------------------
// WordSiv text generation
// ---------------------------------------------------------------------------

#[no_mangle]
pub unsafe extern "C" fn wsv_text(
    ptr: *mut WordSiv,
    glyphs: *const c_char,
    n_paras: u32,
    numbers: f64,
    rnd_punc: f64,
    para_sep: *const c_char,
    vocab: *const c_char,
) -> *mut c_char {
    let wsv = &mut *ptr;
    let params = GenParams {
        glyphs: c_str_to_option(glyphs),
        vocab: c_str_to_option(vocab),
        n_paras: n_paras as usize,
        numbers,
        rnd_punc,
        para_sep: c_str_to_string(para_sep, " "),
        ..Default::default()
    };
    match wsv.text(None, &params) {
        Ok(s) => string_to_c(s),
        Err(_) => ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn wsv_words(
    ptr: *mut WordSiv,
    glyphs: *const c_char,
    case_str: *const c_char,
    contains: *const c_char,
    n_words: u32,
    min_wl: u32,
    max_wl: u32,
    vocab: *const c_char,
    startswith: *const c_char,
    endswith: *const c_char,
    inner: *const c_char,
) -> *mut c_char {
    let wsv = &mut *ptr;
    let case = if case_str.is_null() {
        CaseType::Any
    } else {
        let s = CStr::from_ptr(case_str).to_str().unwrap_or("any");
        CaseType::from_str(s).unwrap_or(CaseType::Any)
    };
    let contains_vec = if contains.is_null() {
        vec![]
    } else {
        let s = CStr::from_ptr(contains).to_str().unwrap_or("");
        if s.is_empty() { vec![] } else { vec![s.to_string()] }
    };
    let inner_vec = if inner.is_null() {
        vec![]
    } else {
        let s = CStr::from_ptr(inner).to_str().unwrap_or("");
        if s.is_empty() { vec![] } else { vec![s.to_string()] }
    };
    let params = GenParams {
        glyphs: c_str_to_option(glyphs),
        vocab: c_str_to_option(vocab),
        case,
        contains: contains_vec,
        inner: inner_vec,
        startswith: c_str_to_option(startswith),
        endswith: c_str_to_option(endswith),
        n_words: Some(n_words as usize),
        min_wl: min_wl as usize,
        max_wl: if max_wl > 0 { Some(max_wl as usize) } else { None },
        ..Default::default()
    };
    match wsv.words(None, &params) {
        Ok(words) => string_to_c(words.join(" ")),
        Err(_) => ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn wsv_top_word(
    ptr: *mut WordSiv,
    glyphs: *const c_char,
    case_str: *const c_char,
    regexp: *const c_char,
    idx: u32,
    min_wl: u32,
    vocab: *const c_char,
) -> *mut c_char {
    let wsv = &mut *ptr;
    let case = if case_str.is_null() {
        CaseType::Any
    } else {
        let s = CStr::from_ptr(case_str).to_str().unwrap_or("any");
        CaseType::from_str(s).unwrap_or(CaseType::Any)
    };
    let params = GenParams {
        glyphs: c_str_to_option(glyphs),
        vocab: c_str_to_option(vocab),
        case,
        regexp: c_str_to_option(regexp),
        min_wl: min_wl as usize,
        ..Default::default()
    };
    match wsv.top_word(None, idx as usize, &params) {
        Ok(s) => string_to_c(s),
        Err(_) => ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn wsv_seed(ptr: *mut WordSiv, seed: u64) {
    let wsv = &mut *ptr;
    wsv.seed(seed);
}

// ---------------------------------------------------------------------------
// Font analysis
// ---------------------------------------------------------------------------

#[repr(C)]
pub struct TPFontInfo {
    pub family_name: *mut c_char,
    pub subfamily_name: *mut c_char,
    pub weight: u16,
    pub width: u16,
    pub fs_selection: u16,
    pub is_variable: bool,
    pub slant: f64,
    pub optical_size: f64,
    pub axes_json: *mut c_char,
    pub features_json: *mut c_char,
}

#[no_mangle]
pub unsafe extern "C" fn tp_load_font(data: *const u8, len: usize) -> *mut TPFontInfo {
    let slice = std::slice::from_raw_parts(data, len);
    let info = match tp_fonts::font_info::load_font_info(slice) {
        Some(i) => i,
        None => return ptr::null_mut(),
    };

    let axes_json = serde_axes_json(&info);
    let features_json = serde_features_json(&info);

    let result = Box::new(TPFontInfo {
        family_name: string_to_c(info.family_name),
        subfamily_name: string_to_c(info.subfamily_name),
        weight: info.weight,
        width: info.width,
        fs_selection: info.fs_selection,
        is_variable: info.is_variable,
        slant: info.slant,
        optical_size: info.optical_size,
        axes_json: string_to_c(axes_json),
        features_json: string_to_c(features_json),
    });
    Box::into_raw(result)
}

#[no_mangle]
pub unsafe extern "C" fn tp_free_font_info(ptr: *mut TPFontInfo) {
    if ptr.is_null() { return; }
    let info = Box::from_raw(ptr);
    free_c_str(info.family_name);
    free_c_str(info.subfamily_name);
    free_c_str(info.axes_json);
    free_c_str(info.features_json);
}

#[no_mangle]
pub unsafe extern "C" fn tp_get_charset(data: *const u8, len: usize) -> *mut c_char {
    let slice = std::slice::from_raw_parts(data, len);
    string_to_c(tp_fonts::charset::filtered_charset(slice))
}

#[no_mangle]
pub unsafe extern "C" fn tp_get_axes_json(data: *const u8, len: usize) -> *mut c_char {
    let slice = std::slice::from_raw_parts(data, len);
    match tp_fonts::axes::get_generation_axes(slice) {
        Some(axes) => {
            let json = axes.iter().map(|a| {
                let tag = std::str::from_utf8(&a.tag).unwrap_or("????");
                let vals: Vec<String> = a.values.iter().map(|v| format!("{}", v)).collect();
                format!("{{\"tag\":\"{}\",\"values\":[{}]}}", tag, vals.join(","))
            }).collect::<Vec<_>>().join(",");
            string_to_c(format!("[{}]", json))
        }
        None => ptr::null_mut(),
    }
}

#[no_mangle]
pub unsafe extern "C" fn tp_get_substitutions_json(data: *const u8, len: usize) -> *mut c_char {
    let slice = std::slice::from_raw_parts(data, len);
    let subs = tp_fonts::substitutions::get_font_substitutions(slice);
    if subs.is_empty() {
        return ptr::null_mut();
    }

    let features: Vec<String> = subs.iter().map(|f| {
        let entries: Vec<String> = f.entries.iter().map(|e| {
            let input: Vec<String> = e.input_glyphs.iter().map(|g| g.to_string()).collect();
            let output: Vec<String> = e.output_glyphs.iter().map(|g| g.to_string()).collect();
            let out_names: Vec<String> = e.output_glyph_names.iter()
                .map(|n| format!("\"{}\"", n.replace('\\', "\\\\").replace('"', "\\\"")))
                .collect();
            format!(
                "{{\"kind\":\"{}\",\"input\":[{}],\"output\":[{}],\"input_text\":\"{}\",\"output_names\":[{}],\"backtrack_text\":\"{}\",\"lookahead_text\":\"{}\"}}",
                e.kind,
                input.join(","),
                output.join(","),
                e.input_text.replace('\\', "\\\\").replace('"', "\\\""),
                out_names.join(","),
                e.backtrack_text.replace('\\', "\\\\").replace('"', "\\\""),
                e.lookahead_text.replace('\\', "\\\\").replace('"', "\\\""),
            )
        }).collect();
        let out_glyphs: Vec<String> = f.output_glyphs.iter()
            .map(|n| format!("\"{}\"", n.replace('\\', "\\\\").replace('"', "\\\"")))
            .collect();
        format!(
            "{{\"tag\":\"{}\",\"entries\":[{}],\"output_glyphs\":[{}]}}",
            f.feature_tag,
            entries.join(","),
            out_glyphs.join(","),
        )
    }).collect();
    string_to_c(format!("[{}]", features.join(",")))
}

// ---------------------------------------------------------------------------
// Version
// ---------------------------------------------------------------------------

#[no_mangle]
pub extern "C" fn tp_version() -> *const c_char {
    static VERSION: &[u8] = b"0.1.0\0";
    VERSION.as_ptr() as *const c_char
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

unsafe fn c_str_to_option(ptr: *const c_char) -> Option<String> {
    if ptr.is_null() {
        None
    } else {
        Some(CStr::from_ptr(ptr).to_str().unwrap_or("").to_string())
    }
}

fn c_str_to_string(ptr: *const c_char, default: &str) -> String {
    if ptr.is_null() {
        default.to_string()
    } else {
        unsafe { CStr::from_ptr(ptr).to_str().unwrap_or(default).to_string() }
    }
}

fn string_to_c(s: String) -> *mut c_char {
    CString::new(s).map(|c| c.into_raw()).unwrap_or(ptr::null_mut())
}

unsafe fn free_c_str(ptr: *mut c_char) {
    if !ptr.is_null() {
        drop(CString::from_raw(ptr));
    }
}

fn serde_axes_json(info: &tp_fonts::font_info::FontInfo) -> String {
    let items: Vec<String> = info.axes.iter().map(|a| {
        let tag = std::str::from_utf8(&a.tag).unwrap_or("????");
        format!(
            "{{\"tag\":\"{}\",\"min\":{},\"default\":{},\"max\":{}}}",
            tag, a.min, a.default, a.max
        )
    }).collect();
    format!("[{}]", items.join(","))
}

fn serde_features_json(info: &tp_fonts::font_info::FontInfo) -> String {
    let items: Vec<String> = info.features.iter()
        .map(|f| format!("\"{}\"", f))
        .collect();
    format!("[{}]", items.join(","))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wsv_text_generation() {
        let wsv = wsv_create(987654);
        assert!(!wsv.is_null());

        unsafe {
            let glyphs = CString::new("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,;:!?-").unwrap();
            let sep = CString::new(" ").unwrap();
            let en = CString::new("en").unwrap();
            let result = wsv_text(wsv, glyphs.as_ptr(), 2, 0.0, 0.0, sep.as_ptr(), en.as_ptr());
            assert!(!result.is_null());
            let text = CStr::from_ptr(result).to_str().unwrap();
            assert!(!text.is_empty());
            eprintln!("generated text ({} chars): {}...", text.len(), &text[..text.len().min(100)]);
            wsv_free_string(result);

            wsv_free(wsv);
        }
    }

    #[test]
    fn test_wsv_words() {
        let wsv = wsv_create(987654);
        unsafe {
            let glyphs = CString::new("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz").unwrap();
            let case = CString::new("cap").unwrap();
            let en = CString::new("en").unwrap();
            let result = wsv_words(wsv, glyphs.as_ptr(), case.as_ptr(), ptr::null(), 3, 5, 14, en.as_ptr(), ptr::null(), ptr::null(), ptr::null());
            assert!(!result.is_null());
            let words = CStr::from_ptr(result).to_str().unwrap();
            assert!(!words.is_empty());
            eprintln!("words: {}", words);
            wsv_free_string(result);
            wsv_free(wsv);
        }
    }

    #[test]
    fn test_font_info_roundtrip() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        unsafe {
            let info = tp_load_font(data.as_ptr(), data.len());
            assert!(!info.is_null());
            let family = CStr::from_ptr((*info).family_name).to_str().unwrap();
            assert!(family.contains("Sets Grotesk"), "family: {}", family);
            assert!((*info).is_variable);
            tp_free_font_info(info);
        }
    }

    #[test]
    fn test_charset_ffi() {
        let data = std::fs::read("../../SetsGroteskVF.ttf").expect("font file");
        unsafe {
            let result = tp_get_charset(data.as_ptr(), data.len());
            assert!(!result.is_null());
            let charset = CStr::from_ptr(result).to_str().unwrap();
            assert!(charset.contains('A'));
            assert_eq!(charset.chars().count(), 475);
            wsv_free_string(result);
        }
    }

    #[test]
    fn bench_wordsiv_speed() {
        use std::time::Instant;
        const ITERS: u32 = 200;

        let wsv = wsv_create(42);
        unsafe {
            let latin = CString::new("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,;:!?-'\"()").unwrap();
            let small = CString::new("abcdefghn").unwrap();
            let sep = CString::new("\n").unwrap();
            let en = CString::new("en").unwrap();
            let cap = CString::new("cap").unwrap();

            // Warm up
            let r = wsv_text(wsv, latin.as_ptr(), 1, 0.0, 0.0, sep.as_ptr(), en.as_ptr());
            wsv_free_string(r);

            // Bench: text generation (full charset)
            let t0 = Instant::now();
            for _ in 0..ITERS {
                let r = wsv_text(wsv, latin.as_ptr(), 3, 0.1, 0.05, sep.as_ptr(), en.as_ptr());
                wsv_free_string(r);
            }
            let text_full = t0.elapsed();

            // Bench: text generation (restricted charset)
            let t0 = Instant::now();
            for _ in 0..ITERS {
                let r = wsv_text(wsv, small.as_ptr(), 3, 0.0, 0.0, sep.as_ptr(), en.as_ptr());
                wsv_free_string(r);
            }
            let text_small = t0.elapsed();

            // Bench: word filtering
            let t0 = Instant::now();
            for _ in 0..ITERS {
                let r = wsv_words(wsv, latin.as_ptr(), cap.as_ptr(), ptr::null(), 10, 4, 12, en.as_ptr(), ptr::null(), ptr::null(), ptr::null());
                wsv_free_string(r);
            }
            let words_full = t0.elapsed();

            // Bench: word filtering (restricted charset)
            let t0 = Instant::now();
            for _ in 0..ITERS {
                let r = wsv_words(wsv, small.as_ptr(), ptr::null(), ptr::null(), 10, 3, 8, en.as_ptr(), ptr::null(), ptr::null(), ptr::null());
                wsv_free_string(r);
            }
            let words_small = t0.elapsed();

            // Bench: top_word
            let t0 = Instant::now();
            for _ in 0..ITERS {
                let r = wsv_top_word(wsv, latin.as_ptr(), cap.as_ptr(), ptr::null(), 0, 4, en.as_ptr());
                wsv_free_string(r);
            }
            let top_full = t0.elapsed();

            wsv_free(wsv);

            eprintln!("\n=== wordsiv bitmask benchmark ({} iterations) ===", ITERS);
            eprintln!("text (full charset):      {:>8.2?} total, {:>8.2?}/call", text_full, text_full / ITERS);
            eprintln!("text (small charset):     {:>8.2?} total, {:>8.2?}/call", text_small, text_small / ITERS);
            eprintln!("words (full charset):     {:>8.2?} total, {:>8.2?}/call", words_full, words_full / ITERS);
            eprintln!("words (small charset):    {:>8.2?} total, {:>8.2?}/call", words_small, words_small / ITERS);
            eprintln!("top_word (full charset):  {:>8.2?} total, {:>8.2?}/call", top_full, top_full / ITERS);
        }
    }
}
