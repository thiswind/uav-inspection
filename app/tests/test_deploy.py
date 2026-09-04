"""Portable launcher tests; no dependencies or actual installs required."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import deploy


class DeploymentLauncherTests(unittest.TestCase):
    def test_original_tree_keeps_legacy_data_root(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(deploy, 'ROOT', Path(tmp)), patch.dict(os.environ, {}, clear=True):
            self.assertEqual(deploy.data_directory(), Path(tmp))

    def test_delivery_uses_sibling_data_even_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
            root = Path(tmp) / 'renamed-app'
            root.mkdir()
            (root / 'deployment-layout.json').write_text(json.dumps({'data_directory': '../02-data'}), encoding='utf-8')
            with patch.object(deploy, 'ROOT', root):
                self.assertEqual(deploy.data_directory(), Path(tmp) / '02-data')
                self.assertFalse(deploy.data_directory().exists())

    def test_explicit_override_precedes_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / 'environment-data'
            override = Path(tmp) / 'explicit-data'
            with patch.dict(os.environ, {'UAV_DATA_DIR': str(env_path)}):
                self.assertEqual(deploy.data_directory(), env_path)
                self.assertEqual(deploy.data_directory(str(override)), override)

    def test_environment_does_not_mutate_parent(self):
        with patch.dict(os.environ, {'UAV_DATA_DIR': 'old'}, clear=True):
            env = deploy.environment(Path('new'))
            self.assertEqual(env['UAV_DATA_DIR'], 'new')
            self.assertEqual(os.environ['UAV_DATA_DIR'], 'old')


if __name__ == '__main__':
    unittest.main()
