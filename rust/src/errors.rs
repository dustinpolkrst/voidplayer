use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::path::Path;

pub fn py_err<E: std::fmt::Display>(err: E) -> PyErr {
    PyRuntimeError::new_err(err.to_string())
}

pub fn resolve_executable(executable: &str, label: &str) -> PyResult<String> {
    let path = Path::new(executable);
    if path.is_absolute() || executable.contains('/') || executable.contains('\\') {
        if path.exists() {
            return Ok(executable.to_string());
        }
        return Err(PyRuntimeError::new_err(format!(
            "{label} executable was not found: {executable}"
        )));
    }
    which::which(executable)
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|_| PyRuntimeError::new_err(format!("{label} executable was not found on PATH. Install FFmpeg or pass an explicit executable path.")))
}

#[pyfunction]
pub fn classify_process_error_kind(
    _args: Vec<String>,
    _returncode: i32,
    _stdout: &str,
    stderr: &str,
) -> String {
    let message = stderr
        .lines()
        .rev()
        .map(str::trim)
        .find(|line| {
            !line.is_empty()
                && !line.starts_with("frame=")
                && !line.starts_with("size=")
                && !line.starts_with("video:")
                && !line.starts_with("audio:")
        })
        .unwrap_or("")
        .to_lowercase();
    if [
        "unknown encoder",
        "encoder not found",
        "unknown decoder",
        "decoder not found",
    ]
    .iter()
    .any(|needle| message.contains(needle))
    {
        "unsupported_codec".to_string()
    } else if [
        "option not found",
        "unrecognized option",
        "trailing option",
        "invalid argument",
        "codec not currently supported in container",
    ]
    .iter()
    .any(|needle| message.contains(needle))
    {
        "invalid_command".to_string()
    } else {
        "process_error".to_string()
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(classify_process_error_kind, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classifies_process_errors() {
        assert_eq!(
            classify_process_error_kind(vec![], 1, "", "Unknown encoder 'x'"),
            "unsupported_codec"
        );
        assert_eq!(
            classify_process_error_kind(vec![], 1, "", "Unrecognized option 'x'"),
            "invalid_command"
        );
        assert_eq!(
            classify_process_error_kind(vec![], 1, "", "Something failed"),
            "process_error"
        );
    }
}
