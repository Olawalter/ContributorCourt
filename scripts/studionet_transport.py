"""Retry transport failures to the hosted StudioNet RPC - and nothing else.

The public endpoint drops connections mid-flight (TLS
SSLV3_ALERT_BAD_RECORD_MAC, resets), serves CDN 502 HTML pages instead of
JSON, and rate-limits bursts (-32429). Aborting on one of those while
polling a receipt strands an already-submitted transaction. A JSON-RPC
error that is a real answer (a revert, an unknown method) is never retried.

Re-sending is safe: a raw transaction is signed before it is sent, so its
nonce and hash are fixed and a repeat is the same transaction.

    import studionet_transport  # noqa: F401  (patches genlayer-py on import)
"""

import time

import requests
from genlayer_py.exceptions import GenLayerError
from genlayer_py.provider.provider import GenLayerProvider

ATTEMPTS = 8
_original = GenLayerProvider.make_request


def _transient(err: GenLayerError) -> bool:
    text = str(err)
    return (isinstance(err.__cause__, requests.exceptions.RequestException)
            or "returned invalid JSON" in text
            or "code=-32429" in text
            or "code=429" in text)


def _make_request_with_retry(self, method, params):
    delay = 5
    for attempt in range(ATTEMPTS):
        try:
            return _original(self, method, params)
        except GenLayerError as err:
            if not _transient(err) or attempt == ATTEMPTS - 1:
                raise
            print(f"    rpc transient on {method} ({attempt + 1}/{ATTEMPTS}): "
                  f"{str(err)[:90]}; retry in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 60)


if getattr(GenLayerProvider.make_request, "__name__", "") != "_make_request_with_retry":
    GenLayerProvider.make_request = _make_request_with_retry
