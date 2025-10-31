#!/usr/bin/env python3
"""Quick smoke test for the Email API service used by the iOS Email Test App.

Run this script after starting the FastAPI server to confirm the health endpoint
and the `POST /send-email` flow are working. The script uses environment variables
(or CLI flags) so you can keep credentials out of source control.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import uuid

DEFAULT_BASE_URL = "http://localhost:8002"
DEFAULT_SUBJECT = "Email API smoke test"
DEFAULT_MESSAGE = (
    "Hello from the Email API smoke test!\n"
    "If you're seeing this email, the end-to-end pipeline is healthy."
)
DEFAULT_FROM_NAME = "Email Test App"


def _default_cache_path() -> Path:
    return Path.home() / ".email_api_bootstrap.json"


def _resolve_cache_path(config: SmokeTestConfig) -> Path:
    if config.cache_file is not None:
        return config.cache_file.expanduser()
    return _default_cache_path()


def load_cached_bootstrap(config: SmokeTestConfig, verbose: bool) -> Optional[Dict[str, str]]:
    if config.disable_cache:
        return None

    cache_path = _resolve_cache_path(config)
    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r", encoding="utf-8") as fh:
            cache_data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        if verbose:
            print(f"⚠️ Could not read cache file {cache_path}: {exc}")
        return None

    entry = cache_data.get(config.base_url)
    if not entry:
        return None

    api_key = entry.get("api_key")
    device_id = entry.get("device_id")
    if not api_key or not device_id:
        return None

    if verbose:
        print(f"🔁 Reusing cached bootstrap key for {config.base_url}")

    return {
        "api_key": api_key,
        "device_id": device_id,
        "username": entry.get("username", "")
    }


def save_cached_bootstrap(config: SmokeTestConfig, payload: Dict[str, str], verbose: bool) -> None:
    if config.disable_cache:
        return

    cache_path = _resolve_cache_path(config)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        if cache_path.exists():
            with cache_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = {}
    except (OSError, json.JSONDecodeError):
        data = {}

    data[config.base_url] = {
        "api_key": payload.get("api_key", ""),
        "device_id": payload.get("device_id", ""),
        "username": payload.get("username", ""),
    }

    try:
        tmp_path = cache_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp_path.replace(cache_path)
    except OSError as exc:
        if verbose:
            print(f"⚠️ Failed to write cache file {cache_path}: {exc}")
        return

    if verbose:
        print(f"💾 Cached bootstrap key at {cache_path}")


@dataclass
class SmokeTestConfig:
    base_url: str
    api_key: Optional[str]
    to_email: Optional[str]
    subject: str
    message: str
    from_name: Optional[str]
    timeout: float = 10.0
    bootstrap: bool = False
    device_id: Optional[str] = None
    display_name: Optional[str] = None
    cache_file: Optional[Path] = None
    disable_cache: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "SmokeTestConfig":
        cache_path: Optional[Path] = args.cache_file
        if cache_path is None:
            env_cache = os.getenv("EMAIL_API_BOOTSTRAP_CACHE")
            if env_cache:
                cache_path = Path(env_cache).expanduser()

        return cls(
            base_url=args.base_url.rstrip("/"),
            api_key=args.api_key,
            to_email=args.to_email,
            subject=args.subject,
            message=args.message,
            from_name=args.from_name,
            timeout=args.timeout,
            bootstrap=args.bootstrap,
            device_id=args.device_id,
            display_name=args.display_name,
            cache_file=cache_path,
            disable_cache=args.no_cache,
        )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test for the Email API service")
    parser.add_argument(
        "--base-url",
        default=os.getenv("EMAIL_API_BASE_URL", DEFAULT_BASE_URL),
        help=f"Email API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("EMAIL_API_KEY"),
        help="Client API key for X-API-Key header (required for /send-email)",
    )
    parser.add_argument(
        "--to-email",
        default=os.getenv("EMAIL_API_TEST_RECIPIENT"),
        help="Recipient email address for send-email test",
    )
    parser.add_argument(
        "--subject",
        default=os.getenv("EMAIL_API_TEST_SUBJECT", DEFAULT_SUBJECT),
        help="Subject for the test email",
    )
    parser.add_argument(
        "--message",
        default=os.getenv("EMAIL_API_TEST_MESSAGE", DEFAULT_MESSAGE),
        help="Body content for the test email",
    )
    parser.add_argument(
        "--from-name",
        default=os.getenv("EMAIL_API_FROM_NAME", DEFAULT_FROM_NAME),
        help="Optional from_name to include in the request",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("EMAIL_API_TIMEOUT", 10.0)),
        help="Request timeout in seconds",
    )
    parser.add_argument(
        "--skip-email",
        action="store_true",
        help="Skip the send-email step and run health/config checks only",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full responses for debugging",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Call /client/bootstrap to mint a temporary API key when --api-key is omitted",
    )
    parser.add_argument(
        "--device-id",
        default=os.getenv("EMAIL_API_DEVICE_ID"),
        help="Optional device_id to send with bootstrap request (default: auto-generated UUID)",
    )
    parser.add_argument(
        "--display-name",
        default=os.getenv("EMAIL_API_DISPLAY_NAME"),
        help="Optional display_name to send with bootstrap request",
    )
    parser.add_argument(
        "--cache-file",
        type=Path,
        default=None,
        help="Path to cache bootstrap keys (default: ~/.email_api_bootstrap.json)",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable reading/writing cached bootstrap keys",
    )
    return parser.parse_args(argv)


def http_get(url: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8")
            if "application/json" in content_type:
                return json.loads(body)
            return {"raw": body}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc


def http_post_json(
    url: str,
    payload: Dict[str, Any],
    timeout: float,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Content-Type", "application/json")
    if headers:
        for key, value in headers.items():
            request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {url} failed: {exc.code} {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"POST {url} failed: {exc.reason}") from exc


def bootstrap_api_key(config: SmokeTestConfig, verbose: bool) -> str:
    device_id = config.device_id or os.getenv("EMAIL_API_DEVICE_ID")
    if not device_id:
        device_id = uuid.uuid4().hex

    payload: Dict[str, Any] = {"device_id": device_id}
    if config.display_name:
        payload["display_name"] = config.display_name

    if verbose:
        print(f"🔐 Bootstrapping client key with payload: {json.dumps(payload)}")

    response = http_post_json(
        f"{config.base_url}/client/bootstrap",
        payload=payload,
        timeout=config.timeout,
    )

    api_key = response.get("api_key")
    if not api_key:
        raise RuntimeError(f"Bootstrap response missing api_key: {response}")

    if verbose:
        print(f"✅ Received bootstrap key for username {response.get('username')}")

    config.api_key = api_key
    config.device_id = device_id
    save_cached_bootstrap(
        config,
        {
            "api_key": api_key,
            "device_id": device_id,
            "username": response.get("username", ""),
        },
        verbose=verbose,
    )
    return api_key


def run_smoke_test(config: SmokeTestConfig, verbose: bool) -> int:
    print(f"🔍 Checking Email API at {config.base_url}…")
    health = http_get(f"{config.base_url}/health", timeout=config.timeout)
    status = http_get(f"{config.base_url}/config/status", timeout=config.timeout)

    if verbose:
        print("Health response:", json.dumps(health, indent=2))
        print("Config status:", json.dumps(status, indent=2))
    else:
        print(f"✅ Health: {health}")
        print(f"✅ Config: {status}")

    if not config.to_email:
        print("ℹ️ Skipping send-email test (no recipient provided).")
        return 0

    if config.api_key is None:
        if config.bootstrap:
            cached = load_cached_bootstrap(config, verbose=verbose)
            if cached:
                config.api_key = cached["api_key"]
                config.device_id = cached.get("device_id")
                if verbose and cached.get("username"):
                    print(f"✅ Using cached key for {cached['username']}")

        if config.api_key is None and config.bootstrap:
            print("ℹ️ No API key provided. Attempting bootstrap…")
            bootstrap_api_key(config, verbose=verbose)
        elif config.api_key is None:
            raise ValueError("EMAIL_API_KEY (or --api-key) is required when testing send-email")

    payload = {
        "to_email": config.to_email,
        "subject": config.subject,
        "message": config.message,
    }
    if config.from_name:
        payload["from_name"] = config.from_name

    print(f"📤 Sending test email to {config.to_email}…")
    result = http_post_json(
        f"{config.base_url}/send-email",
        payload=payload,
        timeout=config.timeout,
        headers={"X-API-Key": config.api_key},
    )

    print(f"✅ Email enqueued: {json.dumps(result, indent=2)}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.skip_email:
        args.to_email = None

    config = SmokeTestConfig.from_args(args)

    try:
        return run_smoke_test(config, verbose=args.verbose)
    except Exception as exc:  # noqa: BLE001 - top-level exception handler
        print(f"❌ Smoke test failed: {exc}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
