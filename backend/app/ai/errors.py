class EmbeddingProviderError(Exception):
    def __init__(
        self,
        message: str,
        *,
        retryable: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.safe_message = message
        self.retryable = retryable
        self.status_code = status_code
