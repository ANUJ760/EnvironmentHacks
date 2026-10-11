"""Stable, safe failures shared by ingestion, models and API."""


class TwinError(Exception):
    def __init__(
        self, code: str, detail: str, status: int = 422, missing_inputs: list[str] | None = None
    ):
        super().__init__(detail)
        self.code, self.detail, self.status = code, detail, status
        self.missing_inputs = missing_inputs or []
