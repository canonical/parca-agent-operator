# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Control Parca Agent on a host system. Provides a Parca Agent class."""

import logging
from subprocess import check_output

from charms.operator_libs_linux.v1 import snap
from charms.parca.v0.parca_config import parse_version

logger = logging.getLogger(__name__)


class ParcaAgent:
    """Class representing Parca Agent on a host system."""

    def install(self):
        """Install the Parca Agent snap package."""
        try:
            self._snap.ensure(snap.SnapState.Latest, channel="edge")
            snap.hold_refresh()
        except snap.SnapError as e:
            logger.error("could not install parca agent. Reason: %s", e.message)
            logger.debug(e, exc_info=True)
            raise e

    def refresh(self):
        """Refresh the Parca Agent snap if there is a new revision."""
        # The operation here is exactly the same, so just call the install method
        self.install()

    def start(self):
        """Start and enable Parca Agent using the snap service."""
        self._snap.start(enable=True)

    def stop(self):
        """Stop Parca Agent using the snap service."""
        self._snap.stop(disable=True)

    def remove(self):
        """Remove the Parca Agent snap, preserving config and data."""
        self._snap.ensure(snap.SnapState.Absent)

    def configure(self, app_config, restart=True):
        """Configure Parca Agent on the host system. Restart Parca Agent by default."""
        self._snap.set({"remote-store-address": app_config["remote-store-address"]})

        if app_config["remote-store-bearer-token"]:
            self._snap.set({"remote-store-bearer-token": app_config["remote-store-bearer-token"]})

        # Restart the snap service
        if restart:
            self._snap.restart()

    @property
    def installed(self):
        """Report if the Parca Agent snap is installed."""
        return self._snap.present

    @property
    def running(self):
        """Report if the 'parca-agent-svc' snap service is running."""
        return self._snap.services["parca-agent-svc"]["active"]

    @property
    def version(self) -> str:
        """Report the version of Parca Agent currently installed."""
        if self.installed:
            results = check_output(["parca-agent", "--version"]).decode()
            return parse_version(results)
        raise snap.SnapError("parca agent snap not installed, cannot fetch version")

    @property
    def _snap(self):
        """Return a representation of the Parca Agent snap."""
        cache = snap.SnapCache()
        return cache["parca-agent"]
