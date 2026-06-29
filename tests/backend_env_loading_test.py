import os
import tempfile
import unittest
from pathlib import Path

from backend.app.core import config


class BackendEnvLoadingTest(unittest.TestCase):
    def setUp(self):
        self.original_env = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_env_file_overrides_inherited_local_key_by_default(self):
        os.environ["OPENAI_API_KEY"] = "test-inherited-bad-key"

        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("OPENAI_API_KEY=test-dotenv-good-key\n", encoding="utf-8")

            config.load_env_file(env_path)

        self.assertEqual(os.environ["OPENAI_API_KEY"], "test-dotenv-good-key")


if __name__ == "__main__":
    unittest.main()
