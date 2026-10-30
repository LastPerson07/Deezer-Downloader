"""Single exception type for every recoverable Deezer failure."""


class DeezerError(RuntimeError):
    """Invalid session, missing rights, catalog miss, or a failed stream."""
