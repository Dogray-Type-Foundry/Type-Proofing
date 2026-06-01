//! Semantic word embeddings for theme-based word selection.
//!
//! Uses pre-trained GloVe embeddings stored in a compact binary format.
//! The binary file is memory-mapped at runtime for zero-copy, instant loading.
//!
//! ## Binary format (version 1)
//!
//! ```text
//! [magic: 4 bytes "WSEM"]
//! [version: u8 = 1]
//! [dim: u16 LE]          — embedding dimension (e.g. 100)
//! [word_count: u32 LE]   — number of words
//! -- for each word: --
//! [word_len: u16 LE]
//! [word_bytes: word_len bytes, UTF-8]
//! [vector: dim × f32 LE]
//! ```

use std::collections::HashMap;
use std::io::{self, BufRead, BufWriter, Write};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use crate::errors::WordsivError;

const MAGIC: &[u8; 4] = b"WSEM";
const FORMAT_VERSION: u8 = 1;

// ---------------------------------------------------------------------------
// EmbeddingStore — memory-mapped embedding file with word → vector lookup
// ---------------------------------------------------------------------------

/// A memory-mapped store of word embeddings with O(1) word lookup.
pub struct EmbeddingStore {
    /// Raw mmap data.
    _mmap: memmap2::Mmap,
    /// Embedding dimension.
    dim: usize,
    /// Word → (offset into vectors, index) for fast lookup.
    index: HashMap<String, usize>,
    /// All vectors laid out contiguously: vectors[i * dim .. (i+1) * dim].
    vectors: Vec<f32>,
}

impl EmbeddingStore {
    /// Open an embedding binary file and build the in-memory index.
    pub fn open(path: &Path) -> Result<Self, WordsivError> {
        let file = std::fs::File::open(path).map_err(|e| {
            WordsivError::Value(format!("Failed to open embedding file '{}': {}", path.display(), e))
        })?;
        let mmap = unsafe {
            memmap2::Mmap::map(&file).map_err(|e| {
                WordsivError::Value(format!("Failed to mmap embedding file: {}", e))
            })?
        };

        Self::from_mmap(mmap)
    }

    /// Parse the binary format from an mmap.
    fn from_mmap(mmap: memmap2::Mmap) -> Result<Self, WordsivError> {
        let data = &mmap[..];
        let mut pos = 0;

        // Magic
        if data.len() < 4 || &data[0..4] != MAGIC {
            return Err(WordsivError::Value("Invalid embedding file: bad magic".into()));
        }
        pos += 4;

        // Version
        if data[pos] != FORMAT_VERSION {
            return Err(WordsivError::Value(format!(
                "Unsupported embedding format version: {}",
                data[pos]
            )));
        }
        pos += 1;

        // Dimension
        if pos + 2 > data.len() {
            return Err(WordsivError::Value("Truncated embedding file (dim)".into()));
        }
        let dim = u16::from_le_bytes([data[pos], data[pos + 1]]) as usize;
        pos += 2;

        // Word count
        if pos + 4 > data.len() {
            return Err(WordsivError::Value("Truncated embedding file (word_count)".into()));
        }
        let word_count = u32::from_le_bytes([
            data[pos], data[pos + 1], data[pos + 2], data[pos + 3],
        ]) as usize;
        pos += 4;

        let vec_bytes = dim * 4; // dim × f32
        let mut index = HashMap::with_capacity(word_count);
        let mut vectors = Vec::with_capacity(word_count * dim);

        for i in 0..word_count {
            // Word length
            if pos + 2 > data.len() {
                return Err(WordsivError::Value(format!(
                    "Truncated embedding file at word {}",
                    i
                )));
            }
            let word_len = u16::from_le_bytes([data[pos], data[pos + 1]]) as usize;
            pos += 2;

            // Word bytes
            if pos + word_len > data.len() {
                return Err(WordsivError::Value(format!(
                    "Truncated embedding file at word {} bytes",
                    i
                )));
            }
            let word = std::str::from_utf8(&data[pos..pos + word_len])
                .map_err(|_| WordsivError::Value(format!("Invalid UTF-8 at word {}", i)))?
                .to_string();
            pos += word_len;

            // Vector
            if pos + vec_bytes > data.len() {
                return Err(WordsivError::Value(format!(
                    "Truncated embedding file at word {} vector",
                    i
                )));
            }
            for j in 0..dim {
                let off = pos + j * 4;
                let val = f32::from_le_bytes([
                    data[off], data[off + 1], data[off + 2], data[off + 3],
                ]);
                vectors.push(val);
            }
            pos += vec_bytes;

            index.insert(word, i);
        }

        Ok(EmbeddingStore {
            _mmap: mmap,
            dim,
            index,
            vectors,
        })
    }

    /// Look up the embedding vector for a word. Returns None if not found.
    pub fn get(&self, word: &str) -> Option<&[f32]> {
        self.index.get(word).map(|&i| {
            let start = i * self.dim;
            &self.vectors[start..start + self.dim]
        })
    }

    /// Embedding dimension.
    pub fn dim(&self) -> usize {
        self.dim
    }

    /// Number of words in the store.
    pub fn word_count(&self) -> usize {
        self.index.len()
    }
}

// ---------------------------------------------------------------------------
// Cosine similarity scoring
// ---------------------------------------------------------------------------

/// Compute cosine similarity between two vectors of the same length.
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    debug_assert_eq!(a.len(), b.len());
    let mut dot = 0.0f32;
    let mut norm_a = 0.0f32;
    let mut norm_b = 0.0f32;
    for i in 0..a.len() {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }
    let denom = norm_a.sqrt() * norm_b.sqrt();
    if denom == 0.0 {
        0.0
    } else {
        dot / denom
    }
}

/// Build a query vector from a theme string by averaging the embeddings of
/// its whitespace-separated tokens. Tokens not found in the store are skipped.
pub fn theme_vector(store: &EmbeddingStore, theme: &str) -> Option<Vec<f32>> {
    let dim = store.dim();
    let mut avg = vec![0.0f32; dim];
    let mut count = 0usize;

    for token in theme.split_whitespace() {
        let lower = token.to_lowercase();
        if let Some(vec) = store.get(&lower) {
            for (i, v) in vec.iter().enumerate() {
                avg[i] += v;
            }
            count += 1;
        }
    }

    if count == 0 {
        return None;
    }

    let scale = 1.0 / count as f32;
    for v in &mut avg {
        *v *= scale;
    }
    Some(avg)
}

/// Score a list of words against a theme vector. Returns words sorted by
/// descending cosine similarity, with their scores.
pub fn score_words(
    store: &EmbeddingStore,
    query_vec: &[f32],
    words: &[String],
) -> Vec<(String, f32)> {
    let mut scored: Vec<(String, f32)> = words
        .iter()
        .map(|w| {
            let lower = w.to_lowercase();
            let sim = store
                .get(&lower)
                .map(|v| cosine_similarity(query_vec, v))
                .unwrap_or(0.0);
            (w.clone(), sim)
        })
        .collect();
    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    scored
}

/// Filter a word list to keep only the top fraction based on theme_strength.
///
/// - `theme_strength = 0.0` → keep 100 % of words (no filtering)
/// - `theme_strength = 0.5` → keep ~50 % of words
/// - `theme_strength = 1.0` → keep ~10 % of words
///
/// Returns the filtered list of (word, count) pairs preserving original counts.
pub fn filter_by_theme(
    store: &EmbeddingStore,
    theme: &str,
    theme_strength: f64,
    word_counts: &[(String, u64)],
) -> Vec<(String, u64)> {
    if theme.trim().is_empty() || theme_strength <= 0.0 {
        return word_counts.to_vec();
    }

    let query_vec = match theme_vector(store, theme) {
        Some(v) => v,
        None => return word_counts.to_vec(), // no tokens found in embeddings
    };

    // Exponential curve: strength 0 → keep 100%, 0.5 → 10%, 1.0 → 1%
    let strength = theme_strength.clamp(0.0, 1.0);
    let keep_fraction = 10.0_f64.powf(-2.0 * strength);
    let keep_n = ((word_counts.len() as f64) * keep_fraction).ceil().max(1.0) as usize;

    // Score all words
    let words_only: Vec<String> = word_counts.iter().map(|(w, _)| w.clone()).collect();
    let scored = score_words(store, &query_vec, &words_only);

    // Build a set of the top-N words
    let top_set: std::collections::HashSet<&str> = scored
        .iter()
        .take(keep_n)
        .map(|(w, _)| w.as_str())
        .collect();

    // Filter original list preserving order and counts
    word_counts
        .iter()
        .filter(|(w, _)| top_set.contains(w.as_str()))
        .cloned()
        .collect()
}

/// Score a text string (possibly multi-word) against a query vector.
/// Averages the cosine similarities of individual whitespace-separated tokens.
/// Tokens not in the embedding store contribute 0.
pub fn score_text(store: &EmbeddingStore, query_vec: &[f32], text: &str) -> f32 {
    let tokens: Vec<&str> = text.split_whitespace().collect();
    if tokens.is_empty() {
        return 0.0;
    }
    let total: f32 = tokens
        .iter()
        .map(|t| {
            let lower = t.to_lowercase();
            store
                .get(&lower)
                .map(|v| cosine_similarity(query_vec, v))
                .unwrap_or(0.0)
        })
        .sum();
    total / tokens.len() as f32
}

// ---------------------------------------------------------------------------
// GloVe text → binary converter
// ---------------------------------------------------------------------------

/// Convert a GloVe text file to our binary format.
///
/// The GloVe text format is: `word val1 val2 ... valN\n`
/// One word per line, space-separated, N = dimension.
pub fn convert_glove_text_to_binary(
    text_path: &Path,
    output_path: &Path,
) -> Result<(), WordsivError> {
    // First pass: detect dimension from first line, count words
    let mut dim: Option<usize> = None;
    let mut word_count = 0u32;
    {
        let file2 = std::fs::File::open(text_path).map_err(|e| {
            WordsivError::Value(format!("Failed to re-open GloVe file: {}", e))
        })?;
        let reader2 = io::BufReader::new(file2);
        for line in reader2.lines() {
            let line = line.map_err(|e| {
                WordsivError::Value(format!("Error reading GloVe file: {}", e))
            })?;
            if dim.is_none() {
                let parts: Vec<&str> = line.split_whitespace().collect();
                if parts.len() < 2 {
                    continue;
                }
                dim = Some(parts.len() - 1);
            }
            word_count += 1;
        }
    }

    let dim = dim.ok_or_else(|| {
        WordsivError::Value("GloVe file is empty or has no valid lines".into())
    })?;

    // Create output directory if needed
    if let Some(parent) = output_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| {
            WordsivError::Value(format!("Failed to create directory: {}", e))
        })?;
    }

    // Second pass: write binary
    let outfile = std::fs::File::create(output_path).map_err(|e| {
        WordsivError::Value(format!(
            "Failed to create binary file '{}': {}",
            output_path.display(),
            e
        ))
    })?;
    let mut writer = BufWriter::new(outfile);

    // Header
    writer.write_all(MAGIC).map_err(write_err)?;
    writer.write_all(&[FORMAT_VERSION]).map_err(write_err)?;
    writer.write_all(&(dim as u16).to_le_bytes()).map_err(write_err)?;
    writer.write_all(&word_count.to_le_bytes()).map_err(write_err)?;

    // Re-read and write entries
    let file3 = std::fs::File::open(text_path).map_err(|e| {
        WordsivError::Value(format!("Failed to re-open GloVe file: {}", e))
    })?;
    let reader3 = io::BufReader::new(file3);

    for line in reader3.lines() {
        let line = line.map_err(|e| {
            WordsivError::Value(format!("Error reading GloVe file: {}", e))
        })?;
        let mut parts = line.split_whitespace();
        let word = match parts.next() {
            Some(w) => w,
            None => continue,
        };
        let word_bytes = word.as_bytes();
        writer
            .write_all(&(word_bytes.len() as u16).to_le_bytes())
            .map_err(write_err)?;
        writer.write_all(word_bytes).map_err(write_err)?;

        for _ in 0..dim {
            let val: f32 = parts
                .next()
                .and_then(|s| s.parse().ok())
                .unwrap_or(0.0);
            writer.write_all(&val.to_le_bytes()).map_err(write_err)?;
        }
    }

    writer.flush().map_err(write_err)?;
    Ok(())
}

fn write_err(e: io::Error) -> WordsivError {
    WordsivError::Value(format!("Write error: {}", e))
}

// ---------------------------------------------------------------------------
// Auto-download GloVe embeddings
// ---------------------------------------------------------------------------

const GLOVE_URL: &str = "https://nlp.stanford.edu/data/glove.6B.zip";
const GLOVE_INNER_FILE: &str = "glove.6B.100d.txt";

/// Return the path to the embeddings binary for a given language.
/// Currently only "en" is supported.
pub fn embeddings_dir() -> Result<PathBuf, WordsivError> {
    let base = dirs::data_dir()
        .or_else(|| dirs::home_dir().map(|h| h.join(".local").join("share")))
        .ok_or_else(|| WordsivError::Value("Cannot determine home directory".into()))?;
    Ok(base.join("wordsiv"))
}

pub fn embeddings_path(lang: &str) -> Result<PathBuf, WordsivError> {
    Ok(embeddings_dir()?.join(format!("{}_glove_100d.bin", lang)))
}

/// Check if embeddings exist for a language.
pub fn has_embeddings(lang: &str) -> bool {
    embeddings_path(lang).map(|p| p.exists()).unwrap_or(false)
}

/// Download and convert GloVe embeddings. Blocks until complete.
/// Prints progress to stderr.
pub fn download_embeddings(lang: &str) -> Result<PathBuf, WordsivError> {
    if lang != "en" {
        return Err(WordsivError::Value(format!(
            "Embedding download for '{}' is not yet supported (only 'en')",
            lang
        )));
    }

    let bin_path = embeddings_path(lang)?;
    if bin_path.exists() {
        return Ok(bin_path);
    }

    eprintln!("[wordsiv] Downloading GloVe embeddings (~862 MB)...");
    eprintln!("[wordsiv] This is a one-time download. The file will be cached at:");
    eprintln!("[wordsiv]   {}", bin_path.display());

    let data_dir = embeddings_dir()?;
    std::fs::create_dir_all(&data_dir).map_err(|e| {
        WordsivError::Value(format!("Failed to create data directory: {}", e))
    })?;

    // Download zip to a temp file
    let zip_path = data_dir.join("_glove_download.zip");
    download_file(GLOVE_URL, &zip_path)?;

    // Extract the 100d file
    eprintln!("[wordsiv] Extracting {}...", GLOVE_INNER_FILE);
    let txt_path = data_dir.join(GLOVE_INNER_FILE);
    extract_from_zip(&zip_path, GLOVE_INNER_FILE, &txt_path)?;

    // Convert to binary
    eprintln!("[wordsiv] Converting to binary format...");
    convert_glove_text_to_binary(&txt_path, &bin_path)?;

    // Clean up
    let _ = std::fs::remove_file(&zip_path);
    let _ = std::fs::remove_file(&txt_path);

    eprintln!("[wordsiv] Embeddings ready.");
    Ok(bin_path)
}

/// Download a URL to a file path using a simple HTTP client.
fn download_file(url: &str, dest: &Path) -> Result<(), WordsivError> {
    // Use a minimal HTTP approach: shell out to curl which is available on
    // macOS and most Linux. This avoids pulling in a heavy HTTP crate.
    let status = std::process::Command::new("curl")
        .args(["-fSL", "--progress-bar", "-o"])
        .arg(dest.as_os_str())
        .arg(url)
        .status()
        .map_err(|e| {
            WordsivError::Value(format!(
                "Failed to run curl (is it installed?): {}",
                e
            ))
        })?;

    if !status.success() {
        return Err(WordsivError::Value(format!(
            "Download failed (curl exit code {:?}). URL: {}",
            status.code(),
            url
        )));
    }
    Ok(())
}

/// Extract a single file from a zip archive.
fn extract_from_zip(
    zip_path: &Path,
    inner_name: &str,
    dest: &Path,
) -> Result<(), WordsivError> {
    let file = std::fs::File::open(zip_path).map_err(|e| {
        WordsivError::Value(format!("Failed to open zip: {}", e))
    })?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| {
        WordsivError::Value(format!("Failed to read zip archive: {}", e))
    })?;
    let mut entry = archive.by_name(inner_name).map_err(|e| {
        WordsivError::Value(format!("File '{}' not found in zip: {}", inner_name, e))
    })?;

    let mut outfile = std::fs::File::create(dest).map_err(|e| {
        WordsivError::Value(format!("Failed to create '{}': {}", dest.display(), e))
    })?;

    io::copy(&mut entry, &mut outfile).map_err(|e| {
        WordsivError::Value(format!("Failed to extract '{}': {}", inner_name, e))
    })?;

    Ok(())
}

// ---------------------------------------------------------------------------
// Global embedding store — loaded once per process
// ---------------------------------------------------------------------------

static EMBEDDING_STORE: OnceLock<Mutex<HashMap<String, Arc<EmbeddingStore>>>> = OnceLock::new();

fn global_embedding_stores() -> &'static Mutex<HashMap<String, Arc<EmbeddingStore>>> {
    EMBEDDING_STORE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Get (or load) the embedding store for a language. Downloads if needed.
pub fn get_embedding_store(lang: &str) -> Result<Arc<EmbeddingStore>, WordsivError> {
    // Check cache
    {
        let stores = global_embedding_stores().lock().unwrap();
        if let Some(store) = stores.get(lang) {
            return Ok(Arc::clone(store));
        }
    }

    // Download if needed
    let bin_path = download_embeddings(lang)?;

    // Load
    let store = EmbeddingStore::open(&bin_path)?;
    let arc = Arc::new(store);

    {
        let mut stores = global_embedding_stores().lock().unwrap();
        stores.insert(lang.to_string(), Arc::clone(&arc));
    }

    Ok(arc)
}

/// Clear cached embedding stores.
pub fn clear_embedding_stores() {
    if let Some(stores) = EMBEDDING_STORE.get() {
        let mut map = stores.lock().unwrap();
        map.clear();
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    /// Create a tiny binary embedding file in a temp directory.
    fn create_test_binary(dir: &Path) -> PathBuf {
        let path = dir.join("test_embeddings.bin");
        let dim: u16 = 3;
        let words = vec![
            ("cat", vec![1.0f32, 0.0, 0.0]),
            ("dog", vec![0.9, 0.1, 0.0]),
            ("car", vec![0.0, 0.0, 1.0]),
            ("truck", vec![0.1, 0.0, 0.9]),
            ("kitten", vec![0.95, 0.05, 0.0]),
        ];
        let word_count = words.len() as u32;

        let mut f = std::fs::File::create(&path).unwrap();
        f.write_all(MAGIC).unwrap();
        f.write_all(&[FORMAT_VERSION]).unwrap();
        f.write_all(&dim.to_le_bytes()).unwrap();
        f.write_all(&word_count.to_le_bytes()).unwrap();

        for (word, vec) in &words {
            let wb = word.as_bytes();
            f.write_all(&(wb.len() as u16).to_le_bytes()).unwrap();
            f.write_all(wb).unwrap();
            for v in vec {
                f.write_all(&v.to_le_bytes()).unwrap();
            }
        }
        path
    }

    #[test]
    fn test_roundtrip_binary() {
        let dir = std::env::temp_dir().join("wordsiv_test_embed");
        let _ = std::fs::create_dir_all(&dir);
        let path = create_test_binary(&dir);

        let store = EmbeddingStore::open(&path).unwrap();
        assert_eq!(store.dim(), 3);
        assert_eq!(store.word_count(), 5);

        let cat = store.get("cat").unwrap();
        assert_eq!(cat, &[1.0f32, 0.0, 0.0]);

        let dog = store.get("dog").unwrap();
        assert!((dog[0] - 0.9).abs() < 1e-6);

        assert!(store.get("fish").is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_cosine_similarity_identical() {
        let a = vec![1.0f32, 0.0, 0.0];
        let b = vec![1.0f32, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn test_cosine_similarity_orthogonal() {
        let a = vec![1.0f32, 0.0, 0.0];
        let b = vec![0.0f32, 1.0, 0.0];
        assert!(cosine_similarity(&a, &b).abs() < 1e-6);
    }

    #[test]
    fn test_theme_vector() {
        let dir = std::env::temp_dir().join("wordsiv_test_theme");
        let _ = std::fs::create_dir_all(&dir);
        let path = create_test_binary(&dir);
        let store = EmbeddingStore::open(&path).unwrap();

        // Theme "cat dog" should average their vectors
        let tv = theme_vector(&store, "cat dog").unwrap();
        assert!((tv[0] - 0.95).abs() < 1e-6); // (1.0 + 0.9) / 2
        assert!((tv[1] - 0.05).abs() < 1e-6); // (0.0 + 0.1) / 2

        // Unknown words return None
        assert!(theme_vector(&store, "zebra").is_none());

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_score_words_ranking() {
        let dir = std::env::temp_dir().join("wordsiv_test_score");
        let _ = std::fs::create_dir_all(&dir);
        let path = create_test_binary(&dir);
        let store = EmbeddingStore::open(&path).unwrap();

        // Query: "cat" → vec [1, 0, 0]
        let query = store.get("cat").unwrap().to_vec();
        let words: Vec<String> = vec![
            "car".into(), "dog".into(), "kitten".into(), "truck".into(),
        ];
        let scored = score_words(&store, &query, &words);

        // kitten (0.95, 0.05, 0) should be closest to cat (1, 0, 0)
        // then dog (0.9, 0.1, 0), then truck (0.1, 0, 0.9), then car (0, 0, 1)
        assert_eq!(scored[0].0, "kitten");
        assert_eq!(scored[1].0, "dog");

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_filter_by_theme() {
        let dir = std::env::temp_dir().join("wordsiv_test_filter");
        let _ = std::fs::create_dir_all(&dir);
        let path = create_test_binary(&dir);
        let store = EmbeddingStore::open(&path).unwrap();

        let word_counts = vec![
            ("cat".into(), 100u64),
            ("dog".into(), 80),
            ("car".into(), 60),
            ("truck".into(), 40),
            ("kitten".into(), 20),
        ];

        // strength=0.0 → keep all
        let result = filter_by_theme(&store, "cat", 0.0, &word_counts);
        assert_eq!(result.len(), 5);

        // strength=1.0 → keep ~1% = ceil(5 * 0.01) = 1 word
        let result = filter_by_theme(&store, "cat", 1.0, &word_counts);
        assert!(result.len() <= 2); // ceil(5 * 0.01) = 1
        // The kept word(s) should be the most cat-like
        assert!(result.iter().any(|(w, _)| w == "cat" || w == "kitten"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn test_convert_glove_text_to_binary() {
        let dir = std::env::temp_dir().join("wordsiv_test_convert");
        let _ = std::fs::create_dir_all(&dir);

        // Write a tiny GloVe-format text file
        let txt_path = dir.join("test_glove.txt");
        let bin_path = dir.join("test_glove.bin");
        {
            let mut f = std::fs::File::create(&txt_path).unwrap();
            writeln!(f, "hello 0.1 0.2 0.3").unwrap();
            writeln!(f, "world 0.4 0.5 0.6").unwrap();
        }

        convert_glove_text_to_binary(&txt_path, &bin_path).unwrap();

        // Read it back
        let store = EmbeddingStore::open(&bin_path).unwrap();
        assert_eq!(store.dim(), 3);
        assert_eq!(store.word_count(), 2);

        let hello = store.get("hello").unwrap();
        assert!((hello[0] - 0.1).abs() < 1e-6);
        assert!((hello[1] - 0.2).abs() < 1e-6);
        assert!((hello[2] - 0.3).abs() < 1e-6);

        let _ = std::fs::remove_dir_all(&dir);
    }
}
