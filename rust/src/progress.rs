use pyo3::prelude::*;
use std::collections::HashMap;

pub fn parse_progress_blocks_inner(stdout: &str) -> Vec<HashMap<String, String>> {
    let mut blocks = Vec::new();
    let mut current = HashMap::new();
    for line in stdout.lines() {
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        current.insert(key.to_string(), value.to_string());
        if key == "progress" {
            blocks.push(current);
            current = HashMap::new();
        }
    }
    if !current.is_empty() {
        blocks.push(current);
    }
    blocks
}

#[pyfunction]
fn parse_progress_blocks_py(stdout: &str) -> Vec<HashMap<String, String>> {
    parse_progress_blocks_inner(stdout)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_progress_blocks_py, m)?)?;
    Ok(())
}
