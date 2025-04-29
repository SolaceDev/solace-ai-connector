#!/usr/bin/env python3
"""
Script to run integration tests for Solace AI Connector.
"""

import os
import sys
import argparse
import subprocess


def main():
    """Run integration tests."""
    parser = argparse.ArgumentParser(
        description="Run integration tests for Solace AI Connector"
    )
    parser.add_argument(
        "--test",
        "-t",
        help="Specific test to run (e.g., test_litellm_chat_flow.py or test_litellm_chat_flow.py::TestLiteLLMChatFlow::test_basic_message_flow)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Run tests in verbose mode"
    )
    parser.add_argument(
        "--xvs",
        action="store_true",
        help="Run tests with -xvs flags (exit on first failure, verbose, show output)",
    )

    args = parser.parse_args()

    # Change to the project root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))
    os.chdir(project_root)

    # Build the pytest command
    cmd = ["pytest"]

    if args.xvs:
        cmd.extend(["-xvs"])
    elif args.verbose:
        cmd.extend(["-v"])

    if args.test:
        if "::" in args.test:
            # If the test includes a specific test method
            cmd.append(f"tests/integration/{args.test}")
        else:
            # If only a test file is specified
            cmd.append(f"tests/integration/{args.test}")
    else:
        # Run all integration tests
        cmd.append("tests/integration")

    # Run the tests
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
