use pyo3::prelude::*;
use std::time::Instant;

const DROP_FRAME_AFTER: f64 = 0.12;

#[pyclass]
pub struct PlaybackClock {
    base_position: f64,
    started_at: Option<Instant>,
    speed: f64,
}

#[pymethods]
impl PlaybackClock {
    #[new]
    fn new() -> Self {
        Self {
            base_position: 0.0,
            started_at: None,
            speed: 1.0,
        }
    }

    #[getter]
    fn position(&self) -> f64 {
        match self.started_at {
            Some(started_at) => {
                self.base_position + started_at.elapsed().as_secs_f64() * self.speed
            }
            None => self.base_position,
        }
    }

    #[getter]
    fn active(&self) -> bool {
        self.started_at.is_some()
    }

    fn start(&mut self) {
        if self.started_at.is_none() {
            self.started_at = Some(Instant::now());
        }
    }
    fn pause(&mut self) {
        if self.started_at.is_some() {
            self.base_position = self.position();
            self.started_at = None;
        }
    }
    fn seek(&mut self, seconds: f64) {
        self.base_position = seconds.max(0.0);
        if self.started_at.is_some() {
            self.started_at = Some(Instant::now());
        }
    }
    fn set_speed(&mut self, speed: f64) {
        let active = self.started_at.is_some();
        self.base_position = self.position();
        self.speed = speed;
        self.started_at = active.then(Instant::now);
    }
    fn reset(&mut self) {
        self.base_position = 0.0;
        self.started_at = None;
    }
}

#[pyclass]
pub struct AudioClock {
    base_position: f64,
    played_samples: u64,
    sample_rate: u32,
    active: bool,
}

#[pymethods]
impl AudioClock {
    #[new]
    fn new() -> Self {
        Self {
            base_position: 0.0,
            played_samples: 0,
            sample_rate: 48000,
            active: false,
        }
    }

    #[getter]
    fn active(&self) -> bool {
        self.active
    }

    #[getter]
    fn position(&self) -> f64 {
        self.base_position + (self.played_samples as f64 / self.sample_rate as f64)
    }

    #[pyo3(signature = (sample_rate, position=0.0))]
    fn start(&mut self, sample_rate: u32, position: f64) {
        self.sample_rate = sample_rate;
        self.base_position = position.max(0.0);
        self.played_samples = 0;
        self.active = true;
    }
    fn advance(&mut self, samples: u64) {
        if self.active {
            self.played_samples += samples;
        }
    }
    fn seek(&mut self, position: f64) {
        self.base_position = position.max(0.0);
        self.played_samples = 0;
    }
    fn stop(&mut self) {
        self.active = false;
    }
    fn reset(&mut self) {
        self.base_position = 0.0;
        self.played_samples = 0;
        self.active = false;
    }
}

#[pyclass(frozen)]
#[derive(Clone)]
pub struct FrameTiming {
    #[pyo3(get)]
    delay: f64,
    #[pyo3(get)]
    should_drop: bool,
}

#[pyfunction]
fn frame_timing_py(frame_timestamp: f64, clock_position: f64) -> FrameTiming {
    let delta = frame_timestamp - clock_position;
    FrameTiming {
        delay: delta.max(0.0),
        should_drop: delta < -DROP_FRAME_AFTER,
    }
}

pub fn register(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PlaybackClock>()?;
    m.add_class::<AudioClock>()?;
    m.add_class::<FrameTiming>()?;
    m.add_function(wrap_pyfunction!(frame_timing_py, m)?)?;
    Ok(())
}
