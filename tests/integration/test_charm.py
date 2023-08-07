#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio

from pytest import mark
from pytest_operator.plugin import OpsTest

AGENT = "parca-agent"
UNIT_0 = f"{AGENT}/0"


@mark.abort_on_fail
@mark.skip_if_deployed
async def test_deploy(ops_test: OpsTest, parca_charm):
    await asyncio.gather(
        ops_test.model.deploy(await parca_charm, application_name=AGENT),
        ops_test.model.deploy("ubuntu", channel="stable"),
        ops_test.model.wait_for_idle(apps=[AGENT, "ubuntu"], status="active", timeout=1000),
        ops_test.model.integrate("ubuntu", AGENT),
    )
