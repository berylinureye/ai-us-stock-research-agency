from __future__ import annotations

import importlib
import unittest


BACKEND_TEST_MODULES = [
    "tests.backend_env_loading_test",
    "tests.backend_pond_test",
    "tests.backend_reference_report_test",
    "tests.backend_fastapi_structure_test",
]


def load_tests(loader: unittest.TestLoader, tests: unittest.TestSuite, pattern: str | None) -> unittest.TestSuite:
    suite = unittest.TestSuite()
    for module_name in BACKEND_TEST_MODULES:
        suite.addTests(loader.loadTestsFromModule(importlib.import_module(module_name)))
    return suite
