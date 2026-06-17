from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ServiceResult(Generic[T]):
    success: bool
    message: str
    code: str | None = None
    data: T | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "success": self.success,
            "message": self.message,
        }
        if self.code is not None:
            payload["code"] = self.code
        if self.data is not None:
            payload["data"] = _public_data(self.data)
        return payload


def _public_data(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [_public_data(item) for item in value]
    if isinstance(value, tuple):
        return [_public_data(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _public_data(item) for key, item in value.items()}
    return value
