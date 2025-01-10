#!/usr/bin/env python3
# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Charmed Operator to deploy Parca Agent."""

import logging

import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider, charm_tracing_config
from charms.operator_libs_linux.v1 import snap
from charms.parca.v0.parca_store import (
    ParcaStoreEndpointRequirer,
    RemoveStoreEvent,
)
from charms.tempo_coordinator_k8s.v0.charm_tracing import trace_charm

from parca_agent import ParcaAgent

logger = logging.getLogger(__name__)


@trace_charm(
    tracing_endpoint="charm_tracing_endpoint",
    extra_types=(
        ParcaAgent,
        COSAgentProvider,
        ParcaStoreEndpointRequirer,
    ),
)
class ParcaAgentOperatorCharm(ops.CharmBase):
    """Charmed Operator to deploy Parca - a continuous profiling tool."""

    def __init__(self, *args):
        super().__init__(*args)
        self.parca_agent = ParcaAgent()

        # Enable the option to send profiles to a remote store (i.e. Polar Signals Cloud)
        self._store_requirer = ParcaStoreEndpointRequirer(self)

        # Enable COS Agent
        self._cos_agent = COSAgentProvider(
            self,
            metrics_endpoints=[{"path": "/metrics", "port": 7071}],
            # Currently, parca-agent snap doesn't expose a slot to access its logs.
            # https://github.com/parca-dev/parca-agent/issues/3017
            log_slots=None,
            tracing_protocols=["otlp_http"],
        )
        self.charm_tracing_endpoint, _ = charm_tracing_config(self._cos_agent, None)

        # === EVENT HANDLER REGISTRATION === #
        self.framework.observe(self.on.install, self._install)
        self.framework.observe(self.on.upgrade_charm, self._upgrade_charm)
        self.framework.observe(self.on.start, self._start)
        self.framework.observe(self.on.remove, self._remove)
        self.framework.observe(self.on.update_status, self._update_status)
        self.framework.observe(
            self._store_requirer.on.endpoints_changed, self._on_store_endpoints_changed
        )
        self.framework.observe(self._store_requirer.on.remove_store, self._on_store_removed)

    # === EVENT HANDLERS === #
    def _on_store_removed(self, event):
        """Remove store config."""
        self._configure_store(event)

    def _on_store_endpoints_changed(self, event):
        """Generate store config."""
        self._configure_store(event)

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

    def _configure_store(self, event):
        """Configure remote store with credentials passed over parca-store-endpoint relation."""
        self.unit.status = ops.MaintenanceStatus("reconfiguring parca-agent")
        store_config = {} if isinstance(event, RemoveStoreEvent) else event.store_config
        self.parca_agent.configure(store_config)
        self.unit.status = ops.ActiveStatus()

    def _remove(self, _):
        """Remove Parca Agent from the machine."""
        self.unit.status = ops.MaintenanceStatus("removing parca-agent")
        self.parca_agent.remove()


if __name__ == "__main__":  # pragma: nocover
    ops.main(ParcaAgentOperatorCharm)
