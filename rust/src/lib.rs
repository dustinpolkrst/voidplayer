use pyo3::prelude::*;

mod errors;
mod options;
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
    Ok(())
}
