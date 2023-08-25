# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import unittest
from unittest.mock import PropertyMock, patch

import ops.testing
from charm import ParcaAgentOperatorCharm
from charms.operator_libs_linux.v1 import snap
from ops.model import ActiveStatus, BlockedStatus, MaintenanceStatus
from ops.testing import Harness

ops.testing.SIMULATE_CAN_CONNECT = True


class TestCharm(unittest.TestCase):
    def setUp(self):
        self.harness = Harness(ParcaAgentOperatorCharm)
        self.addCleanup(self.harness.cleanup)
        self.harness.add_network("10.10.10.10")
        self.harness.begin()
        self.maxDiff = None

    @patch("charm.ParcaAgent.install", lambda _: True)
    @patch("charm.ParcaAgent.version", "v0.12.0")
    def test_install_success(self):
        self.harness.charm.on.install.emit()
        self.assertEqual(
            self.harness.charm.unit.status, MaintenanceStatus("installing parca-agent")
        )

    @patch("parca_agent.ParcaAgent.install")
    def test_install_fail_(self, install):
        install.side_effect = snap.SnapError("failed installing parca-agent")
        self.harness.charm.on.install.emit()
        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("failed installing parca-agent")
        )

    @patch("charm.ParcaAgent.refresh", lambda _: True)
    def test_upgrade_charm(self):
        self.harness.charm.on.upgrade_charm.emit()
        self.assertEqual(
            self.harness.charm.unit.status, MaintenanceStatus("refreshing parca-agent")
        )

    @patch("parca_agent.ParcaAgent.refresh")
    def test_upgrade_fail_(self, refresh):
        refresh.side_effect = snap.SnapError("failed refreshing parca-agent")
        self.harness.charm.on.upgrade_charm.emit()
        self.assertEqual(
            self.harness.charm.unit.status, BlockedStatus("failed refreshing parca-agent")
        )

    @patch("charm.snap.hold_refresh")
    @patch("parca_agent.ParcaAgent.version", new_callable=PropertyMock(return_value="v0.12.0"))
    def test_update_status(self, _, hold):
        self.harness.charm.on.update_status.emit()
        hold.assert_called_once()
        self.assertEqual(self.harness.get_workload_version(), "v0.12.0")

    @patch("charm.ParcaAgent.start")
    def test_start(self, parca_start):
        self.harness.charm.on.start.emit()
        parca_start.assert_called_once()
        self.assertEqual(
            self.harness.charm.unit.opened_ports(), {ops.OpenedPort(protocol="tcp", port=7071)}
        )
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.ParcaAgent.remove")
    def test_remove(self, parca_stop):
        self.harness.charm.on.remove.emit()
        parca_stop.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("removing parca-agent"))

    @patch("charm.ParcaAgent.configure")
    def test_metrics_endpoint_relation(self, _):
        # Create a relation to an app named "prometheus"
        rel_id = self.harness.add_relation("metrics-endpoint", "prometheus")
        # Add a prometheus unit
        self.harness.add_relation_unit(rel_id, "prometheus/0")
        # Ugly re-init workaround: manually call `set_scrape_job_spec`
        # https://github.com/canonical/operator/issues/736
        self.harness.charm.metrics_endpoint_provider.set_scrape_job_spec()
        # Grab the unit data from the relation
        unit_data = self.harness.get_relation_data(rel_id, self.harness.charm.unit.name)
        # Ensure that the unit set its targets correctly
        expected = {
            "prometheus_scrape_unit_address": "10.10.10.10",
            "prometheus_scrape_unit_name": "parca-agent/0",
        }
        self.assertEqual(unit_data, expected)

    @patch("charm.ParcaAgent.configure")
    def test_parca_external_store_relation(self, configure):
        self.harness.set_leader(True)
        # Create a relation to an app named "polar-signals-cloud"
        rel_id = self.harness.add_relation("parca-store-endpoint", "polar-signals-cloud")
        # Add a polar-signals-cloud unit
        self.harness.add_relation_unit(rel_id, "polar-signals-cloud/0")
        # Set some data from the remote application
        store_config = {
            "remote-store-address": "grpc.polarsignals.com:443",
            "remote-store-bearer-token": "deadbeef",
            "remote-store-insecure": "false",
        }
        self.harness.update_relation_data(rel_id, "polar-signals-cloud", store_config)
        # Ensure that we call the configure method on Parca with the correct store details
        configure.assert_called_with(store_config)
        configure.reset()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

        self.harness.remove_relation(rel_id)
        configure.assert_called_with({})
