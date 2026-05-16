use crate::errors::resolve_executable;
use pyo3::prelude::*;
use pyo3::types::{PyMapping, PySequence};

pub fn normalize_options_inner(options: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
    let Some(options) = options else {
        return Ok(Vec::new());
    };
    if options.is_none() {
        return Ok(Vec::new());
    }
    let mapping = options.downcast::<PyMapping>()?;
    let items = mapping.call_method0("items")?;
    let mut args = Vec::new();
    for item in items.iter()? {
        let tuple = item?;
        let key_obj = tuple.get_item(0)?;
        let value = tuple.get_item(1)?;
        let key: String = key_obj.extract()?;
        let flag = if key.starts_with('-') {
            key
        } else {
            format!("-{key}")
        };
        if value.is_none() {
            continue;
        }
        if let Ok(v) = value.extract::<bool>() {
            if v {
                args.push(flag);
            }
            continue;
        }
        if value.is_instance_of::<pyo3::types::PyString>()
            || value.is_instance_of::<pyo3::types::PyBytes>()
        {
            args.push(flag);
            args.push(value.str()?.to_str()?.to_string());
            continue;
        }
        if let Ok(seq) = value.downcast::<PySequence>() {
            for seq_item in seq.iter()? {
                args.push(flag.clone());
                args.push(seq_item?.str()?.to_str()?.to_string());
            }
        } else {
            args.push(flag);
            args.push(value.str()?.to_str()?.to_string());
        }
    }
    Ok(args)
}

#[pyfunction]
#[pyo3(signature = (options=None))]
fn normalize_options(options: Option<&Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
    normalize_options_inner(options)
}

#[pyfunction]
#[pyo3(signature = (inputs, output, ffmpeg="ffmpeg", global_options=None, input_options=None, output_options=None, overwrite=false, progress=false))]
fn build_command(
    inputs: Vec<String>,
    output: String,
    ffmpeg: &str,
    global_options: Option<&Bound<'_, PyAny>>,
    input_options: Option<&Bound<'_, PyAny>>,
    output_options: Option<&Bound<'_, PyAny>>,
    overwrite: bool,
    progress: bool,
) -> PyResult<Vec<String>> {
    let mut args = vec![resolve_executable(ffmpeg, "ffmpeg")?];
    args.extend(normalize_options_inner(global_options)?);
    args.push(if overwrite { "-y" } else { "-n" }.to_string());
    if progress {
        args.extend(["-progress".to_string(), "pipe:1".to_string()]);
    }
    let input_opts = normalize_options_inner(input_options)?;
    for input in inputs {
        args.extend(input_opts.clone());
        args.extend(["-i".to_string(), input]);
    }
    args.extend(normalize_options_inner(output_options)?);
    args.push(output);
    Ok(args)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(normalize_options, m)?)?;
    m.add_function(wrap_pyfunction!(build_command, m)?)?;
    Ok(())
}
