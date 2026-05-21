#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import plantuml


BASE_SERVER = "https://www.plantuml.com/plantuml"
SUPPORTED_SUFFIXES = {".puml", ".plantuml", ".uml"}
SUPPORTED_FORMATS = {"png", "svg", "pdf"}
INLINE_CLASS_RE = re.compile(r"^(class\s+\S+\s*\{\s*)([^{}]+?)(\s*\}\s*)$")


def build_server_url(base_server: str, output_format: str) -> str:
    endpoint = "img" if output_format == "png" else output_format
    return f"{base_server.rstrip('/')}/{endpoint}/"


def normalize_inline_class_bodies(text: str) -> str:
    normalized_lines: list[str] = []

    for line in text.splitlines():
        match = INLINE_CLASS_RE.match(line.strip())
        if not match:
            normalized_lines.append(line)
            continue

        prefix, body, suffix = match.groups()
        members = [token for token in body.split() if token]
        normalized_lines.append(prefix.rstrip())
        normalized_lines.extend(f"  {member}" for member in members)
        normalized_lines.append(suffix.lstrip())

    return "\n".join(normalized_lines) + ("\n" if text.endswith("\n") else "")


def iter_sources(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() in SUPPORTED_SUFFIXES else []
    if path.is_dir():
        return [
            source
            for source in sorted(path.iterdir())
            if source.is_file() and source.suffix.lower() in SUPPORTED_SUFFIXES
        ]
    return []


def export_sources(path: Path, server: str, output_format: str) -> tuple[list[Path], list[str]]:
    client = plantuml.PlantUML(url=server)
    outputs: list[Path] = []
    errors: list[str] = []

    for source in iter_sources(path):

        text = source.read_text(encoding="utf-8")
        variants = [text]
        normalized = normalize_inline_class_bodies(text)
        if normalized != text:
            variants.append(normalized)

        response = None
        content = b""
        last_error = ""

        for variant in variants:
            url = client.get_url(variant)

            try:
                response, content = client.http.request(url, **client.request_opts)
            except client.HttpLib2Error as exc:
                last_error = f"connection error: {exc}"
                response = None
                continue

            if response.status == 200:
                break

            body = content.decode("utf-8", errors="replace")[:400].replace("\n", " ")
            last_error = f"HTTP {response.status}: {body}"
        else:
            errors.append(f"{source.name}: {last_error}")
            continue

        target = source.with_suffix(f".{output_format}")
        target.write_bytes(content)
        outputs.append(target)

    return outputs, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Export PlantUML files via PlantUML Server.")
    parser.add_argument("path", type=Path, help="A .puml file or a directory containing .puml files")
    parser.add_argument(
        "--format",
        default="png",
        choices=sorted(SUPPORTED_FORMATS),
        help="Output format",
    )
    parser.add_argument(
        "--server",
        default=BASE_SERVER,
        help="PlantUML server base URL, for example https://www.plantuml.com/plantuml",
    )
    args = parser.parse_args()

    path = args.path.expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"Path not found: {path}")

    server = build_server_url(args.server, args.format)
    outputs, errors = export_sources(path, server, args.format)
    if not outputs:
        raise SystemExit("\n".join(errors) if errors else f"No UML files found in: {path}")

    for output in outputs:
        print(output)

    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
