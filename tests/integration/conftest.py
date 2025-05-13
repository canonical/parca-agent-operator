# Copyright 2021 Canonical Ltd.
# See LICENSE file for licensing details.
import logging
import os
import shlex
from pathlib import Path
from subprocess import check_call

from pytest import fixture

logger = logging.getLogger(__name__)


@fixture(scope="module")
async def parca_charm():
    """Build the parca charms used for integration testing."""
    if not os.environ.get("CHARM_PATH"):  # if no charm is passed, pack it
        check_call(shlex.split("charmcraft pack -v"))
    charms = [f"./{path}" for path in Path(".").glob("*.charm")]
    logger.info(f"packed {charms}")
    return charms["24.04"]

