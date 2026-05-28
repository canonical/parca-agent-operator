# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
from pathlib import Path

from pytest import fixture
from pytest_jubilant import pack

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).parent.parent.parent
OTEL_COLLECTOR_APP_NAME = "opentelemetry-collector"
COS_CHANNEL = "2/edge"


@fixture(scope="module")
def charm():
    """Parca-agent charm (noble/amd64) for jubilant integration tests."""
    if path := os.getenv("CHARM_PATH"):
        logger.info("using charm from env")
        return path
    candidates = list(REPO_ROOT.glob("parca-agent_ubuntu@24.04-amd64.charm"))
    if candidates:
        logger.info(f"using existing charm from {REPO_ROOT}")
        return str(candidates[0])
    logger.info(f"packing from {REPO_ROOT}")

    return pack(REPO_ROOT)


@fixture(scope="module")
def charm_jammy(charm):
    """Parca-agent charm (jammy/amd64) for jubilant integration tests.

    Depends on the ``charm`` fixture to ensure ``charmcraft pack`` has already
    been run (which produces both the noble and jammy ``.charm`` files).
    """
    if path := os.getenv("CHARM_PATH_JAMMY"):
        logger.info("using jammy charm from env")
        return path
    candidates = list(REPO_ROOT.glob("parca-agent_ubuntu@22.04-amd64.charm"))
    if not candidates:
        raise FileNotFoundError(
            "parca-agent_ubuntu@22.04-amd64.charm not found after packing; "
            "check that charmcraft.yaml lists ubuntu@22.04:amd64 as a platform."
        )
    logger.info(f"using existing jammy charm from {REPO_ROOT}")
    return str(candidates[0])
