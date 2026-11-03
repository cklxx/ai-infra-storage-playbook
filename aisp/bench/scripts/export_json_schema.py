#!/usr/bin/env python3
"""Generate the JSON Schema files of every type the markdown docs define.

A doc carries its structures as fenced ```bash blocks. The doc is the
directory and each block is a module in it, so a block inside
aisp/bench/checkpoint/README.md with module `ckpt_bench` is the module
`aisp.bench.checkpoint.readme.ckpt_bench`, resolved against the project
directory as VIBA_PATH. The script writes those modules into a temporary tree,
converts every type, and writes one <Type>.schema.json per type to the
json_schema/ directory beside the doc.

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
REPO = Path(__file__).resolve().parents[3]
SCHEMA_DIR = "json_schema"
FENCE = re.compile(r"^```bash[ \t]*(\w*)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
DEFINITION = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*) *=(?!=)", re.M)
SKIPPED = ("a function is no JSON value", "has no argument")


def module_path(doc: Path) -> list[str]:
    parts = list(doc.relative_to(REPO).with_suffix("").parts)
    parts[-1] = parts[-1].lower()
    for part in parts:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part):
            raise SystemExit(f"{doc}: {part!r} cannot be a module name")
    return parts


def modules_by_doc() -> dict[Path, dict[str, tuple[str, str]]]:
    found: dict[Path, dict[str, tuple[str, str]]] = {}
    seen: dict[str, Path] = {}
    for doc in sorted(ROOT.rglob("*.md")):
        blocks = FENCE.findall(doc.read_text(encoding="utf-8"))
        if not blocks:
            continue
        base = module_path(doc)
        modules: dict[str, tuple[str, str]] = {}
        for module, source in blocks:
            if not module:
                raise SystemExit(f"{doc}: a viba block has no module name")
            fqn = ".".join(base + [module])
            if fqn in seen:
                raise SystemExit(f"module {fqn} is defined twice: {seen[fqn]} and {doc}")
            seen[fqn] = doc
            modules[module] = (fqn, source)
        found[doc] = modules
    return found


def main() -> int:
    docs = modules_by_doc()
    if not docs:
        print("no viba block under the bench", file=sys.stderr)
        return 1

    written: dict[Path, set[str]] = {}
    failures = 0
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        for _doc, modules in docs.items():
            for _module, (fqn, source) in modules.items():
                path = repo / (fqn.replace(".", "/") + ".viba")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")

        for doc, modules in docs.items():
            directory = doc.parent / SCHEMA_DIR
            for _module, (fqn, source) in modules.items():
                for name in DEFINITION.findall(source):
                    answer = convert_to_json_schema(
                        [str(repo)], ("type_names", [f"{fqn}.{name}"]))
                    if not isinstance(answer, Ok):
                        message = str(answer.msg)
                        if any(marker in message for marker in SKIPPED):
                            continue
                        print(f"{doc.name}: {fqn}.{name}: {message}", file=sys.stderr)
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
