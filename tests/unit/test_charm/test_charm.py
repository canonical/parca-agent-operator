# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.
import tempfile
from contextlib import ExitStack
from pathlib import Path

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.
from unittest.mock import MagicMock, patch

import pytest
from charms.certificate_transfer_interface.v1.certificate_transfer import (
    ProviderApplicationData,
)
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus
from ops.testing import CharmEvents, Relation, State, TCPPort


@pytest.fixture(autouse=True)
def patch_all():
    with ExitStack() as stack:
        stack.enter_context(patch("charm.ParcaAgent._reconcile_config", lambda _: None))
        yield


def assert_blocked_no_store(state: State):
    """Assert the unit is blocked because there is no store relation."""
    assert isinstance(state.unit_status, BlockedStatus)
    assert "No store configured" in state.unit_status.message


@pytest.fixture
def store_relation():
    return Relation(
        "parca-store-endpoint",
        remote_app_data={
            "remote-store-address": "192.0.2.0/24",
            "remote-store-bearer-token": "foo",
        },
    )


@pytest.mark.parametrize(
    "event",
    (
        (CharmEvents().install()),
        (CharmEvents().upgrade_charm()),
        (CharmEvents().update_status()),
    ),
)
@patch("charm.ParcaAgent.install", lambda _: True)
@patch("charm.ParcaAgent.refresh", lambda _: True)
@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.running", True)
@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
def test_happy_path_status(context, event, store_relation):
    # GIVEN the charm's install/refresh exit 0
    # AND GIVEN a remote store relation
    state = State(relations={store_relation})
    # WHEN the charm receives an event
    state_out = context.run(event, state)
    # THEN the charm sets active
    assert isinstance(state_out.unit_status, ActiveStatus)
    assert state_out.workload_version == "v0.12.0"


@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.install", lambda _: True)
@patch("charm.ParcaAgent.refresh", lambda _: True)
@pytest.mark.parametrize(
    "event",
    (
        (CharmEvents().install()),
        (CharmEvents().upgrade_charm()),
        (CharmEvents().update_status()),
    ),
)
def test_store_not_related_set_blocked(context, event):
    # GIVEN there is no store relation
    state_out = context.run(event, State())
    # THEN the charm sets blocked
    assert_blocked_no_store(state_out)


@patch("charm.ParcaAgent.installed", False)
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


@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("parca_agent.ParcaAgent._snap")
def test_update_status_refreshes_snap_hold(snap, context):
    state_out = context.run(context.on.install(), State())
    snap.hold.assert_called_once()
    assert state_out.workload_version == "v0.12.0"


@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.start")
def test_charm_opens_ports_on_start(parca_start, context):
    state_out = context.run(context.on.start(), State())
    parca_start.assert_called_once()
    assert state_out.opened_ports == frozenset({TCPPort(port=7071, protocol="tcp")})


@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.running", True)
@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.start", lambda _: True)
def test_charm_sets_active_on_start_success(context, store_relation):
    state_out = context.run(context.on.start(), State(relations={store_relation}))
    assert isinstance(state_out.unit_status, ActiveStatus)


@patch("charm.ParcaAgent.installed", False)
@patch("charm.ParcaAgent.remove")
def test_remove(parca_stop, context, store_relation):
    state_out = context.run(context.on.remove(), State(relations={store_relation}))
    parca_stop.assert_called_once()
    assert isinstance(state_out.unit_status, BlockedStatus)
    assert "parca-agent snap is not installed" in state_out.unit_status.message


@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.running", True)
@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.install", lambda _: True)
@patch("charm.ParcaAgent.refresh", lambda _: True)
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


@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.running", True)
@pytest.mark.parametrize("remote_data_present", (0, 1))
def test_parca_external_store_relation_removed(context, remote_data_present):
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
        # THEN Parca has no store config
        assert charm.parca_agent._store_config == {}
        state_out = mgr.run()

    # AND THEN we set blocked because we have no store
    assert_blocked_no_store(state_out)


@patch("charm.ParcaAgent._snap", MagicMock())
@patch("subprocess.run", MagicMock())
@patch("charm.ParcaAgent.revision", 2587)
@patch("charm.ParcaAgent.version", "v0.12.0")
@patch("charm.ParcaAgent.installed", True)
@patch("charm.ParcaAgent.running", True)
@patch(
    "parca_agent.CA_CERTS_PATH",
    new_callable=lambda: Path(tempfile.TemporaryDirectory().name),
)
def test_parca_receive_ca_cert(mock_dir, context, store_relation):
    # GIVEN parca-agent is connected to multiple CA transfer providers
    ca_transfer_relation = Relation(
        "receive-ca-cert",
        remote_app_name="ca1",
        remote_app_data=ProviderApplicationData(certificates={"ca1"}).dump(),
    )
    ca_transfer_relation2 = Relation(
        "receive-ca-cert",
        remote_app_name="ca2",
        remote_app_data=ProviderApplicationData(certificates={"ca2"}).dump(),
    )
    # WHEN any event fires
    context.run(
        context.on.relation_changed(ca_transfer_relation),
        State(
            leader=True, relations={store_relation, ca_transfer_relation, ca_transfer_relation2}
        ),
    )

    # THEN CAs are flushed into one ca file
    ca_path = mock_dir / "receive-ca-cert-parca-agent-ca.crt"
    assert ca_path.read_text() == "ca1\n\nca2\n\n"

    # GIVEN A CA transfer provider is broken
    # WHEN a relation broken event fires
    context.run(
        context.on.relation_broken(ca_transfer_relation),
        State(
            leader=True, relations={store_relation, ca_transfer_relation, ca_transfer_relation2}
        ),
    )

    # THEN only 1 CA is flushed into the ca file
    assert ca_path.read_text() == "ca2\n\n"
