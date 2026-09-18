"""Domain exceptions mapped to safe HTTP problem responses."""


class UpstreamServiceError(RuntimeError):
    def __init__(self, service: str, message: str, *, retryable: bool = True):
        super().__init__(message)
        self.service = service
        self.retryable = retryable


class ArtifactError(RuntimeError):
    pass

