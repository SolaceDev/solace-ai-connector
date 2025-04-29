"""Test that all integration test modules can be imported."""

import os
import sys
import importlib.util
import pytest

# Add src to path for imports
sys.path.append("src")


def test_import_all_test_modules():
    """Test that all test modules can be imported."""
    # Get the directory of this file
    test_dir = os.path.dirname(os.path.abspath(__file__))

    # Get all Python files in the directory
    test_files = [
        f
        for f in os.listdir(test_dir)
        if f.endswith(".py") and f.startswith("test_") and f != "test_imports.py"
    ]

    # Try to import each file
    for test_file in test_files:
        module_name = test_file[:-3]  # Remove .py extension
        file_path = os.path.join(test_dir, test_file)

        # Import the module
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check that the module has test classes or test functions
        test_classes = [
            obj
            for name, obj in module.__dict__.items()
            if isinstance(obj, type) and name.startswith("Test")
        ]

        test_functions = [
            obj
            for name, obj in module.__dict__.items()
            if callable(obj) and name.startswith("test_")
        ]

        # Assert that there are either test classes or test functions
        assert (
            len(test_classes) > 0 or len(test_functions) > 0
        ), f"No tests found in {test_file}"

        # If there are test classes, check that they have test methods
        for test_class in test_classes:
            test_methods = [
                method
                for method in dir(test_class)
                if method.startswith("test_") and callable(getattr(test_class, method))
            ]

            assert (
                len(test_methods) > 0
            ), f"No test methods found in {test_class.__name__}"


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
