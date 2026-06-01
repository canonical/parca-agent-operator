from contextlib import ExitStack
from unittest.mock import patch

import pytest
from ops.testing import Context

from charm import ParcaAgentOperatorCharm


@pytest.fixture
def mock_ca_cert(tmp_path):
    tmp_ca_path = tmp_path / "receive-ca-cert-parca-agent-ca.crt"
    with patch("charm._CA_CERT_PATH", tmp_ca_path):
        yield tmp_ca_path


@pytest.fixture
def context():
    return Context(ParcaAgentOperatorCharm)


@pytest.fixture(autouse=True, scope="session")
def patch_all():
    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "parca_agent.check_output",
                new=lambda _: b"parca-agent, version v0.12.0 (commit: e888718c206a5dd63d476849c7349a0352547f1a)\n",
            )
        )
        stack.enter_context(
            patch(
                "charms.operator_libs_linux.v1.snap.Snap.present",
                True,
            )
        )
        stack.enter_context(
            patch(
                "charm.ParcaAgent.target_revision",
                "1",
            )
        )
        stack.enter_context(
            patch(
                "charm.ParcaAgent.revision",
                "1",
            )
        )
        stack.enter_context(
            patch(
                "charm.ParcaAgent.running",
                True,
            )
        )

        yield
