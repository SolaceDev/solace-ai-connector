import sys
import time
import threading
import pytest

sys.path.append("src")

from solace_ai_connector.common.message import Message
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
)
from solace_ai_connector.common.exceptions import (
    SessionNotFoundError,
    SessionLimitExceededError,
    SessionClosedError,
)
from solace_ai_connector.components.inputs_outputs.broker_request_response import (
    BrokerRequestResponse,
)
from solace_ai_connector.common.log import log
import queue


def test_multi_session_lifecycle_and_isolation():
    """
    Tests the basic lifecycle of multi-session request/response:
    - Session creation
    - Independent usage
    - Listing active sessions
    - Session destruction
    - Error on using a destroyed session
    """
    config = {
        "flows": [
            {
                "name": "test_multi_session_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    # Get the component instance directly to call its API
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create two sessions
        session_id_A = component.create_request_response_session()
        session_id_B = component.create_request_response_session(
            session_config_overrides={
                "request_expiry_ms": 60000  # Custom config for this session
            }
        )
        assert session_id_A != session_id_B

        # 2. Use both sessions independently
        message_A = Message(payload={"data": "A"})
        response_A = component.do_broker_request_response(
            message_A, session_id=session_id_A
        )
        assert response_A.get_payload() == {"data": "A"}

        message_B = Message(payload={"data": "B"})
        response_B = component.do_broker_request_response(
            message_B, session_id=session_id_B
        )
        assert response_B.get_payload() == {"data": "B"}

        # 3. List sessions and verify status
        sessions = component.list_request_response_sessions()
        assert len(sessions) == 2
        session_ids_from_list = {s["session_id"] for s in sessions}
        assert session_ids_from_list == {session_id_A, session_id_B}
        for s in sessions:
            assert s["active_request_count"] == 0

        # 4. Destroy one session
        assert component.destroy_request_response_session(session_id_A) is True
        sessions_after_destroy = component.list_request_response_sessions()
        assert len(sessions_after_destroy) == 1
        assert sessions_after_destroy[0]["session_id"] == session_id_B

        # 5. Verify error on using destroyed session
        with pytest.raises(SessionNotFoundError):
            component.do_broker_request_response(message_A, session_id=session_id_A)

        # 6. Verify the other session is still functional
        response_B_again = component.do_broker_request_response(
            message_B, session_id=session_id_B
        )
        assert response_B_again.get_payload() == {"data": "B"}

        # 7. Destroy the second session
        assert component.destroy_request_response_session(session_id_B) is True
        assert len(component.list_request_response_sessions()) == 0

    finally:
        dispose_connector(connector)


def test_max_sessions_limit():
    """Tests that the max_sessions limit is enforced."""
    config = {
        "flows": [
            {
                "name": "test_max_sessions_flow",
                "components": [
                    {
                        "component_name": "session_handler",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "max_sessions": 2,  # Set a low limit
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create sessions up to the limit
        session_id_1 = component.create_request_response_session()
        component.create_request_response_session()
        assert len(component.list_request_response_sessions()) == 2

        # 2. Verify that creating one more session raises an error
        with pytest.raises(SessionLimitExceededError):
            component.create_request_response_session()

        # 3. Destroy a session and verify a new one can be created
        component.destroy_request_response_session(session_id_1)
        assert len(component.list_request_response_sessions()) == 1
        component.create_request_response_session()
        assert len(component.list_request_response_sessions()) == 2

    finally:
        dispose_connector(connector)


def test_backward_compatibility_with_legacy_rrc():
    """
    Tests that do_broker_request_response works correctly with the legacy,
    component-level RRC configuration when no session_id is provided.
    """
    config = {
        "flows": [
            {
                "name": "test_legacy_flow",
                "components": [
                    {
                        "component_name": "legacy_requester",
                        "component_module": "handler_callback",
                        # NOTE: No multi_session_request_response block
                        "broker_request_response": {
                            "enabled": True,
                            "broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # Call do_broker_request_response WITHOUT a session_id
        message = Message(payload={"data": "legacy_test"})
        response = component.do_broker_request_response(message)

        # Verify the response is correct, proving the fallback worked
        assert response.get_payload() == {"data": "legacy_test"}

    finally:
        dispose_connector(connector)


def test_error_on_destroying_active_session(monkeypatch):
    """
    Tests that a thread waiting for a response fails with SessionClosedError
    if the session is destroyed mid-request.
    """
    handler_started = threading.Event()
    handler_should_finish = threading.Event()
    worker_exception = None

    # 1. Create a test-only subclass that blocks in the response path
    class BlockingBrokerRequestResponse(BrokerRequestResponse):
        def handle_test_pass_through(self):
            while not self._local_stop_signal.is_set():
                try:
                    # This is where the worker thread will block
                    message = self.pass_through_queue.get(timeout=1)

                    # Signal to the main thread that we are now blocking
                    handler_started.set()
                    # Wait until the main thread tells us to continue
                    handler_should_finish.wait(timeout=5)

                    # After being unblocked, process the response as normal
                    decoded_payload = self.decode_payload(message.get_payload())
                    message.set_payload(decoded_payload)
                    self.process_response(message)
                except queue.Empty:
                    continue
                except Exception as e:
                    log.error("Error in blocking test passthrough.", trace=e)

    # 2. Use monkeypatch to replace the real component with our blocking one
    monkeypatch.setattr(
        "solace_ai_connector.flow.flow.import_module",
        lambda module, base_path, component_package: (
            __import__(
                "solace_ai_connector.components.inputs_outputs.broker_request_response"
            ).components.inputs_outputs.broker_request_response
            if module == "broker_request_response"
            else sys.modules["solace_ai_connector.common.utils"].import_module(
                module, base_path, component_package
            )
        ),
    )
    monkeypatch.setattr(
        "solace_ai_connector.components.inputs_outputs.broker_request_response.BrokerRequestResponse",
        BlockingBrokerRequestResponse,
    )

    config = {
        "flows": [
            {
                "name": "test_blocking_flow",
                "components": [
                    {
                        "component_name": "requester_component",
                        "component_module": "handler_callback",
                        "multi_session_request_response": {
                            "enabled": True,
                            "default_broker_config": {
                                "broker_type": "test",
                                "broker_url": "test",
                                "broker_username": "test",
                                "broker_password": "test",
                                "broker_vpn": "test",
                            },
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    def worker_thread_task(session_id):
        nonlocal worker_exception
        try:
            message = Message(payload={"data": "wait_for_it"})
            # This call will block inside our patched component
            component.do_broker_request_response(message, session_id=session_id)
        except Exception as e:
            worker_exception = e

    try:
        # 3. Create a session
        session_id = component.create_request_response_session()

        # 4. Start a worker thread to make a blocking request
        worker = threading.Thread(target=worker_thread_task, args=(session_id,))
        worker.start()

        # 5. Wait for the handler to signal that it's blocking
        assert handler_started.wait(timeout=5), "Handler did not start in time"

        # 6. Destroy the session while the worker is waiting for a response
        component.destroy_request_response_session(session_id)

        # 7. Join the worker thread and check for the expected exception
        worker.join(timeout=5)
        assert not worker.is_alive(), "Worker thread did not terminate"
        assert isinstance(worker_exception, SessionClosedError)

    finally:
        # Unblock the handler so its thread can terminate cleanly
        handler_should_finish.set()
        dispose_connector(connector)


