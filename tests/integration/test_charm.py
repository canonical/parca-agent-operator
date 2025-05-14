#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio

from pytest import mark
from pytest_operator.plugin import OpsTest

PARCA_AGENT = "parca-agent"
AGENT_JAMMY = "parca-agent-jammy"
UBUNTU = "ubuntu-lite"
UBUNTU_APP_NOBLE = "ubuntu-noble"
UBUNTU_APP_JAMMY = "ubuntu-jammy"
NOBLE_BASE = "ubuntu@24.04"
JAMMY_BASE = "ubuntu@22.04"


@mark.abort_on_fail
@mark.skip_if_deployed
@mark.setup
async def test_deploy(ops_test: OpsTest, parca_charm_noble, parca_charm_jammy):
    await asyncio.gather(
        ops_test.model.deploy(parca_charm_noble,
                              application_name=PARCA_AGENT,
                              num_units=0),
        ops_test.model.deploy(parca_charm_jammy,
                              application_name=AGENT_JAMMY,
                              num_units=0)
    )


async def test_deploy_on_noble_with_virt(ops_test: OpsTest):
    # Deploy principal on a virtual-machine with ubuntu@24.04 for parca-agent to start.
    await asyncio.gather(
        ops_test.model.deploy(
            UBUNTU,
            application_name=UBUNTU_APP_NOBLE,
            base="ubuntu@24.04",
            constraints={"virt-type": "virtual-machine"},
        ),
        ops_test.model.wait_for_idle(apps=[UBUNTU_APP_NOBLE], status="active", timeout=1000),
    )
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.integrate(UBUNTU_APP_NOBLE, PARCA_AGENT),
            ops_test.model.wait_for_idle(
                apps=[UBUNTU_APP_NOBLE], status="active", timeout=500
            ),
            # parca-agent will be in blocked because there's no remote store backend configured
            ops_test.model.wait_for_idle(
                apps=[PARCA_AGENT], status="blocked", timeout=500
            )
        )


async def test_remove_relation_noble(ops_test: OpsTest):
    await ops_test.juju("remove-relation", PARCA_AGENT, UBUNTU_APP_NOBLE)


async def test_deploy_on_jammy_no_virt(ops_test: OpsTest):
    await asyncio.gather(
        ops_test.model.deploy(
            UBUNTU,
            application_name=UBUNTU_APP_JAMMY,
            channel="stable",
            base=JAMMY_BASE,
        ),
        ops_test.model.wait_for_idle(apps=[UBUNTU_APP_JAMMY], status="active", timeout=1000),
    )
    async with ops_test.fast_forward():
        await asyncio.gather(
            ops_test.model.integrate(UBUNTU_APP_JAMMY, AGENT_JAMMY),
            ops_test.model.wait_for_idle(apps=[UBUNTU_APP_JAMMY], status="active", timeout=500),
            # parca-agent will be in blocked state, as the snap failed to start due to permission errors.
            ops_test.model.wait_for_idle(apps=[AGENT_JAMMY], status="blocked", timeout=500),
        )


@mark.teardown
async def test_remove_relation_jammy(ops_test: OpsTest):
    # unjam
    await ops_test.juju("remove-relation", AGENT_JAMMY, UBUNTU_APP_JAMMY)


@mark.teardown
async def test_remove_agents(ops_test: OpsTest):
    await ops_test.model.remove_application(PARCA_AGENT)
    await ops_test.model.remove_application(AGENT_JAMMY)
