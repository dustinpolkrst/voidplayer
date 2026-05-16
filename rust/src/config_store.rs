use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Clone, Debug, Serialize, Deserialize)]
struct AnimeHistoryItem {
    title: String,
    show_id: String,
    episode: String,
    mode: String,
    stream_url: String,
    display_name: String,
    #[serde(default)]
    position: f64,
    #[serde(default)]
    duration: Option<f64>,
    #[serde(default)]
    subtitle_url: Option<String>,
    #[serde(default)]
    updated_at: f64,
}

fn now_seconds() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}

fn optional_positive(value: Option<f64>) -> Option<f64> {
    value.filter(|v| *v > 0.0)
}

fn item_from_dict(raw: &Bound<'_, PyDict>) -> PyResult<Option<AnimeHistoryItem>> {
    let get_str = |key: &str| -> PyResult<Option<String>> {
        Ok(raw
            .get_item(key)?
            .and_then(|v| v.extract::<String>().ok())
            .filter(|v| !v.is_empty()))
    };
    let Some(title) = get_str("title")? else {
        return Ok(None);
    };
    let Some(show_id) = get_str("show_id")? else {
        return Ok(None);
    };
    let Some(episode) = get_str("episode")? else {
        return Ok(None);
    };
    let Some(mode) = get_str("mode")? else {
        return Ok(None);
    };
    let Some(stream_url) = get_str("stream_url")? else {
        return Ok(None);
    };
    let Some(display_name) = get_str("display_name")? else {
        return Ok(None);
    };
    let position = raw
        .get_item("position")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let duration = optional_positive(
        raw.get_item("duration")?
            .and_then(|v| v.extract::<f64>().ok()),
    );
    let subtitle_url = raw
        .get_item("subtitle_url")?
        .and_then(|v| v.extract::<String>().ok());
    let updated_at = raw
        .get_item("updated_at")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    Ok(Some(AnimeHistoryItem {
        title,
        show_id,
        episode,
        mode,
        stream_url,
        display_name,
        position,
        duration,
        subtitle_url,
        updated_at,
    }))
}

fn item_to_dict<'py>(py: Python<'py>, item: &AnimeHistoryItem) -> PyResult<Bound<'py, PyDict>> {
    let dict = PyDict::new_bound(py);
    dict.set_item("title", &item.title)?;
    dict.set_item("show_id", &item.show_id)?;
    dict.set_item("episode", &item.episode)?;
    dict.set_item("mode", &item.mode)?;
    dict.set_item("stream_url", &item.stream_url)?;
    dict.set_item("display_name", &item.display_name)?;
    dict.set_item("position", item.position)?;
    dict.set_item("duration", item.duration)?;
    dict.set_item("subtitle_url", &item.subtitle_url)?;
    dict.set_item("updated_at", item.updated_at)?;
    Ok(dict)
}

fn history_items(config: &Bound<'_, PyDict>) -> PyResult<Vec<AnimeHistoryItem>> {
    let Some(raw_items) = config.get_item("anime_history")? else {
        return Ok(Vec::new());
    };
    let Ok(list) = raw_items.downcast::<PyList>() else {
        return Ok(Vec::new());
    };
    let mut items = Vec::new();
    for raw in list.iter() {
        if let Ok(dict) = raw.downcast::<PyDict>() {
            if let Some(item) = item_from_dict(dict)? {
                items.push(item);
            }
        }
    }
    Ok(items)
}

#[pyfunction]
fn load_config_py(py: Python<'_>, path: PathBuf) -> PyResult<PyObject> {
    let Ok(text) = fs::read_to_string(path) else {
        return Ok(PyDict::new_bound(py).into_py(py));
    };
    let value: serde_json::Value = match serde_json::from_str(&text) {
        Ok(value) => value,
        Err(_) => return Ok(PyDict::new_bound(py).into_py(py)),
    };
    if !value.is_object() {
        return Ok(PyDict::new_bound(py).into_py(py));
    }
    crate::probe::json_to_py(py, &value)
}

#[pyfunction]
fn anime_history_from_config_py(py: Python<'_>, config: &Bound<'_, PyDict>) -> PyResult<PyObject> {
    let list = PyList::empty_bound(py);
    for item in history_items(config)? {
        list.append(item_to_dict(py, &item)?)?;
    }
    Ok(list.into_py(py))
}

#[pyfunction]
#[pyo3(signature = (config, item, limit=20))]
fn set_anime_history_item_py(
    py: Python<'_>,
    config: &Bound<'_, PyDict>,
    item: &Bound<'_, PyDict>,
    limit: usize,
) -> PyResult<PyObject> {
    let updated = config.copy()?;
    let Some(mut fresh) = item_from_dict(item)? else {
        return Ok(updated.into_py(py));
    };
    if fresh.updated_at == 0.0 {
        fresh.updated_at = now_seconds();
    }
    let mut entries = vec![fresh.clone()];
    for existing in history_items(config)? {
        if (
            existing.show_id.as_str(),
            existing.episode.as_str(),
            existing.mode.as_str(),
        ) != (
            fresh.show_id.as_str(),
            fresh.episode.as_str(),
            fresh.mode.as_str(),
        ) {
            entries.push(existing);
        }
    }
    let list = PyList::empty_bound(py);
    for entry in entries.iter().take(limit) {
        list.append(item_to_dict(py, entry)?)?;
    }
    updated.set_item("anime_history", list)?;
    Ok(updated.into_py(py))
}

#[pyfunction]
fn remove_anime_history_item_py(
    py: Python<'_>,
    config: &Bound<'_, PyDict>,
    show_id: &str,
    episode: &str,
    mode: &str,
) -> PyResult<PyObject> {
    let updated = config.copy()?;
    let list = PyList::empty_bound(py);
    for item in history_items(config)? {
        if (
            item.show_id.as_str(),
            item.episode.as_str(),
            item.mode.as_str(),
        ) != (show_id, episode, mode)
        {
            list.append(item_to_dict(py, &item)?)?;
        }
    }
    updated.set_item("anime_history", list)?;
    Ok(updated.into_py(py))
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(load_config_py, m)?)?;
    m.add_function(wrap_pyfunction!(anime_history_from_config_py, m)?)?;
    m.add_function(wrap_pyfunction!(set_anime_history_item_py, m)?)?;
    m.add_function(wrap_pyfunction!(remove_anime_history_item_py, m)?)?;
    Ok(())
}
