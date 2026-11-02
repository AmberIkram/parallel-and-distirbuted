# shared/protocol.py
# Protocol version and compatibility checking

PROTOCOL_VERSION = "1.0"
MIN_COMPATIBLE_VERSION = "1.0"


def is_compatible(version: str) -> bool:
    """Check if a given protocol version is compatible with ours."""
    try:
        major_theirs = int(version.split(".")[0])
        major_ours = int(PROTOCOL_VERSION.split(".")[0])
        return major_theirs == major_ours
    except (ValueError, IndexError):
        return False


def version_tuple(v: str):
    return tuple(int(x) for x in v.split("."))
