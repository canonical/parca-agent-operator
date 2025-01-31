#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio

from pytest import mark
from pytest_operator.plugin import OpsTest

AGENT = "parca-agent"
UBUNTU = "ubuntu-lite"
UBUNTU_APP_JAMMY = "ubuntu-jammy"
UBUNTU_APP_NOBLE = "ubuntu-noble"
UNIT_0 = f"{AGENT}/0"


@mark.abort_on_fail
@mark.skip_if_deployed
@mark.setup
async def test_deploy(ops_test: OpsTest, parca_charm):
    await ops_test.model.deploy(parca_charm, application_name=AGENT, num_units=0)


async def test_agent_running(ops_test: OpsTest):
    # Deploy principal on a virtual-machine with ubuntu@24.04 for parca-agent to start.
    # check https://github.com/canonical/parca-agent-operator/issues/37
    # and https://github.com/canonical/parca-agent-operator/issues/47
    await asyncio.gather(
        ops_test.model.deploy(
            UBUNTU,
            application_name=UBUNTU_APP_NOBLE,
            channel="stable",
            series="noble",
            constraints={"virt-type": "virtual-machine"},
        ),
        ops_test.model.wait_for_idle(apps=[UBUNTU_APP_NOBLE], status="active", timeout=1000),
    )
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.integrate(UBUNTU_APP_NOBLE, AGENT),
            # parca-agent will be in active/idle
            ops_test.model.wait_for_idle(
                apps=[AGENT, UBUNTU_APP_NOBLE], status="active", timeout=500
            ),
        )


async def test_remove_relation(ops_test: OpsTest):
    await ops_test.juju("remove-relation", AGENT, UBUNTU_APP_NOBLE)


async def test_agent_blocked(ops_test: OpsTest):
    await asyncio.gather(
        ops_test.model.deploy(
            UBUNTU,
            application_name=UBUNTU_APP_JAMMY,
            channel="stable",
            series="jammy",
        ),
        ops_test.model.wait_for_idle(apps=[UBUNTU_APP_JAMMY], status="active", timeout=1000),
    )
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.integrate(UBUNTU_APP_JAMMY, AGENT),
            ops_test.model.wait_for_idle(apps=[UBUNTU_APP_JAMMY], status="active", timeout=500),
            # parca-agent will be in blocked state, as the snap failed to start due to permission errors.
            ops_test.model.wait_for_idle(apps=[AGENT], status="blocked", timeout=500),
        )


@mark.teardown
async def test_remove_agent(ops_test: OpsTest):
    await ops_test.model.remove_application(AGENT)


# @mark.abort_on_fail
# @retry(wait=wexp(multiplier=2, min=1, max=30), stop=stop_after_attempt(10), reraise=True)
# async def test_application_is_up(ops_test: OpsTest):
#     status = await ops_test.model.get_status()  # noqa: F821
#     address = status["applications"][UBUNTU]["units"][f"{UBUNTU}/0"]["public-address"]
#     response = requests.get(f"http://{address}:7071/")
#     assert response.status_code == 200
#     response = requests.get(f"http://{address}:7071/metrics")
#     assert response.status_code == 200
