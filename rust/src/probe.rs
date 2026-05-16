use crate::errors::{py_err, resolve_executable};
use crate::options::normalize_options_inner;
use crate::process::run_process_async;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

fn json_to_py(py: Python<'_>, value: &serde_json::Value) -> PyResult<PyObject> {
    Ok(match value {
        serde_json::Value::Null => py.None(),
        serde_json::Value::Bool(v) => v.into_py(py),
        serde_json::Value::Number(v) => {
            if let Some(i) = v.as_i64() {
                i.into_py(py)
            } else if let Some(u) = v.as_u64() {
                u.into_py(py)
            } else {
                v.as_f64().unwrap_or(0.0).into_py(py)
            }
        }
        serde_json::Value::String(v) => v.into_py(py),
        serde_json::Value::Array(values) => {
            let list = PyList::empty_bound(py);
            for item in values {
                list.append(json_to_py(py, item)?)?;
            }
            list.into_py(py)
        }
        serde_json::Value::Object(values) => {
            let dict = PyDict::new_bound(py);
            for (key, item) in values {
                dict.set_item(key, json_to_py(py, item)?)?;
            }
            dict.into_py(py)
        }
    })
}

#[pyfunction]
fn parse_probe_json_py(py: Python<'_>, raw: &str) -> PyResult<PyObject> {
    let value: serde_json::Value = serde_json::from_str(raw)
        .map_err(|err| PyValueError::new_err(format!("Invalid ffprobe JSON: {err}")))?;
    json_to_py(py, &value)
}

#[pyfunction]
#[pyo3(signature = (path, ffprobe="ffprobe", timeout=None, input_options=None))]
fn probe_py(
    py: Python<'_>,
    path: String,
    ffprobe: &str,
    timeout: Option<f64>,
    input_options: Option<&Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    let mut args = vec![
        resolve_executable(ffprobe, "ffprobe")?,
        "-v".to_string(),
        "error".to_string(),
        "-print_format".to_string(),
        "json".to_string(),
        "-show_format".to_string(),
        "-show_streams".to_string(),
    ];
    args.extend(normalize_options_inner(input_options)?);
    args.push(path);
    let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
    let result = rt.block_on(run_process_async(args, timeout))?;
    parse_probe_json_py(py, &result.stdout)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_probe_json_py, m)?)?;
    m.add_function(wrap_pyfunction!(probe_py, m)?)?;
    Ok(())
}
