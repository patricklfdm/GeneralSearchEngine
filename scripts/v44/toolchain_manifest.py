#!/usr/bin/env python3
"""Validate the frozen V4.4 canonical release-toolchain identity."""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS = {"m": "http://maven.apache.org/POM/4.0.0"}
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class ToolchainError(ValueError):
    """The canonical toolchain is incomplete or differs from repository inputs."""


def _pom_properties(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    properties = root.find("m:properties", NS)
    if properties is None:
        raise ToolchainError(f"properties absent: {path}")
    return {node.tag.rsplit("}", 1)[-1]: (node.text or "").strip()
            for node in properties}


def validate(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as failure:
        raise ToolchainError("toolchain manifest is not valid JSON") from failure
    if value.get("schemaVersion") != "gse-v44-release-toolchain-v1" \
            or value.get("status") != "CANONICAL_IDENTITY_FROZEN":
        raise ToolchainError("toolchain identity differs")
    container = value.get("container", {})
    for field in ("indexDigest", "platformDigest", "baseDigest"):
        if DIGEST.fullmatch(str(container.get(field))) is None:
            raise ToolchainError(f"container {field} is not pinned")
    if value.get("architecture") != "linux/amd64" \
            or value.get("java") != {
                "distribution": "Eclipse Temurin", "feature": 21,
                "fullVersion": "21.0.12+8"}:
        raise ToolchainError("Java or architecture identity differs")
    wrapper = value.get("mavenWrapper", {})
    wrapper_properties = {}
    for line in (ROOT / ".mvn/wrapper/maven-wrapper.properties").read_text(
            encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, item = line.split("=", 1)
            wrapper_properties[key] = item
    for manifest_key, repo_key in (
            ("distributionUrl", "distributionUrl"),
            ("distributionSha256Sum", "distributionSha256Sum"),
            ("wrapperVersion", "wrapperVersion")):
        if wrapper.get(manifest_key) != wrapper_properties.get(repo_key):
            raise ToolchainError(f"Maven Wrapper {manifest_key} differs")
    if wrapper.get("canonicalAcquisition") \
            != "host-download-read-only-mount" \
            or wrapper.get("canonicalExtraction") != "jdk-jar" \
            or wrapper.get("canonicalInvocation") != "direct-maven-binary":
        raise ToolchainError("canonical Maven bootstrap differs")
    core = _pom_properties(ROOT / "pom.xml")
    processor = _pom_properties(ROOT / "general-search-engine-processor/pom.xml")
    mappings = {
        "centralPublishing": "central.publishing.maven.plugin.version",
        "compiler": "maven.compiler.plugin.version",
        "deploy": "maven.deploy.plugin.version",
        "gpg": "maven.gpg.plugin.version",
        "jar": "maven.jar.plugin.version",
        "javadoc": "maven.javadoc.plugin.version",
        "source": "maven.source.plugin.version",
    }
    plugins = value.get("plugins", {})
    for name, property_name in mappings.items():
        observed = core.get(property_name, processor.get(property_name))
        if plugins.get(name) != observed:
            raise ToolchainError(f"plugin identity differs: {name}")
    artifacts = value.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 8 \
            or len(set(artifacts)) != 8 \
            or value.get("canonicalJarCount") != 6 \
            or value.get("canonicalPomCount") != 2:
        raise ToolchainError("canonical artifact inventory differs")
    environment = value.get("environment", {})
    if environment.get("locale") != "C.UTF-8" \
            or environment.get("timezone") != "UTC" \
            or environment.get("umask") != "0022" \
            or environment.get("cleanWorkspace") is not True:
        raise ToolchainError("canonical environment is incomplete")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    value = validate(parser.parse_args().manifest.resolve())
    print("v44ReleaseToolchain=PASS "
          f"image={value['container']['platformDigest']} "
          f"java={value['java']['fullVersion']} artifacts=8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ToolchainError as failure:
        print(f"v44ReleaseToolchain=FAIL reason={failure}", file=sys.stderr)
        raise SystemExit(2) from failure
