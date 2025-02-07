# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
from pathlib import Path
from typing import List

from pytest import fixture
from pytest_operator.plugin import OpsTest

logger = logging.getLogger(__name__)

@fixture(scope="module")
async def build_charms(ops_test: OpsTest):
    """Build the parca charms used for integration testing."""
    await ops_test.build_charm(".", verbosity="verbose")
    charms= list(Path('.').glob("*.charm"))
    logger.info(f"packed {charms}")
    return charms


def _find_charm(built:List[str], version:str):
    charm = [c for c in built if version in str(c)]
    if not charm:
        raise FileNotFoundError(
            f"charm for {version} not found in built charms: {built!r}"
        )
    return charm[0]


@fixture(scope="module")
def parca_charm_noble(build_charms):
    """Parca charm with 24.04 base."""
    return _find_charm(build_charms, "24.04")

@fixture(scope="module")
async def parca_charm_jammy(build_charms):
    """Parca charm with 22.04 base."""
    return _find_charm(build_charms, "22.04")
