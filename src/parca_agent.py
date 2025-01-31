# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Control Parca Agent on a host system. Provides a Parca Agent class."""

import logging
import platform
from subprocess import check_output
from typing import Dict, Optional, Tuple

from charms.operator_libs_linux.v1 import snap
from charms.parca_k8s.v0.parca_config import parse_version

logger = logging.getLogger(__name__)


def get_system_arch() -> str:
    """Return the architecture of this machine, mapping some values to amd64 or arm64.

    If platform is x86_64 or amd64, it returns amd64.
    If platform is aarch64, arm64, armv8b, or armv8l, it returns arm64.
    """
    arch = platform.processor()
    if arch in ["x86_64", "amd64"]:
        arch = "amd64"
    elif arch in ["aarch64", "arm64", "armv8b", "armv8l"]:
        arch = "arm64"
    # else: keep arch as is
    return arch


ARCH = get_system_arch()


class SnapSpecError(snap.SnapError):
    """Custom exception type for errors related to the snap spec."""

    pass


class ParcaAgent:
    """Class representing Parca Agent on a host system."""

    _snap_revisions: Dict[Tuple[str, str], int] = {
        # (confinement, arch): revision
        ("classic", "amd64"): 2587,  # v0.35.3
    }
    _confinement = "classic"

    def __init__(self, store_config: Dict[str, str]):
        self._store_config = store_config

    # RECONCILERS
    def reconcile(self):
        """Parca agent reconcile logic."""
        self._reconcile_config()

    def _reconcile_config(
        self,
    ):
        """Configure Parca Agent on the host system.

        Restart Parca Agent snap if needed.
        """
        changes = {}
        for key in ("remote-store-address", "remote-store-insecure", "remote-store-bearer-token"):
            desired_value = self._store_config.get(key, "")
            current_value = self._snap.get(key)
            if current_value != desired_value:
                changes[key] = desired_value

        # Restart the snap service
        if changes:
            self._snap.set(changes)
            self._snap.restart()

    def install(self):
        """Install the Parca Agent snap package."""
        if not self.target_revision:
            raise SnapSpecError(
                f"parca-agent snap is not supported for arch={ARCH} and confinement={self._confinement}."
            )

        try:
            self._snap.ensure(
                state=snap.SnapState.Present, revision=self.target_revision, classic=True
            )
        except snap.SnapError as e:
            raise e
        self._snap.hold()

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

    @property
    def target_revision(self) -> Optional[int]:
        """The snap revision we want to install."""
        return self._snap_revisions.get((self._confinement, ARCH), None)

    @property
    def installed(self) -> bool:
        """Report if the Parca Agent snap is installed."""
        return self._snap.present

    @property
    def running(self) -> bool:
        """Report if the 'parca-agent-svc' snap service is running."""
        if self.installed:
            try:
                return self._snap.services["parca-agent-svc"]["active"]
            except KeyError as e:
                logger.exception("Failed to get parca-agent snap state %s", str(e))
        return False

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

    @property
    def revision(self):
        """The currently installed revision of the parca-agent snap."""
        return self._snap.revision
