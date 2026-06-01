pub mod engine;
pub mod errors;
pub mod filter;
pub mod punctuation;
pub mod vocab;

#[cfg(feature = "shaping")]
pub mod shaping;

#[cfg(feature = "semantic")]
pub mod semantic;

#[cfg(feature = "python")]
mod python;

#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pymodule]
fn wordsiv(m: &Bound<'_, PyModule>) -> PyResult<()> {
    python::register(m)
}
