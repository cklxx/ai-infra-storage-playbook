#!/usr/bin/env python3
"""Regenerate the JSON Schema section of playbook/ckpt-sample-interface.md.

The doc carries four viba modules (public, apis, types, configs). This script
writes them to a temporary directory, converts every type the public module
exports with viba's convert_to_json_schema, and replaces the trailing
"## json schema" section with one schema per export, titled with the export
name. Function exports are skipped: a function is not a JSON value.

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
SECTION = "## json schema"
MODULES = ("public", "apis", "types", "configs")


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


def render(doc: str, schemas: list[tuple[str, str]]) -> str:
    body = [f"# {SECTION.lstrip('# ').strip()}", ""]
    body.append("由 `scripts/export_json_schema.py` 生成，不要手改。每个 public 导出类型一份，标题就是导出名。")
    body.append("")
    for name, schema in schemas:
        body += [f"`{name}`", "", "```json", schema.rstrip(), "```", ""]
    head = doc.split(SECTION)[0].rstrip()
    return head + "\n\n" + SECTION + "\n\n" + "\n".join(body[2:]).rstrip() + "\n"


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
            titled = OrderedDict()
            titled["$schema"] = schema.pop("$schema")
            titled["title"] = export
            titled.update(schema)
            schemas.append((export, json.dumps(titled, ensure_ascii=False, indent=2)))

    if not schemas:
        print("no type exports to convert", file=sys.stderr)
        return 1
    args.doc.write_text(render(doc, schemas), encoding="utf-8")
    print(f"{args.doc.name}: wrote {len(schemas)} schema(s): {', '.join(name for name, _ in schemas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
