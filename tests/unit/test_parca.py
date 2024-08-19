# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

import unittest
from unittest.mock import patch

from charms.operator_libs_linux.v1 import snap

from parca_agent import ParcaAgent


class TestParca(unittest.TestCase):
    @patch("parca_agent.check_output")
    @patch("parca_agent.ParcaAgent.installed", True)
    def test_parca_version_next(self, checko):
        checko.return_value = b"parca-agent, version v0.12.0-next (commit: e888718c206a5dd63d476849c7349a0352547f1a)\n"
        parca_agent = ParcaAgent()
        self.assertEqual(parca_agent.version, "v0.12.0-next+e88871")

    @patch("parca_agent.ParcaAgent.installed", False)
    def test_parca_agent_version_not_installed(self):
        try:
            parca_agent = ParcaAgent()
            parca_agent.version
        except snap.SnapError as e:
            self.assertEqual(str(e), "parca agent snap not installed, cannot fetch version")
