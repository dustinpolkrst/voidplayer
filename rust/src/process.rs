use crate::errors::py_err;
use crate::progress::parse_progress_blocks_inner;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use std::collections::HashMap;
use std::process::Stdio;
use std::time::Duration;
use tokio::process::Command;
use tokio::time::timeout as tokio_timeout;

#[pyclass]
#[derive(Clone, Debug)]
pub struct FFmpegResult {
    #[pyo3(get)]
    pub args: Vec<String>,
    #[pyo3(get)]
    pub returncode: i32,
    #[pyo3(get)]
    pub stdout: String,
    #[pyo3(get)]
    pub stderr: String,
    #[pyo3(get)]
    pub progress: Vec<HashMap<String, String>>,
}

pub async fn run_process_async(
    args: Vec<String>,
    timeout_seconds: Option<f64>,
) -> PyResult<FFmpegResult> {
    if args.is_empty() {
        return Err(PyValueError::new_err("args must not be empty"));
    }
    let mut cmd = Command::new(&args[0]);
    cmd.args(&args[1..])
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let child = cmd.spawn().map_err(py_err)?;
    let wait = child.wait_with_output();
    let output = if let Some(seconds) = timeout_seconds {
        tokio_timeout(Duration::from_secs_f64(seconds), wait)
            .await
            .map_err(|_| {
                PyRuntimeError::new_err(format!(
                    "Process timed out after {seconds} seconds: {args:?}"
                ))
            })?
            .map_err(py_err)?
    } else {
        wait.await.map_err(py_err)?
    };
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    let code = output.status.code().unwrap_or(-1);
    if !output.status.success() {
        return Err(PyRuntimeError::new_err(format!(
            "FFmpeg process failed with exit code {code}: {stderr}"
        )));
    }
    let progress = parse_progress_blocks_inner(&stdout);
    Ok(FFmpegResult {
        args,
        returncode: code,
        stdout,
        stderr,
        progress,
    })
}

#[pyfunction]
#[pyo3(signature = (args, timeout=None))]
fn run_ffmpeg_py(args: Vec<String>, timeout: Option<f64>) -> PyResult<FFmpegResult> {
    let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
    rt.block_on(run_process_async(args, timeout))
}

#[pyfunction]
#[pyo3(signature = (args, timeout=None, cwd=None, env=None, max_output_bytes=None))]
fn run_ffmpeg_full_py(
    args: Vec<String>,
    timeout: Option<f64>,
    cwd: Option<String>,
    env: Option<HashMap<String, String>>,
    max_output_bytes: Option<usize>,
) -> PyResult<FFmpegResult> {
    let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
    let result = rt.block_on(async {
        if args.is_empty() {
            return Err(PyValueError::new_err("args must not be empty"));
        }
        let mut cmd = Command::new(&args[0]);
        cmd.args(&args[1..])
            .stdin(Stdio::null())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        if let Some(cwd) = &cwd {
            cmd.current_dir(cwd);
        }
        if let Some(env) = &env {
            cmd.envs(env);
        }
        let child = cmd.spawn().map_err(py_err)?;
        let wait = child.wait_with_output();
        let output = if let Some(seconds) = timeout {
            tokio_timeout(Duration::from_secs_f64(seconds), wait)
                .await
                .map_err(|_| PyRuntimeError::new_err(format!("timeout:{seconds}")))?
                .map_err(py_err)?
        } else {
            wait.await.map_err(py_err)?
        };
        let mut stdout_bytes = output.stdout;
        let mut stderr_bytes = output.stderr;
        if let Some(limit) = max_output_bytes {
            if stdout_bytes.len() > limit {
                stdout_bytes = stdout_bytes[stdout_bytes.len() - limit..].to_vec();
            }
            if stderr_bytes.len() > limit {
                stderr_bytes = stderr_bytes[stderr_bytes.len() - limit..].to_vec();
            }
        }
        let stdout = String::from_utf8_lossy(&stdout_bytes).to_string();
        let stderr = String::from_utf8_lossy(&stderr_bytes).to_string();
        let code = output.status.code().unwrap_or(-1);
        let progress = parse_progress_blocks_inner(&stdout);
        Ok(FFmpegResult {
            args,
            returncode: code,
            stdout,
            stderr,
            progress,
        })
    })?;
    Ok(result)
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FFmpegResult>()?;
    m.add_function(wrap_pyfunction!(run_ffmpeg_py, m)?)?;
    m.add_function(wrap_pyfunction!(run_ffmpeg_full_py, m)?)?;
    Ok(())
}
