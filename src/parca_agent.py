# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

"""Control Parca Agent on a host system. Provides a Parca Agent class."""

import logging
import platform
import subprocess
from pathlib import Path
from subprocess import CalledProcessError, check_output
from typing import Dict, Optional, Set, Tuple, cast

from charms.operator_libs_linux.v1 import snap

logger = logging.getLogger(__name__)

CA_CERTS_PATH = Path("/usr/local/share/ca-certificates")


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

    def __init__(
        self, app_name: str, store_config: Optional[Dict[str, str]], certificates: Set[str]
    ):
        self._app_name = app_name
        self._store_config = store_config
        self._certificates = certificates

    # RECONCILERS
    def reconcile(self):
        """Parca agent reconcile logic."""
        if self._store_config:
            self._reconcile_certs()
            self._reconcile_config()
        else:
            logger.error("no store configured: cannot reconcile parca_agent")

    def _reconcile_certs(self):
        """Configure certs, which are transferred from a certificate_transfer provider, on disk."""
        changes = False
        # TODO: is app_name enough to avoid collisions with other charms' certs?
        combined_ca_path = CA_CERTS_PATH / f"receive-ca-cert-{self._app_name}-ca.crt"
        if self._certificates:
            combined_ca = "".join(cert + "\n\n" for cert in sorted(self._certificates))
            current_combined_ca = combined_ca_path.read_text() if combined_ca_path.exists() else ""
            if current_combined_ca != combined_ca:
                logger.debug("Updating CA file with a new set of certificates.")
                combined_ca_path.parent.mkdir(parents=True, exist_ok=True)
                combined_ca_path.write_text(combined_ca)
                self._update_ca_certs()
                changes = True
        else:
            if combined_ca_path.exists():
                logger.debug("Deleting CA file since no certificates were transferred.")
                combined_ca_path.unlink()
                self._update_ca_certs()
                changes = True

        if changes:
            # parca-agent needs to stop and restart for it to notice the change in CAs
            self._snap.stop()
            self._snap.start()

    def _reconcile_config(
        self,
    ):
        """Configure Parca Agent on the host system.

        Restart Parca Agent snap if needed.

        Assumes it only will get called if _store_config is set (i.e. if a remote-store relation is active).
        """
        store_config = cast(Dict[str, str], self._store_config)
        changes = {}
        for key in ("remote-store-address", "remote-store-insecure", "remote-store-bearer-token"):
            desired_value = store_config.get(key, "")
            current_value = self._snap.get(key)
            if current_value != desired_value:
                changes[key] = desired_value

        # Restart the snap service
        if changes:
            self._snap.set(changes)
            self._snap.restart()

    def _update_ca_certs(self):
        try:
            subprocess.run(["update-ca-certificates", "--fresh"])
        except CalledProcessError as e:
            logger.warning(f"Failed to run update-ca-certificates: {e}")

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


def parse_version(vstr: str) -> str:
    """Parse the output of 'parca --version' and return a representative string."""
    parts = vstr.split(" ")
    # If we're not on a 'proper' released version, include the first few digits of
    # the commit we're build from - e.g. 0.12.1-next+deadbeef
    if "-next" in parts[2]:
        return f"{parts[2]}+{parts[4][:6]}"
    return parts[2]
