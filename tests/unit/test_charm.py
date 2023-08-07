# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

# This file contains basic tests simply to ensure that the various event handlers for operator
# framework are being called, and that they in turn are invoking the right helpers.
#
# The helpers themselves require too much mocking, and are validated in functional/integration
# tests.


import unittest
from subprocess import CalledProcessError
from types import SimpleNamespace
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

    @patch("charm.ParcaAgentOperatorCharm._open_port")
    @patch("charm.ParcaAgent.start")
    def test_start(self, parca_start, open_port):
        self.harness.charm.on.start.emit()
        parca_start.assert_called_once()
        open_port.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, ActiveStatus())

    @patch("charm.ParcaAgent.remove")
    def test_remove(self, parca_stop):
        self.harness.charm.on.remove.emit()
        parca_stop.assert_called_once()
        self.assertEqual(self.harness.charm.unit.status, MaintenanceStatus("removing parca-agent"))

    @patch("charm.check_call")
    def test_open_port(self, check_call):
        result = self.harness.charm._open_port()
        check_call.assert_called_with(["open-port", "7071/TCP"])
        self.assertTrue(result)

    @patch("charm.check_call")
    def test_open_port_fail(self, check_call):
        check_call.side_effect = CalledProcessError(1, "foo")
        result = self.harness.charm._open_port()
        check_call.assert_called_with(["open-port", "7071/TCP"])
        self.assertFalse(result)

    @patch("charm.ParcaAgent.configure")
    @patch("ops.model.Model.get_binding", lambda *args: MockBinding("10.10.10.10"))
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


class MockBinding:
    def __init__(self, addr):
        self.network = SimpleNamespace(bind_address=addr)
