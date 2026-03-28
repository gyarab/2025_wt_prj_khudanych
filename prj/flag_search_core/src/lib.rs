use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;

/// Odstraní diakritiku (ekvivalent unicodedata.normalize)
#[pyfunction]
fn strip_accents(text: &str) -> String {
    text.nfd()
        .filter(|c| {
            let cv = *c as u32;
            // Odfiltruje "combining marks" (háčky, čárky atd.)
            !(cv >= 0x0300 && cv <= 0x036F)
        })
        .collect()
}

/// Case- and accent-insensitive substring match
#[pyfunction]
fn accent_insensitive_match(haystack: &str, needle: &str) -> bool {
    if haystack.is_empty() || needle.is_empty() {
        return false;
    }
    let stripped_haystack = strip_accents(haystack).to_lowercase();
    let stripped_needle = strip_accents(needle).to_lowercase();
    
    stripped_haystack.contains(&stripped_needle)
}

/// Registrace modulu pro Python
#[pymodule]
fn flag_search_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(strip_accents, m)?)?;
    m.add_function(wrap_pyfunction!(accent_insensitive_match, m)?)?;
    Ok(())
}