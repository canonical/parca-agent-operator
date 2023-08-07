# Copyright 2023 Jon Seager
# See LICENSE file for licensing details.

import unittest
from pathlib import Path
from subprocess import check_call

from parca_agent import ParcaAgent

# DEFAULT_PARCA_CONFIG = {
#     "remote-store-address": "grpc.polarsignals.com:443",
#     "remote-store-bearer-token": "deadbeef",
# }


class TestParcaAgent(unittest.TestCase):
    def setUp(self):
        self.parca_config = ParcaAgent()
        if not self.parca_config.installed:
            self.parca_config.install()

    def test_install(self):
        self.assertTrue(Path("/snap/bin/parca-agent").exists())
        self.assertEqual(check_call(["/snap/bin/parca-agent", "--version"]), 0)

    def test_start(self):
        self.parca_config.start()
        self.assertTrue(self.parca_config.running)
        self.parca_config.remove()

    def test_stop(self):
        self.parca_config.stop()
        self.assertFalse(self.parca_config.running)
        self.parca_config.remove()

    def test_remove(self):
        self.parca_config.remove()
        self.assertFalse(self.parca_config.installed)

    # def test_configure_parca_agent(self):
    #     self.parca_config.configure(DEFAULT_PARCA_CONFIG)
    #     self.assertEqual(
    #         self.parca_config._snap.get("remote-store-address"), "grpc.polarsignals.com:443"
    #     )
    #     self.assertEqual(self.parca_config._snap.get("remote-store-bearer-token"), "deadbeef")
