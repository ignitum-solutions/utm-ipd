"""Exercise the deployed HTTP path without AWS credentials or stored run data."""
from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.revision = None
        self.assets = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "meta" and attrs.get("name") == "utm-build-revision":
            self.revision = attrs.get("content")
        if tag == "script" and attrs.get("type") == "module":
            self.assets.append(attrs.get("src", ""))
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs.get("href", ""))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def get_json(url):
    with urlopen(url, timeout=60) as response:
        return json.load(response)


def check_stream(base_url, kind, config, revision):
    body = json.dumps(config, separators=(",", ":")).encode()
    request = Request(base_url + "/api/run/" + kind, data=body, headers={
        "Content-Type": "application/json",
        "x-amz-content-sha256": hashlib.sha256(body).hexdigest(),
    })
    started = time.monotonic()
    first_event = None
    result = None
    count = 0
    progress = False
    # POSTs are deliberately never retried: an interrupted run may still execute.
    with urlopen(request, timeout=300) as response:
        require(response.headers.get_content_type() == "application/x-ndjson", "Expected an NDJSON stream.")
        while line := response.readline(8_000_001):
            require(len(line) <= 8_000_000, "Stream event exceeds the size limit.")
            require(time.monotonic() - started < 300, "Stream exceeded the verification deadline.")
            if not line.strip():
                continue
            require(result is None, "Received an event after the terminal result.")
            event = json.loads(line)
            if count == 0:
                require(event.get("type") == "started", "The stream must start with a started event.")
                first_event = time.monotonic() - started
            count += 1
            require(event.get("type") in {"started", "progress", "heartbeat", "result", "error"}, "Unknown stream event.")
            require(event["type"] != "error", "Simulation returned an error: " + event.get("message", "unknown"))
            progress = progress or event["type"] == "progress"
            if event["type"] == "result":
                result = event.get("result")
                require(isinstance(result, dict), "Terminal event has no result.")
    require(result is not None and progress, "Stream ended without progress and a completed result.")
    require(result["kind"] == kind, "Result kind differs from the request.")
    require(result["config"]["seed"] == config["seed"], "Result seed differs from the request.")
    require(result["metadata"]["build_revision"] == revision, "Result uses a different backend revision.")
    require(bool(result["metadata"]["source_file_sha256"]), "Result source hashes are missing.")
    print(f"{kind}: passed; first event {first_event:.2f}s, completed {time.monotonic() - started:.2f}s")


def expect_forbidden(url):
    try:
        with urlopen(url, timeout=30) as response:
            raise RuntimeError(f"Expected denied direct-origin access; received HTTP {response.status}.")
    except HTTPError as exc:
        require(exc.code == 403, f"Expected HTTP 403 from the direct origin; received {exc.code}.")


def verify(base_url, revision, *, api_only=False, protected_function_url=None, bucket=None, region=None):
    health = get_json(base_url + "/api/health")
    require(health.get("status") == "ok" and health.get("version") == revision, "Health reports a different backend revision.")
    catalogue = get_json(base_url + "/api/catalogue")
    require(catalogue.get("version") == revision, "Catalogue reports a different backend revision.")
    require("Defector" in catalogue.get("opponents", []), "Opponent catalogue is unavailable.")
    with urlopen(base_url + "/api/explanation", timeout=60) as response:
        require(b"Universal Trust" in response.read(), "Model guide is unavailable.")
    for kind, config in [
        ("trust", {"rounds": 10, "seed": 42, "betrayal_probability": .3}),
        ("tournament", {"rounds": 6, "repetitions": 1, "opponents": ["Defector"], "seed": 42}),
        ("moran", {"rounds": 5, "generations": 3, "population": 5, "seed": 42}),
    ]:
        check_stream(base_url, kind, config, revision)
    if not api_only:
        with urlopen(base_url + "/", timeout=60) as response:
            page = Page()
            page.feed(response.read().decode())
        require(page.revision == revision, "Frontend and backend revisions differ.")
        require(bool(page.assets), "The page has no built application assets.")
        for asset in page.assets:
            require(asset.startswith("/assets/") and not urlsplit(asset).netloc, "Unexpected application asset URL.")
            with urlopen(base_url + asset, timeout=60) as response:
                require(response.status == 200 and bool(response.read(1)), "Application asset is unavailable.")
        print("frontend: passed; matching revision and application assets")
    if protected_function_url:
        expect_forbidden(protected_function_url)
        print("Lambda origin: unsigned access denied")
    if bucket:
        require(bool(region), "Supply the bucket region for the S3 origin check.")
        expect_forbidden(f"https://{bucket}.s3.{region}.amazonaws.com/site/index.html")
        print("S3 origin: unsigned access denied")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--protected-function-url")
    parser.add_argument("--bucket")
    parser.add_argument("--region")
    args = parser.parse_args()
    url = args.url.rstrip("/")
    require(urlsplit(url).scheme in {"http", "https"}, "Provide an HTTP or HTTPS application URL.")
    verify(url, args.revision, api_only=args.api_only,
           protected_function_url=args.protected_function_url, bucket=args.bucket, region=args.region)


if __name__ == "__main__":
    main()
