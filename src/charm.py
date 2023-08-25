#!/usr/bin/env python3
# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Charmed Operator to deploy Parca Agent."""

import logging

import ops
from charms.operator_libs_linux.v1 import snap
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider
from parca_agent import ParcaAgent

logger = logging.getLogger(__name__)


class ParcaAgentOperatorCharm(ops.CharmBase):
    """Charmed Operator to deploy Parca - a continuous profiling tool."""

    def __init__(self, *args):
        super().__init__(*args)
        self.parca_agent = ParcaAgent()

        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)
        self.framework.observe(self.on.start, self._start)
        self.framework.observe(self.on.remove, self._remove)
        self.framework.observe(self.on.update_status, self._update_status)

        # The metrics_endpoint_provider enables Parca to be scraped by Prometheus for metrics
        self.metrics_endpoint_provider = MetricsEndpointProvider(
            self, jobs=[{"static_configs": [{"targets": ["*:7071"]}]}]
        )

        self.framework.observe(
            self.on.parca_store_endpoint_relation_changed, self._configure_remote_store
        )

    def _install(self, _):
        """Install dependencies for Parca Agent and ensure initial configs are written."""
        self.unit.status = ops.MaintenanceStatus("installing parca-agent")
        try:
            self.parca_agent.install()
            self.unit.set_workload_version(self.parca_agent.version)
        except snap.SnapError as e:
            self.unit.status = ops.BlockedStatus(str(e))

    def _upgrade_charm(self, _):
        """Ensure the snap is refreshed (in channel) if there are new revisions."""
        self.unit.status = ops.MaintenanceStatus("refreshing parca-agent")
        try:
            self.parca_agent.refresh()
        except snap.SnapError as e:
            self.unit.status = ops.BlockedStatus(str(e))

    def _update_status(self, _):
        """Handle the update status hook (on an interval dictated by model config)."""
        # Ensure the hold is extended to make sure the snap never auto-refreshes
        # out of our control
        snap.hold_refresh()
        self.unit.set_workload_version(self.parca_agent.version)

    def _start(self, _):
        """Start Parca Agent."""
        self.parca_agent.start()
        self.unit.open_port("tcp", 7071)
        self.unit.status = ops.ActiveStatus()

    def _configure_remote_store(self, event):
        """Configure remote store with credentials passed over parca-store-endpoint relation."""
        self.unit.status = ops.MaintenanceStatus("reconfiguring parca-agent")
        rel_data = event.relation.data[event.relation.app]
        rel_keys = ["remote-store-address", "remote-store-bearer-token", "remote-store-insecure"]
        self.parca_agent.configure({k: rel_data.get(k, "") for k in rel_keys})
        self.unit.status = ops.ActiveStatus()

    def _remove(self, _):
        """Remove Parca Agent from the machine."""
        self.unit.status = ops.MaintenanceStatus("removing parca-agent")
        self.parca_agent.remove()


if __name__ == "__main__":  # pragma: nocover
    ops.main(ParcaAgentOperatorCharm)
