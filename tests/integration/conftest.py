# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import shlex
from pathlib import Path
from subprocess import check_call
from typing import List

from pytest import fixture

logger = logging.getLogger(__name__)


@fixture(scope="module")
async def build_charms():
    """Build the parca charms used for integration testing."""
    if not os.environ.get("CHARM_PATH"):  # if no charm is passed, pack it
        check_call(shlex.split("charmcraft pack -v"))
    charms = [f"./{path}" for path in Path(".").glob("*.charm")]
    logger.info(f"packed {charms}")
    return charms


def _find_charm(built: List[str], version: str):
    charm = [c for c in built if version in c]
    if not charm:
        raise FileNotFoundError(f"charm for {version} not found in built charms: {built!r}")
    return charm[0]


@fixture(scope="module")
def parca_charm_noble(build_charms):
    """Parca charm with 24.04 base."""
    return _find_charm(build_charms, "24.04")

