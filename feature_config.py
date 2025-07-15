# Feature Configuration - OpenType feature management

# Default OpenType features that are typically enabled
DEFAULT_ON_FEATURES = {
    "ccmp",
    "kern",
    "calt",
    "rlig",
    "liga",
    "mark",
    "mkmk",
    "clig",
    "dist",
    "rclt",
    "rvrn",
    "curs",
    "locl",
}

HIDDEN_FEATURES = {
    "init",
    "medi",
    "med2",
    "fina",
    "fin2",
    "fin3",
    "isol",
    "curs",
    "aalt",
    "rand",
}


def filter_visible_features(feature_tags):
    """
    Filter out hidden OpenType features from a list of feature tags.

    Args:
        feature_tags (list): List of OpenType feature tags (strings)

    Returns:
        list: Filtered list with hidden features removed
    """
    return [tag for tag in feature_tags if tag not in HIDDEN_FEATURES]
