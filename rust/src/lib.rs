use pyo3::prelude::*;

mod config_store;
mod core_error;
mod errors;
mod options;
mod playback_state;
mod probe;
mod process;
mod progress;
mod thumbnail;
mod timestamp;

#[pymodule]
fn voidplayer_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    process::register(m)?;
    options::register(m)?;
    progress::register(m)?;
    errors::register(m)?;
    probe::register(m)?;
    timestamp::register(m)?;
    thumbnail::register(m)?;
    config_store::register(m)?;
    playback_state::register(m)?;
    Ok(())
}
