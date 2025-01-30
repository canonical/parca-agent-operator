# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


from unittest.mock import patch

import pytest
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import CharmEvents, Relation, State
from scenario import TCPPort


@pytest.fixture(autouse=True)
def patch_reconcile():
    with patch("charm.ParcaAgent.reconcile", lambda _: None):
        yield


@patch("charm.ParcaAgent.install", lambda _: True)
@patch("charm.ParcaAgent.refresh", lambda _: True)
@patch("charm.ParcaAgent.running", True)
@pytest.mark.parametrize(
    "event",
    (
        (CharmEvents().install()),
        (CharmEvents().upgrade_charm()),
    ),
)
def test_happy_path_status(context, event):
    # verify that if the charm's install/refresh exit 0, the charm sets active
    state_out = context.run(event, State())
    assert isinstance(state_out.unit_status, ActiveStatus)


@pytest.mark.parametrize("error_message", ("foobar", "something went wrong"))
@pytest.mark.parametrize(
    "event",
    (
        CharmEvents().install(),
        CharmEvents().upgrade_charm(),
    ),
)
@patch("charm.ParcaAgent.running", False)
@patch("parca_agent.ParcaAgent.install")
@patch("parca_agent.ParcaAgent.refresh")
def test_snap_operation_error_set_blocked(install, refresh, context, event, error_message):
    # verify that if the snap commands error out, the charm sets
    # blocked
    install.side_effect = snap.SnapError(error_message)
    refresh.side_effect = snap.SnapError(error_message)
    state_out = context.run(event, State())
    assert isinstance(state_out.unit_status, BlockedStatus)


@patch("parca_agent.ParcaAgent._snap")
def test_update_status_refreshes_snap_hold(snap, context):
    state_out = context.run(context.on.install(), State())
    snap.hold.assert_called_once()
    assert state_out.workload_version == "v0.12.0"


@patch("charm.ParcaAgent.start")
def test_charm_opens_ports_on_start(parca_start, context):
    state_out = context.run(context.on.start(), State())
    parca_start.assert_called_once()
    assert state_out.opened_ports == frozenset({TCPPort(port=7071, protocol="tcp")})


@patch("charm.ParcaAgent.running", True)
@patch("charm.ParcaAgent.start")
def test_charm_sets_active_on_start_success(_, context):
    state_out = context.run(context.on.start(), State())
    assert isinstance(state_out.unit_status, ActiveStatus)


@patch("charm.ParcaAgent.running", True)
@patch("charm.ParcaAgent.remove")
def test_remove(parca_stop, context):
    state_out = context.run(context.on.remove(), State())
    parca_stop.assert_called_once()
    assert isinstance(state_out.unit_status, ActiveStatus)


@patch("charm.ParcaAgent.running", True)
def test_parca_external_store_relation_join(context):
    # GIVEN we are leader and have a store relation
    store_config = {
        "remote-store-address": "grpc.polarsignals.com:443",
        "remote-store-bearer-token": "deadbeef",
        "remote-store-insecure": "false",
    }

    store_relation = Relation(
        "parca-store-endpoint", "polar-signals-cloud", remote_app_data=store_config
    )
    # WHEN we receive a relation-changed event
    with context(
        context.on.relation_changed(store_relation), State(leader=True, relations={store_relation})
    ) as mgr:
        charm = mgr.charm
        # THEN Parca has the correct store details
        assert charm.parca_agent._store_config == store_config
        state_out = mgr.run()

    # AND THEN we set active
    assert state_out.unit_status == ActiveStatus()


@patch("charm.ParcaAgent.running", True)
@pytest.mark.parametrize("remote_data_present", (0, 1))
def test_parca_external_store_relation_remove(context, remote_data_present):
    # GIVEN we are leader and are removing a store relation (whether or not the remote data is still there)
    store_config = (
        {
            "remote-store-address": "grpc.polarsignals.com:443",
            "remote-store-bearer-token": "deadbeef",
            "remote-store-insecure": "false",
        }
        if remote_data_present
        else {}
    )

    store_relation = Relation(
        "parca-store-endpoint", "polar-signals-cloud", remote_app_data=store_config
    )
    # WHEN we receive a relation-removed event
    with context(
        context.on.relation_broken(store_relation),
        State(leader=True, relations={store_relation}),
    ) as mgr:
        charm = mgr.charm
        # THEN Parca has empty store details
        assert charm.parca_agent._store_config == {
            "remote-store-address": "grpc.polarsignals.com:443",
            "remote-store-bearer-token": "",
            "remote-store-insecure": "false",
        }
        state_out = mgr.run()

    # AND THEN we set active
    assert state_out.unit_status == ActiveStatus()
