use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

#[pyfunction]
fn seconds_from_timestamp(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    if value.is_none() {
        return Ok(0.0);
    }
    if let Ok(v) = value.extract::<f64>() {
        return Ok(v.max(0.0));
    }
    let text: String = value.extract()?;
    let parts: Vec<&str> = text.split(':').collect();
    let invalid = || PyValueError::new_err(format!("Invalid timestamp: {text:?}"));
    let seconds = match parts.len() {
        1 => parts[0].parse::<f64>().map_err(|_| invalid())?,
        2 => {
            parts[0].parse::<f64>().map_err(|_| invalid())? * 60.0
                + parts[1].parse::<f64>().map_err(|_| invalid())?
        }
        3 => {
            parts[0].parse::<f64>().map_err(|_| invalid())? * 3600.0
                + parts[1].parse::<f64>().map_err(|_| invalid())? * 60.0
                + parts[2].parse::<f64>().map_err(|_| invalid())?
        }
        _ => return Err(invalid()),
    };
    Ok(seconds.max(0.0))
}

#[pyfunction]
#[pyo3(signature = (seconds=None))]
fn format_timestamp(seconds: Option<f64>) -> String {
    let total = seconds.unwrap_or(0.0).max(0.0);
    let hours = (total / 3600.0).floor() as u64;
    let minutes = ((total % 3600.0) / 60.0).floor() as u64;
    let secs = total % 60.0;
    format!("{hours:02}:{minutes:02}:{secs:05.2}")
}

#[pyfunction]
#[pyo3(signature = (duration, interval=30.0, max_count=20))]
fn preview_timestamps(duration: Option<f64>, interval: f64, max_count: usize) -> Vec<f64> {
    let Some(duration) = duration else {
        return Vec::new();
    };
    if duration <= 0.0 || max_count == 0 {
        return Vec::new();
    }
    let step = interval.max(duration / max_count as f64);
    let mut stamps = Vec::new();
    let mut current = 0.0;
    while current < duration && stamps.len() < max_count {
        stamps.push((current * 1000.0).round() / 1000.0);
        current += step;
    }
    let rounded_duration = (duration * 1000.0).round() / 1000.0;
    if !stamps.contains(&rounded_duration) {
        stamps.push(rounded_duration);
    }
    stamps.truncate(max_count + 1);
    stamps
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(seconds_from_timestamp, m)?)?;
    m.add_function(wrap_pyfunction!(format_timestamp, m)?)?;
    m.add_function(wrap_pyfunction!(preview_timestamps, m)?)?;
    Ok(())
}
