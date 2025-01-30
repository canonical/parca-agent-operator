#!/usr/bin/env python3
# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Charmed Operator to deploy Parca Agent."""

import logging

import ops
from charms.grafana_agent.v0.cos_agent import COSAgentProvider, charm_tracing_config
from charms.operator_libs_linux.v1 import snap
from charms.parca_k8s.v0.parca_store import (
    ParcaStoreEndpointRequirer,
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

        # === WORKLOADS === #
        self.parca_agent = ParcaAgent(self._store_requirer.config)

        # === EVENT HANDLER REGISTRATION === #
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.start, self._on_start)
        self.framework.observe(self.on.remove, self._on_remove)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_unit_status)

        self._reconcile()

    # === RECONCILERS === #
    def _reconcile(self):
        """Event-independent logic."""
        if self.parca_agent.installed:
            self.parca_agent.reconcile()
            self.unit.set_workload_version(self.parca_agent.version)

    # === EVENT HANDLERS === #

    def _on_install(self, _):
        """Install dependencies for Parca Agent and ensure initial configs are written."""
        self.unit.status = ops.MaintenanceStatus("installing parca-agent")
        try:
            self.parca_agent.install()
        except snap.SnapError as e:
            logger.exception("Failed to install parca-agent snap %s", str(e))

    def _on_upgrade_charm(self, _):
        """Ensure the snap is refreshed (in channel) if there are new revisions."""
        self.unit.status = ops.MaintenanceStatus("refreshing parca-agent")
        try:
            self.parca_agent.refresh()
        except snap.SnapError as e:
            logger.exception("Failed to refresh parca-agent snap %s", str(e))

    def _on_start(self, _):
        """Start Parca Agent."""
        self.parca_agent.start()
        self.unit.open_port("tcp", 7071)

    def _on_remove(self, _):
        """Remove Parca Agent from the machine."""
        self.unit.status = ops.MaintenanceStatus("removing parca-agent")
        self.parca_agent.remove()

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent):
        """Set unit status depending on the state."""
        if not self.parca_agent.installed:
            event.add_status(
                ops.BlockedStatus(
                    "Failed to install parca-agent snap. Check juju debug-log for errors."
                )
            )

        if not self.parca_agent.running:
            event.add_status(
                ops.BlockedStatus(
                    "parca-agent snap is not running. Check juju debug-log for errors."
                )
            )
        # We'll only hit the below case if the snap is already installed, but failed to refresh.
        elif self.parca_agent.target_revision != self.parca_agent.revision:
            event.add_status(
                ops.BlockedStatus(
                    "Failed to refresh parca-agent snap. Check juju debug-log for errors."
                )
            )

        event.add_status(ops.ActiveStatus(""))


if __name__ == "__main__":  # pragma: nocover
    ops.main(ParcaAgentOperatorCharm)
