#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio

from pytest import mark
from pytest_operator.plugin import OpsTest

AGENT = "parca-agent"
UBUNTU = "ubuntu-lite"
UNIT_0 = f"{AGENT}/0"


@mark.abort_on_fail
@mark.skip_if_deployed
async def test_deploy(ops_test: OpsTest, parca_charm):
    await asyncio.gather(
        ops_test.model.deploy(parca_charm, application_name=AGENT, num_units=0),
        ops_test.model.deploy(
            UBUNTU,
            channel="stable",
            series="jammy",
        ),
        ops_test.model.wait_for_idle(apps=[UBUNTU], status="active", timeout=1000),
    )
    await asyncio.gather(
        ops_test.model.integrate(UBUNTU, AGENT),
        ops_test.model.wait_for_idle(apps=[AGENT, UBUNTU], status="active", timeout=1000),
    )


# @mark.abort_on_fail
# @retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
# async def test_application_is_up(ops_test: OpsTest):
#     status = await ops_test.model.get_status()  # noqa: F821
#     address = status["applications"][UBUNTU]["units"][f"{UBUNTU}/0"]["public-address"]
#     response = requests.get(f"http://{address}:7071/")
#     assert response.status_code == 200
#     response = requests.get(f"http://{address}:7071/metrics")
#     assert response.status_code == 200
