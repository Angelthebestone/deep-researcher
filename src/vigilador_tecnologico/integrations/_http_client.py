from typing import Any, Optional, Type

import httpx


class AsyncHttpClient:
    _instance: Optional["AsyncHttpClient"] = None

    def __new__(cls) -> "AsyncHttpClient":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._client = httpx.AsyncClient(
                http2=True,
                timeout=httpx.Timeout(60.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            cls._instance = instance
        return cls._instance

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            AsyncHttpClient._instance = None


async def async_request_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout: float,
    error_cls: Type[Exception],
    provider_name: str,
) -> dict[str, Any]:
    client = AsyncHttpClient().client
    try:
        response = await client.post(url, json=payload, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as error:
        raise error_cls(
            f"{provider_name} request failed with HTTP {error.response.status_code}: {error.response.text}"
        ) from error
    except httpx.RequestError as error:
        raise error_cls(f"{provider_name} request failed: {error}") from error


def get_http_client() -> AsyncHttpClient:
    return AsyncHttpClient()
