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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_blocks_and_trailing_block() {
        let blocks = parse_progress_blocks_inner("ignore\nframe=1\nprogress=continue\nframe=2\n");
        assert_eq!(blocks.len(), 2);
        assert_eq!(blocks[0].get("frame").unwrap(), "1");
        assert_eq!(blocks[1].get("frame").unwrap(), "2");
    }
}
