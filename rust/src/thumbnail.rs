use pyo3::prelude::*;
use sha1::{Digest, Sha1};

#[pyfunction]
fn thumbnail_cache_key(media_path: String, modified: String) -> String {
    let mut hasher = Sha1::new();
    hasher.update(format!("{media_path}:{modified}").as_bytes());
    format!("{:x}", hasher.finalize())[..16].to_string()
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(thumbnail_cache_key, m)?)?;
    Ok(())
}
