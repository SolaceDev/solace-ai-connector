import unittest
import os
import json
import base64
import gzip
import types
from solace_ai_connector.common.utils import (
    import_from_directories,
    get_subdirectories,
    resolve_config_values,
    import_module,
    invoke_config,
    call_function,
    install_package,
    extract_evaluate_expression,
    call_function_with_params,
    create_lambda_function_for_source_expression,
    get_source_expression,
    get_obj_text,
    ensure_slash_on_end,
    ensure_slash_on_start,
    encode_payload,
    decode_payload,
)


class TestUtils(unittest.TestCase):

    def test_get_subdirectories(self):
        # Setup
        test_dir = "test_dir"
        os.makedirs(test_dir, exist_ok=True)
        sub_dir = os.path.join(test_dir, "sub_dir")
        os.makedirs(sub_dir, exist_ok=True)

        # Test
        subdirectories = get_subdirectories(test_dir)

        # Assert
        self.assertIn(sub_dir, subdirectories)

        # Cleanup
        os.rmdir(sub_dir)
        os.rmdir(test_dir)

    def test_ensure_slash_on_end(self):
        self.assertEqual(ensure_slash_on_end("path/to/dir"), "path/to/dir/")
        self.assertEqual(ensure_slash_on_end("path/to/dir/"), "path/to/dir/")
        self.assertEqual(ensure_slash_on_end(""), "")

    def test_ensure_slash_on_start(self):
        self.assertEqual(ensure_slash_on_start("path/to/dir"), "/path/to/dir")
        self.assertEqual(ensure_slash_on_start("/path/to/dir"), "/path/to/dir")
        self.assertEqual(ensure_slash_on_start(""), "")

    def test_encode_payload(self):
        payload = {"key": "value"}
        encoded = encode_payload(payload, "utf-8", "json")
        self.assertEqual(encoded, json.dumps(payload).encode("utf-8"))

        encoded = encode_payload(payload, "base64", "json")
        self.assertEqual(encoded, base64.b64encode(json.dumps(payload).encode("utf-8")))

        encoded = encode_payload(payload, "gzip", "json")
        self.assertEqual(encoded, gzip.compress(json.dumps(payload).encode("utf-8")))

    def test_decode_payload(self):
        payload = {"key": "value"}
        encoded = json.dumps(payload).encode("utf-8")
        decoded = decode_payload(encoded, "utf-8", "json")
        self.assertEqual(decoded, payload)

        encoded = base64.b64encode(json.dumps(payload).encode("utf-8"))
        decoded = decode_payload(encoded, "base64", "json")
        self.assertEqual(decoded, payload)

        encoded = gzip.compress(json.dumps(payload).encode("utf-8"))
        decoded = decode_payload(encoded, "gzip", "json")
        self.assertEqual(decoded, payload)

    def test_extract_evaluate_expression(self):
        expression, data_type = extract_evaluate_expression(
            "evaluate_expression(1 + 1, int)"
        )
        self.assertEqual(expression, "1 + 1")
        self.assertEqual(data_type, "int")

    def test_get_obj_text(self):
        text = '```json\n{"key": "value"}\n```'
        extracted_text = get_obj_text("json", text)
        self.assertEqual(extracted_text, '\n{"key": "value"}\n')

    def test_call_function(self):
        def sample_function(a, b):
            return a + b

        params = {"positional": [1, 2]}
        result = call_function(sample_function, params, False)
        self.assertEqual(result, 3)

        params = {"keyword": {"a": 1, "b": 2}}
        result = call_function(sample_function, params, False)
        self.assertEqual(result, 3)

    def test_call_function_with_params(self):
        def sample_function(a, b):
            return a + b

        params = {"positional": [1, 2]}
        result = call_function_with_params(
            {}, sample_function, params["positional"], {}
        )
        self.assertEqual(result, 3)

        params = {"keyword": {"a": 1, "b": 2}}
        result = call_function_with_params({}, sample_function, [], params["keyword"])
        self.assertEqual(result, 3)

    def test_create_lambda_function_for_source_expression(self):
        def mock_get_data(expression, data_type=None):
            return eval(expression)

        message = types.SimpleNamespace(get_data=mock_get_data)
        lambda_func = create_lambda_function_for_source_expression("1 + 1", "int")
        result = lambda_func(message)
        self.assertEqual(result, 2)

    def test_get_source_expression(self):
        config_obj = {"source_value": "test_value"}
        result = get_source_expression(config_obj)
        self.assertEqual(result, "static:test_value")

        config_obj = {"source_expression": "test_expression"}
        result = get_source_expression(config_obj)
        self.assertEqual(result, "test_expression")

    def test_install_package(self):
        try:
            install_package("requests")
            import requests
        except ImportError:
            self.fail("install_package failed to install 'requests'")

    def test_invoke_config(self):
        pass

    def test_import_module(self):
        module = import_module("json")
        self.assertIsNotNone(module)
        self.assertTrue(hasattr(module, "loads"))

    def test_resolve_config_values(self):
        pass

    def test_import_from_directories(self):
        pass


if __name__ == "__main__":
    unittest.main()
