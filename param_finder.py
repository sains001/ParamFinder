#!/usr/bin/env python3
"""
ParamFinderPy - mencari parameter pada domain secara ringan.

Gunakan hanya pada domain yang Anda miliki atau punya izin untuk diuji.
Tool ini melakukan crawling terbatas, tidak melakukan eksploitasi, fuzzing agresif,
atau pengiriman payload.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Iterable


USER_AGENT = "ParamFinderPy/1.0 (+authorized parameter discovery)"
DEFAULT_TIMEOUT = 10


@dataclass
class ParameterHit:
    name: str
    source_type: str
    source_url: str
    method: str = "GET"
    action: str = ""


@dataclass
class CrawlResult:
    start_url: str
    visited: list[str] = field(default_factory=list)
    parameters: dict[str, list[ParameterHit]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def add_param(self, hit: ParameterHit) -> None:
        self.parameters.setdefault(hit.name, [])
        existing = {
            (item.source_type, item.source_url, item.method, item.action)
            for item in self.parameters[hit.name]
        }
        key = (hit.source_type, hit.source_url, hit.method, hit.action)
        if key not in existing:
            self.parameters[hit.name].append(hit)


class LinkAndFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.forms: list[dict[str, object]] = []
        self.current_form: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}

        if tag == "a" and attrs_dict.get("href"):
            self.links.append(attrs_dict["href"])
            return

        if tag == "form":
            self.current_form = {
                "method": attrs_dict.get("method", "GET").upper(),
                "action": attrs_dict.get("action", ""),
                "inputs": [],
            }
            self.forms.append(self.current_form)
            return

        if tag in {"input", "textarea", "select", "button"} and self.current_form is not None:
            name = attrs_dict.get("name", "").strip()
            if name:
                self.current_form["inputs"].append(name)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            self.current_form = None


def normalize_start_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("Target kosong.")
    if "://" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("URL harus memakai http atau https.")
    if not parsed.netloc:
        raise ValueError("Domain target tidak valid.")
    path = parsed.path or "/"
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


def same_scope(url: str, root_host: str, include_subdomains: bool) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if include_subdomains:
        return host == root_host or host.endswith("." + root_host)
    return host == root_host


def clean_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc.lower(), parsed.path or "/", "", parsed.query, "")
    )


def request_url(url: str, timeout: int) -> tuple[str, bytes, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8,*/*;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "")
        body = response.read(1_500_000)
        final_url = response.geturl()
        return final_url, body, content_type


def query_parameters(url: str) -> list[str]:
    parsed = urllib.parse.urlparse(url)
    pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    return sorted({name for name, _ in pairs if name})


def discover_js_like_params(body: bytes) -> set[str]:
    text = body.decode("utf-8", errors="ignore")
    found = set()

    patterns = [
        r"[?&]([A-Za-z0-9_.:-]{1,80})=",
        r"(?:params|data|query)\s*[:=]\s*\{([^}]{1,1000})\}",
    ]
    for match in re.finditer(patterns[0], text):
        found.add(match.group(1))

    for match in re.finditer(patterns[1], text):
        block = match.group(1)
        for key in re.findall(r"['\"]?([A-Za-z0-9_.:-]{1,80})['\"]?\s*:", block):
            found.add(key)

    return found


def parse_html(body: bytes) -> LinkAndFormParser:
    parser = LinkAndFormParser()
    parser.feed(body.decode("utf-8", errors="ignore"))
    return parser


def crawl(args: argparse.Namespace) -> CrawlResult:
    start_url = normalize_start_url(args.target)
    parsed_start = urllib.parse.urlparse(start_url)
    root_host = parsed_start.hostname or parsed_start.netloc
    result = CrawlResult(start_url=start_url)

    queue: deque[tuple[str, int]] = deque([(start_url, 0)])
    seen = set()

    while queue and len(result.visited) < args.max_urls:
        url, depth = queue.popleft()
        url = clean_url(url)
        if url in seen:
            continue
        seen.add(url)

        if not same_scope(url, root_host, args.include_subdomains):
            continue

        try:
            final_url, body, content_type = request_url(url, args.timeout)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            result.errors.append(f"{url}: {exc}")
            continue

        final_url = clean_url(final_url)
        result.visited.append(final_url)

        for name in query_parameters(final_url):
            result.add_param(ParameterHit(name=name, source_type="url", source_url=final_url))

        if args.javascript:
            for name in discover_js_like_params(body):
                result.add_param(ParameterHit(name=name, source_type="javascript/text", source_url=final_url))

        if "html" not in content_type.lower():
            time.sleep(args.delay)
            continue

        parser = parse_html(body)
        for form in parser.forms:
            method = str(form.get("method", "GET")).upper()
            action = urllib.parse.urljoin(final_url, str(form.get("action", "")))
            action = clean_url(action)
            for name in form.get("inputs", []):
                result.add_param(
                    ParameterHit(
                        name=str(name),
                        source_type="form",
                        source_url=final_url,
                        method=method,
                        action=action,
                    )
                )

        if depth < args.depth:
            for href in parser.links:
                next_url = urllib.parse.urljoin(final_url, href)
                next_url = clean_url(next_url)
                if next_url not in seen and same_scope(next_url, root_host, args.include_subdomains):
                    queue.append((next_url, depth + 1))

        time.sleep(args.delay)

    return result


def render_text(result: CrawlResult) -> str:
    lines = [
        f"Target       : {result.start_url}",
        f"URL dikunjungi: {len(result.visited)}",
        f"Parameter    : {len(result.parameters)}",
        "",
    ]

    if result.parameters:
        lines.append("Daftar parameter:")
        for name in sorted(result.parameters):
            hits = result.parameters[name]
            types = sorted({hit.source_type for hit in hits})
            lines.append(f"- {name} [{', '.join(types)}]")
            for hit in hits[:3]:
                if hit.source_type == "form":
                    lines.append(f"  form {hit.method} {hit.action} dari {hit.source_url}")
                else:
                    lines.append(f"  {hit.source_url}")
            if len(hits) > 3:
                lines.append(f"  ... {len(hits) - 3} lokasi lain")
    else:
        lines.append("Tidak ada parameter yang ditemukan dari crawl terbatas ini.")

    if result.errors:
        lines.extend(["", f"Error ringan: {len(result.errors)}"])
        for error in result.errors[:5]:
            lines.append(f"- {error}")
        if len(result.errors) > 5:
            lines.append(f"- ... {len(result.errors) - 5} error lain")

    return "\n".join(lines)


def render_json(result: CrawlResult) -> str:
    return json.dumps(
        {
            "target": result.start_url,
            "visited": result.visited,
            "parameter_count": len(result.parameters),
            "parameters": {
                name: [hit.__dict__ for hit in hits]
                for name, hits in sorted(result.parameters.items())
            },
            "errors": result.errors,
        },
        ensure_ascii=False,
        indent=2,
    )


def save_unique_params(result: CrawlResult, path: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for name in sorted(result.parameters):
            handle.write(name + "\n")


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cari nama parameter dari URL, form, dan teks JavaScript pada domain yang diizinkan."
    )
    parser.add_argument("target", help="Domain atau URL target, contoh: https://example.com")
    parser.add_argument("--depth", type=int, default=2, help="Kedalaman crawl link internal.")
    parser.add_argument("--max-urls", type=int, default=100, help="Batas maksimal URL yang dikunjungi.")
    parser.add_argument("--delay", type=float, default=0.25, help="Jeda antar request dalam detik.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout request dalam detik.")
    parser.add_argument("--include-subdomains", action="store_true", help="Ikuti subdomain dari domain target.")
    parser.add_argument("--javascript", action="store_true", help="Cari pola parameter sederhana di teks/JavaScript.")
    parser.add_argument("--json", action="store_true", help="Tampilkan output JSON.")
    parser.add_argument("--save", help="Simpan nama parameter unik ke file.")
    return parser.parse_args(list(argv))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.depth < 0 or args.max_urls < 1 or args.delay < 0:
        print("Argumen depth, max-urls, dan delay harus bernilai valid.", file=sys.stderr)
        return 2

    try:
        result = crawl(args)
    except ValueError as exc:
        print(f"Input salah: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Dibatalkan.", file=sys.stderr)
        return 130

    if args.save:
        save_unique_params(result, args.save)

    print(render_json(result) if args.json else render_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
