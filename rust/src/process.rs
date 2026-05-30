use crate::errors::py_err;
use crate::progress::parse_progress_blocks_inner;
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyString};
use std::collections::HashMap;
use std::process::Stdio;
use std::time::Duration;
use tokio::io::AsyncWriteExt;
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

fn extract_input_data(input_data: Option<&Bound<'_, PyAny>>) -> PyResult<Option<Vec<u8>>> {
    let Some(input) = input_data else {
        return Ok(None);
    };
    if input.is_none() {
        return Ok(None);
    }
    if let Ok(bytes) = input.downcast::<PyBytes>() {
        return Ok(Some(bytes.as_bytes().to_vec()));
    }
    if let Ok(text) = input.downcast::<PyString>() {
        return Ok(Some(text.to_str()?.as_bytes().to_vec()));
    }
    Err(PyTypeError::new_err(
        "input_data must be bytes, str, or None",
    ))
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
        .stderr(Stdio::piped())
        .kill_on_drop(true);
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
#[pyo3(signature = (args, input_data=None, timeout=None, cwd=None, env=None, max_output_bytes=None))]
fn run_ffmpeg_full_py(
    args: Vec<String>,
    input_data: Option<&Bound<'_, PyAny>>,
    timeout: Option<f64>,
    cwd: Option<String>,
    env: Option<HashMap<String, String>>,
    max_output_bytes: Option<usize>,
) -> PyResult<FFmpegResult> {
    let input = extract_input_data(input_data)?;
    let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
    let result = rt.block_on(async {
        if args.is_empty() {
            return Err(PyValueError::new_err("args must not be empty"));
        }
        let mut cmd = Command::new(&args[0]);
        cmd.args(&args[1..])
            .stdin(if input.is_some() {
                Stdio::piped()
            } else {
                Stdio::null()
            })
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .kill_on_drop(true);
        if let Some(cwd) = &cwd {
            cmd.current_dir(cwd);
        }
        if let Some(env) = &env {
            cmd.envs(env);
        }
        let mut child = cmd.spawn().map_err(py_err)?;
        if let Some(input) = input {
            if let Some(mut stdin) = child.stdin.take() {
                stdin.write_all(&input).await.map_err(py_err)?;
            }
        }
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

#[cfg(test)]
mod tests {
    use super::run_process_async;
    use std::path::Path;
    use std::time::Duration;

    fn delayed_marker_command(marker_path: &Path) -> Vec<String> {
        let path = marker_path.to_string_lossy();
        if cfg!(windows) {
            let escaped = path.replace('\'', "''");
            vec![
                "powershell".to_string(),
                "-NoProfile".to_string(),
                "-Command".to_string(),
                format!("Start-Sleep -Milliseconds 500; Set-Content -LiteralPath '{escaped}' -Value done"),
            ]
        } else {
            let escaped = path.replace('\'', "'\\''");
            vec![
                "sh".to_string(),
                "-c".to_string(),
                format!("sleep 0.5; printf done > '{escaped}'"),
            ]
        }
    }

    #[tokio::test]
    async fn timed_out_process_is_killed() {
        let marker_path = std::env::temp_dir().join(format!(
            "voidplayer-timeout-marker-{}-{}.txt",
            std::process::id(),
            chrono_like_timestamp()
        ));
        let _ = std::fs::remove_file(&marker_path);

        let result = run_process_async(delayed_marker_command(&marker_path), Some(0.05)).await;

        assert!(result.is_err());
        tokio::time::sleep(Duration::from_millis(900)).await;
        assert!(!marker_path.exists());
    }

    fn chrono_like_timestamp() -> u128 {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |duration| duration.as_nanos())
    }
}
