#!/usr/bin/env python3
# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Charmed Operator to deploy Parca Agent."""

import logging
from typing import Dict, Optional

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
        self.parca_agent = ParcaAgent(self._store_config)

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

    # === STORE CONFIG === #
    @property
    def _store_config(self) -> Optional[Dict[str, str]]:
        return self._store_requirer.config

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
        self.unit.set_ports(7071)

    def _on_remove(self, _):
        """Remove Parca Agent from the machine."""
        self.unit.status = ops.MaintenanceStatus("removing parca-agent")
        self.parca_agent.remove()

    def _on_collect_unit_status(self, event: ops.CollectStatusEvent):
        """Set unit status depending on the state."""
        # by most to least serious issue with the snap, report a blocked status
        if not self._store_config:
            event.add_status(
                ops.BlockedStatus(
                    "No store configured; relate with a `parca_store` provider to start "
                    "sending profiles to a parca backend."
                )
            )
        elif not self.parca_agent.installed:
            event.add_status(
                ops.BlockedStatus(
                    "The parca-agent snap is not installed. "
                    "Check `juju debug-log` for errors during the setup phase."
                )
            )

        # set to blocked if the snap failed to start.
        # it might happen that the snap would take some time before it becomes "inactive".
        # if this happens, the charm will be set to blocked in the next processed event.
        # https://github.com/canonical/parca-agent-operator/issues/56
        elif not self.parca_agent.running:
            event.add_status(
                ops.BlockedStatus(
                    f"The parca-agent snap is not running. "
                    f"Check `juju ssh -m {self.model.name} {self.unit.name} sudo snap logs parca-agent` "
                    f"for errors."
                )
            )
        # We'll only hit the below case if the snap is already installed,
        # but couldn't be refreshed during the upgrade-charm event
        elif (target_revision := self.parca_agent.target_revision) != (current_revision:=self.parca_agent.revision):
            event.add_status(
                ops.BlockedStatus(
                    f"The snap revision {target_revision!r} doesn't match the expected value {current_revision!r}, "
                    f"hinting at an upgrade error."
                    "Check `juju debug-log` for errors."
                )
            )

        event.add_status(ops.ActiveStatus(""))


if __name__ == "__main__":  # pragma: nocover
    ops.main(ParcaAgentOperatorCharm)
