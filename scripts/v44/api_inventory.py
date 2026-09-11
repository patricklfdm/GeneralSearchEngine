#!/usr/bin/env python3
"""Generate and compare a deterministic public API inventory with javap."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

SCHEMA = "gse-v44-public-api-inventory-v1"
ANONYMOUS = re.compile(r"\$\d+(?:\$|$)")


class InventoryError(ValueError):
    """A JAR cannot be inventoried or its public API differs."""


def _classes(jar: Path) -> list[str]:
    try:
        with zipfile.ZipFile(jar) as archive:
            names = archive.namelist()
    except (OSError, zipfile.BadZipFile) as failure:
        raise InventoryError("input is not a readable JAR") from failure
    result = []
    for name in names:
        if not name.startswith("io/github/patricklfdm/generalsearch/") \
                or not name.endswith(".class") \
                or name.endswith("module-info.class") \
                or ANONYMOUS.search(name):
            continue
        result.append(name[:-6].replace("/", "."))
    return sorted(result)


def declarations(jar: Path, javap: str = "javap") -> list[str]:
    classes = _classes(jar)
    completed = subprocess.run(
        [javap, "-classpath", str(jar), "-public", "-s", "-constants",
         *classes], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise InventoryError("javap failed while reading public declarations")
    result: list[str] = []
    sections = re.split(r"(?=Compiled from )", completed.stdout)
    for section in sections:
        lines = [" ".join(line.strip().split())
                 for line in section.splitlines()
                 if line.strip() and not line.startswith("Compiled from")]
        if not lines or not lines[0].startswith("public "):
            continue
        match = re.search(
            r"(?:class|interface|enum|record) ([A-Za-z0-9_.$]+)", lines[0])
        if match is None:
            raise InventoryError("cannot identify a public declaration")
        class_name = match.group(1)
        result.append(f"TYPE {class_name}")
        result.append(lines[0])
        result.extend(sorted(lines[1:-1]))
        result.append(lines[-1])
    return result


def generate(jar: Path, javap: str = "javap") -> dict[str, object]:
    inventory = declarations(jar, javap)
    public_types = sum(line.startswith("TYPE ") for line in inventory)
    payload = ("\n".join(inventory) + "\n").encode("utf-8")
    return {
        "schemaVersion": SCHEMA,
        "publicTypeCount": public_types,
        "declarationLineCount": len(inventory),
        "inventorySha256": hashlib.sha256(payload).hexdigest(),
    }


def write_inventory(jar: Path, output: Path, javap: str) -> None:
    value = generate(jar.resolve(), javap)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8")


def compare(jar: Path, expected_path: Path, javap: str) -> None:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    observed = generate(jar.resolve(), javap)
    if observed != expected:
        raise InventoryError(
            "public API differs from frozen published-4.3 inventory: "
            f"expected={expected.get('inventorySha256')} "
            f"observed={observed.get('inventorySha256')}")
    print("v44PublicApiInventory=PASS "
          f"types={observed['publicTypeCount']} "
          f"lines={observed['declarationLineCount']} "
          f"sha256={observed['inventorySha256']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--javap", default="javap")
    commands = parser.add_subparsers(dest="command", required=True)
    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("jar", type=Path)
    generate_parser.add_argument("output", type=Path)
    compare_parser = commands.add_parser("compare")
    compare_parser.add_argument("jar", type=Path)
    compare_parser.add_argument("expected", type=Path)
    arguments = parser.parse_args()
    if arguments.command == "generate":
        write_inventory(arguments.jar, arguments.output, arguments.javap)
    else:
        compare(arguments.jar, arguments.expected, arguments.javap)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InventoryError, OSError, json.JSONDecodeError) as failure:
        print(f"v44PublicApiInventory=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
