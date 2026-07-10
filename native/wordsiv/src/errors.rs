use std::fmt;

#[derive(Debug, Clone)]
pub enum WordsivError {
    Filter(String),
    VocabEmpty(String),
    VocabFormat(String),
    Value(String),
}

impl fmt::Display for WordsivError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Filter(msg) => write!(f, "FilterError: {}", msg),
            Self::VocabEmpty(msg) => write!(f, "VocabEmptyError: {}", msg),
            Self::VocabFormat(msg) => write!(f, "VocabFormatError: {}", msg),
            Self::Value(msg) => write!(f, "ValueError: {}", msg),
        }
    }
}

impl std::error::Error for WordsivError {}
