#!/usr/bin/env python3
"""Regenerate the JSON Schema files of the checkpoint sample interface.

The doc playbook/ckpt-sample-interface.md carries four viba modules (public,
apis, types, configs). This script writes them to a temporary directory,
converts every type the public module exports with viba's
convert_to_json_schema, and writes one file per export to
playbook/json_schema/<export>.schema.json. Function exports are skipped: a
function is not a JSON value.

The doc's last section, "## json schema", only says where the files are; this
script rewrites that section too, so the paragraph never goes stale.

Usage:
    PYTHONPATH=<viba checkout> python3 scripts/export_json_schema.py [--doc PATH]

Exit codes: 0 written, 1 a type cannot be converted, 2 the viba package is missing.
"""

from __future__ import annotations

import argparse
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
DEFAULT_DOC = ROOT / "playbook" / "ckpt-sample-interface.md"
SCHEMA_DIR = "json_schema"
SECTION = "## json schema"
MODULES = ("public", "apis", "types", "configs")
ID_PREFIX = "https://example.com/ai-infra-storage-playbook/aisp/bench/playbook/json_schema"


def read_modules(text: str) -> dict[str, str]:
    found = {}
    for match in re.finditer(r"## (\w+)\n\n(?:.*?)?```bash\n(.*?)```", text, re.S):
        found[match.group(1)] = match.group(2)
    missing = [name for name in MODULES if name not in found]
    if missing:
        raise SystemExit(f"{DEFAULT_DOC.name}: missing viba section(s): {', '.join(missing)}")
    return found


def public_exports(source: str) -> list[tuple[str, str, str]]:
    """(export name, module, definition) for every `Name = module.Definition` line."""
    exports = []
    for match in re.finditer(r"(?m)^([A-Za-z_][A-Za-z0-9_]*) = (\w+)\.([A-Za-z_][A-Za-z0-9_]*)$", source):
        exports.append((match.group(1), match.group(2), match.group(3)))
    if not exports:
        raise SystemExit("public exports no names")
    return exports


def write_modules(directory: Path, modules: dict[str, str]) -> None:
    """Write the doc's modules as viba files, annotations and all.

    A `Hint[{ ... }]` annotation is a unit of the type layer: it carries no
    value, so the converter reads past it and the schema is the same with or
    without it. The document keeps them, so the files do too.
    """
    for name, source in modules.items():
        (directory / f"{name}.viba").write_text(source, encoding="utf-8")


def write_schemas(directory: Path, schemas: list[tuple[str, str]]) -> None:
    """One `<export>.schema.json` per export, and no file for a type gone.

    The files are self-contained: each one repeats the `$defs` its type
    reaches, so a reader can take one file and validate against it alone.
    """
    directory.mkdir(parents=True, exist_ok=True)
    current = {f"{name}.schema.json" for name, _ in schemas}
    for stale in directory.glob("*.schema.json"):
        if stale.name not in current:
            stale.unlink()
    for name, text in schemas:
        (directory / f"{name}.schema.json").write_text(text + "\n", encoding="utf-8")


def render(doc: str) -> str:
    """The doc with its last section cut down to where the files are."""
    body = [
        SECTION,
        "",
        "接口的每个导出类型各有一份 JSON Schema，放在 [`json_schema/`](json_schema/) 下，"
        "文件名是导出名加 `.schema.json`。函数导出没有对应的 JSON 值，不生成文件。",
        "",
        "这些文件由 `scripts/export_json_schema.py` 从本文档的四个模块生成，不要手改。",
        "",
    ]
    head = doc.split(SECTION)[0].rstrip()
    return head + "\n\n" + "\n".join(body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC)
    args = parser.parse_args()

    doc = args.doc.read_text(encoding="utf-8")
    modules = read_modules(doc)
    exports = public_exports(modules["public"])

    schemas: list[tuple[str, str]] = []
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary)
        write_modules(repo, modules)
        for export, module, definition in exports:
            answer = convert_to_json_schema([str(repo)], ("type_names", [f"{module}.{definition}"]))
            if not isinstance(answer, Ok):
                message = str(answer.msg)
                if "a function is no JSON value" in message:
                    continue
                print(f"{export}: {message}", file=sys.stderr)
                return 1
            schema = json.loads(answer.ok_value, object_pairs_hook=OrderedDict)
            document = OrderedDict()
            document["$schema"] = schema.pop("$schema")
            document["$id"] = f"{ID_PREFIX}/{export}.schema.json"
            document["title"] = export
            document.update(schema)
            schemas.append((export, json.dumps(document, ensure_ascii=False, indent=2)))

    if not schemas:
        print("no type exports to convert", file=sys.stderr)
        return 1
    directory = args.doc.parent / SCHEMA_DIR
    write_schemas(directory, schemas)
    args.doc.write_text(render(doc), encoding="utf-8")
    print(f"{directory.name}/: wrote {len(schemas)} schema(s): {', '.join(name for name, _ in schemas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
