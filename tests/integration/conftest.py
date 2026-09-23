# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import re
import subprocess
from pathlib import Path

from pytest import fixture

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
OTEL_COLLECTOR_APP_NAME = "opentelemetry-collector"
COS_CHANNEL = "2/edge"


def _pack_charm(root: Path, platform: str) -> str:
    """Pack the charm for the given platform and return the path to the built .charm file."""
    result = subprocess.run(
        ["charmcraft", "pack", "-p", str(root), "--platform", platform],
        check=True,
        capture_output=True,
        text=True,
    )
    # charmcraft reports packed files on stderr: "Packed <filename>"
    for line in result.stderr.strip().splitlines():
        if line.startswith("Packed"):
            charm_name = line.split()[1]
            charm_path = root / charm_name
            logger.info(f"packed charm at {charm_path}")
            return str(charm_path)
    raise RuntimeError(
        f"charmcraft pack did not report a packed charm. stderr: {result.stderr}"
    )


@fixture(scope="module")
def charm():
    """Parca-agent charm (noble/amd64) for jubilant integration tests."""
    if path := os.getenv("CHARM_PATH"):
        logger.info("using charm from env")
        return re.sub(r"ubuntu@\d+\.\d+", "ubuntu@24.04", path)
    candidates = list(REPO_ROOT.glob("parca-agent_ubuntu@24.04-amd64.charm"))
    if candidates:
        logger.info(f"using existing charm from {REPO_ROOT}")
        return str(candidates[0])
    logger.info(f"packing from {REPO_ROOT}")
    return _pack_charm(REPO_ROOT, "ubuntu@24.04:amd64")


@fixture(scope="module")
def charm_jammy():
    """Parca-agent charm (jammy/amd64) for jubilant integration tests."""
    if path := os.getenv("CHARM_PATH_JAMMY"):
        logger.info("using jammy charm from env")
        return path
    if path := os.getenv("CHARM_PATH"):
        logger.info("using jammy charm from env")
        return re.sub(r"ubuntu@\d+\.\d+", "ubuntu@22.04", path)
    candidates = list(REPO_ROOT.glob("parca-agent_ubuntu@22.04-amd64.charm"))
    if candidates:
        logger.info(f"using existing jammy charm from {REPO_ROOT}")
        return str(candidates[0])
    logger.info(f"packing from {REPO_ROOT}")
    return _pack_charm(REPO_ROOT, "ubuntu@22.04:amd64")
