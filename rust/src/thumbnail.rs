use crate::errors::{py_err, resolve_executable};
use crate::process::run_process_async;
use crate::timestamp::format_timestamp_value;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use sha1::{Digest, Sha1};
use std::path::PathBuf;
use std::sync::Arc;
use tokio::sync::Semaphore;

#[pyfunction]
fn thumbnail_cache_key(media_path: String, modified: String) -> String {
    let mut hasher = Sha1::new();
    hasher.update(format!("{media_path}:{modified}").as_bytes());
    format!("{:x}", hasher.finalize())[..16].to_string()
}

#[pyfunction]
#[pyo3(signature = (media_path, duration, output_dir, ffmpeg="ffmpeg", interval=30.0, max_count=20, quality=3, max_workers=2))]
fn generate_timeline_thumbnails_py(
    py: Python<'_>,
    media_path: String,
    duration: Option<f64>,
    output_dir: PathBuf,
    ffmpeg: &str,
    interval: f64,
    max_count: usize,
    quality: u8,
    max_workers: usize,
) -> PyResult<PyObject> {
    std::fs::create_dir_all(&output_dir).map_err(py_err)?;
    let stamps = crate::timestamp::preview_timestamps_inner(duration, interval, max_count);
    let ffmpeg = resolve_executable(ffmpeg, "ffmpeg")?;
    let workers = max_workers.max(1);
    let rt = tokio::runtime::Runtime::new().map_err(py_err)?;
    let results = rt.block_on(async {
        let semaphore = Arc::new(Semaphore::new(workers));
        let mut handles: Vec<tokio::task::JoinHandle<PyResult<(f64, String, bool)>>> = Vec::new();
        for stamp in stamps {
            let permit = semaphore.clone().acquire_owned().await.map_err(py_err)?;
            let ffmpeg = ffmpeg.clone();
            let media_path = media_path.clone();
            let output = output_dir.join(format!("{:010}.jpg", (stamp * 1000.0) as u64));
            handles.push(tokio::spawn(async move {
                let _permit = permit;
                if output.exists() {
                    return Ok((stamp, output.to_string_lossy().to_string(), false));
                }
                let args = vec![
                    ffmpeg,
                    "-y".to_string(),
                    "-ss".to_string(),
                    format_timestamp_value(stamp),
                    "-i".to_string(),
                    media_path,
                    "-frames:v".to_string(),
                    "1".to_string(),
                    "-q:v".to_string(),
                    quality.to_string(),
                    output.to_string_lossy().to_string(),
                ];
                run_process_async(args, None).await?;
                Ok((stamp, output.to_string_lossy().to_string(), true))
            }));
        }
        let mut out = Vec::new();
        for handle in handles {
            out.push(handle.await.map_err(py_err)??);
        }
        Ok::<_, PyErr>(out)
    })?;
    let list = PyList::empty_bound(py);
    for (timestamp, path, generated) in results {
        let dict = PyDict::new_bound(py);
        dict.set_item("timestamp", timestamp)?;
        dict.set_item("path", path)?;
        dict.set_item("generated", generated)?;
        list.append(dict)?;
    }
    Ok(list.into_py(py))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(thumbnail_cache_key, m)?)?;
    m.add_function(wrap_pyfunction!(generate_timeline_thumbnails_py, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn cache_key_is_stable() {
        assert_eq!(
            thumbnail_cache_key("a".into(), "1".into()),
            thumbnail_cache_key("a".into(), "1".into())
        );
        assert_eq!(thumbnail_cache_key("a".into(), "1".into()).len(), 16);
    }
}
