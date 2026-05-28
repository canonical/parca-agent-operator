#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests verifying parca-agent deploys correctly on ubuntu@24.04 and ubuntu@22.04."""

import jubilant
import pytest
from jubilant import Juju

PARCA_AGENT = "parca-agent"
AGENT_JAMMY = "parca-agent-jammy"
UBUNTU = "ubuntu-lite"
UBUNTU_APP_NOBLE = "ubuntu-noble"
UBUNTU_APP_JAMMY = "ubuntu-jammy"
NOBLE_BASE = "ubuntu@24.04"
JAMMY_BASE = "ubuntu@22.04"


@pytest.mark.setup
def test_deploy(juju: Juju, charm, charm_jammy):
    """Deploy both noble and jammy parca-agent charms as subordinates (zero units)."""
    juju.deploy(charm, PARCA_AGENT, num_units=0)
    juju.deploy(charm_jammy, AGENT_JAMMY, num_units=0)


def test_noble_with_virt_parca_agent_is_blocked(juju: Juju):
    """Deploy a noble principal with virt-type=virtual-machine; parca-agent should be blocked.

    parca-agent ends up blocked because no parca_store backend is configured.  The snap
    starts successfully on a virtual machine, but without a store the charm stays blocked.
    """
    juju.deploy(
        UBUNTU,
        UBUNTU_APP_NOBLE,
        base=NOBLE_BASE,
        constraints={"virt-type": "virtual-machine"},
    )
    juju.wait(
        lambda status: jubilant.all_active(status, UBUNTU_APP_NOBLE),
        timeout=15 * 60,
        error=lambda status: jubilant.any_error(status, UBUNTU_APP_NOBLE),
        delay=10,
        successes=3,
    )
    juju.integrate(UBUNTU_APP_NOBLE, PARCA_AGENT)
    juju.wait(
        lambda status: jubilant.all_active(status, UBUNTU_APP_NOBLE),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )
    juju.wait(
        lambda status: jubilant.all_blocked(status, PARCA_AGENT),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )


def test_jammy_without_virt_parca_agent_is_blocked(juju: Juju):
    """Deploy a jammy principal WITHOUT virt-type; parca-agent should be blocked.

    On a jammy machine that is not a virtual machine the parca snap fails to start
    due to insufficient permissions, leaving the charm in a blocked state.
    """
    # Remove the noble relation first so parca-agent is free to attach to jammy
    juju.cli("remove-relation", PARCA_AGENT, UBUNTU_APP_NOBLE)

    juju.deploy(UBUNTU, UBUNTU_APP_JAMMY, channel="stable", base=JAMMY_BASE)
    juju.wait(
        lambda status: jubilant.all_active(status, UBUNTU_APP_JAMMY),
        timeout=15 * 60,
        error=lambda status: jubilant.any_error(status, UBUNTU_APP_JAMMY),
        delay=10,
        successes=3,
    )
    juju.integrate(UBUNTU_APP_JAMMY, AGENT_JAMMY)
    juju.wait(
        lambda status: jubilant.all_active(status, UBUNTU_APP_JAMMY),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )
    juju.wait(
        lambda status: jubilant.all_blocked(status, AGENT_JAMMY),
        timeout=10 * 60,
        delay=10,
        successes=3,
    )


@pytest.mark.teardown
def test_remove_relations(juju: Juju):
    juju.cli("remove-relation", AGENT_JAMMY, UBUNTU_APP_JAMMY)


@pytest.mark.teardown
def test_remove_applications(juju: Juju):
    juju.cli("remove-application", PARCA_AGENT)
    juju.cli("remove-application", AGENT_JAMMY)
    juju.cli("remove-application", UBUNTU_APP_NOBLE)
    juju.cli("remove-application", UBUNTU_APP_JAMMY)
