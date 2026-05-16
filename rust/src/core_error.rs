use thiserror::Error;

#[allow(dead_code)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcessErrorKind {
    UnsupportedCodec,
    InvalidCommand,
    ProcessError,
}

#[allow(dead_code)]
#[derive(Debug, Error)]
pub enum CoreError {
    #[error("args must not be empty")]
    EmptyArgs,
    #[error("executable not found: {0}")]
    ExecutableNotFound(String),
    #[error("process timed out after {timeout} seconds")]
    Timeout { args: Vec<String>, timeout: f64 },
    #[error("process failed with exit code {returncode}")]
    ProcessFailed {
        args: Vec<String>,
        returncode: i32,
        stdout: String,
        stderr: String,
        kind: ProcessErrorKind,
    },
    #[error("invalid ffprobe JSON: {0}")]
    InvalidProbeJson(String),
    #[error("invalid timestamp: {0}")]
    InvalidTimestamp(String),
    #[error("io error: {0}")]
    Io(String),
}
