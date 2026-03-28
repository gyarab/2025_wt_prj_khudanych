use pyo3::prelude::*;
use unicode_normalization::UnicodeNormalization;
use regex::Regex;

/// Odstraní diakritiku (ekvivalent unicodedata.normalize v Pythonu)
#[pyfunction]
fn strip_accents(text: &str) -> String {
    text.nfd()
        .filter(|c| {
            let cv = *c as u32;
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

/// Rychlé rozhodnutí o základu pro slug, využívá optimalizovaný regex
#[pyfunction]
fn get_slug_base(name: &str, en_label: Option<String>) -> String {
    let re = Regex::new(r"^Q\d+$").unwrap();
    match en_label {
        Some(label) if !re.is_match(&label) => label,
        _ => name.to_string(),
    }
}

/// Rychlé vyhledávání vlastníka území podle klíčových slov (O(n) hledání v paměti)
#[pyfunction]
fn identify_owner_cca3(text: &str) -> Option<String> {
    let keywords = [
        ("french", "FRA"), ("british", "GBR"), ("dutch", "NLD"),
        ("netherlands", "NLD"), ("american", "USA"), ("united states", "USA"),
        ("danish", "DNK"), ("norwegian", "NOR"), ("australian", "AUS"),
        ("new zealand", "NZL"), ("chinese", "CHN"), ("hong kong", "CHN"),
        ("macao", "CHN"), ("macau", "CHN"),
    ];
    let lower_text = text.to_lowercase();
    for (key, cca3) in keywords {
        if lower_text.contains(key) {
            return Some(cca3.to_string());
        }
    }
    None
}

/// Registrace modulu pro Python
#[pymodule]
fn flag_search_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(strip_accents, m)?)?;
    m.add_function(wrap_pyfunction!(accent_insensitive_match, m)?)?;
    m.add_function(wrap_pyfunction!(get_slug_base, m)?)?;
    m.add_function(wrap_pyfunction!(identify_owner_cca3, m)?)?;
    Ok(())
}