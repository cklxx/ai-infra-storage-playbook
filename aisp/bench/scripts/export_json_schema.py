#!/usr/bin/env python3
"""Generate the JSON Schema files of every type the markdown docs define.

A doc carries its structures as fenced ```viba blocks; the fence's info string
names the module. This script collects those blocks from every doc under
aisp/bench, converts each type with viba's convert_to_json_schema, and writes
one <Type>.schema.json per type to the json_schema/ directory beside the doc.
Function definitions and generic types are skipped: neither is a JSON value on
its own.

Usage:
    PYTHONPATH=<viba checkout> python3 scripts/export_json_schema.py

Exit codes: 0 written, 1 a type cannot be converted, 2 the viba package is missing.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

try:
    from viba.convert_to_json_schema import convert_to_json_schema
    from viba.type import Ok
except ImportError:  # pragma: no cover - depends on the environment
    print("viba is not importable; put the viba checkout on PYTHONPATH", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCHEMA_DIR = "json_schema"
FENCE = re.compile(r"^```viba[ \t]*(\w*)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
DEFINITION = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*) *=(?!=)", re.M)
SKIPPED = ("a function is no JSON value", "has no argument")


def modules_by_doc() -> dict[Path, dict[str, str]]:
    """{doc: {module name: source}} for every doc that carries a viba block."""
    found: dict[Path, dict[str, str]] = {}
    names: dict[str, Path] = {}
    for doc in sorted(ROOT.rglob("*.md")):
        blocks: dict[str, str] = {}
        for match in FENCE.finditer(doc.read_text(encoding="utf-8")):
            module = match.group(1) or doc.stem.replace("-", "_")
            if module in names or module in blocks:
                raise SystemExit(f"{doc}: module {module!r} is used twice")
            names[module] = doc
            blocks[module] = match.group(2)
        if blocks:
            found[doc] = blocks
    return found


def definitions(source: str) -> list[str]:
    return DEFINITION.findall(source)


def main() -> int:
    docs = modules_by_doc()
    if not docs:
        print("no viba block under the bench", file=sys.stderr)
        return 1

    written: dict[Path, set[str]] = {}
    failures = 0
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        for doc, modules in docs.items():
            for module, source in modules.items():
                (repo / f"{module}.viba").write_text(source, encoding="utf-8")

        for doc, modules in docs.items():
            directory = doc.parent / SCHEMA_DIR
            for module, source in modules.items():
                for name in definitions(source):
                    answer = convert_to_json_schema(
                        [str(repo)], ("type_names", [f"{module}.{name}"]))
                    if not isinstance(answer, Ok):
                        message = str(answer.msg)
                        if any(marker in message for marker in SKIPPED):
                            continue
                        print(f"{doc.name}: {module}.{name}: {message}", file=sys.stderr)
                        failures += 1
                        continue
                    schema = json.loads(answer.ok_value, object_pairs_hook=OrderedDict)
                    document = OrderedDict()
                    document["$schema"] = schema.pop("$schema")
                    document["$id"] = (
                        f"https://example.com/{REPO.name}/"
                        f"{(directory / f'{name}.schema.json').relative_to(REPO).as_posix()}")
                    document["title"] = name
                    document.update(schema)
                    written.setdefault(directory, set()).add(f"{name}.schema.json")
                    target = directory / f"{name}.schema.json"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    if failures:
        return 1
    for directory, names in sorted(written.items()):
        directory.mkdir(parents=True, exist_ok=True)
        for stale in directory.glob("*.schema.json"):
            if stale.name not in names:
                stale.unlink()
        listing = ", ".join(sorted(name.removesuffix(".schema.json") for name in names))
        print(f"{directory.relative_to(ROOT)}/: {len(names)} schema(s): {listing}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
