import sys
import time
import pytest

sys.path.append("src")

from solace_ai_connector.common.message import Message
from solace_ai_connector.test_utils.utils_for_test_files import (
    create_test_flows,
    dispose_connector,
)
from solace_ai_connector.common.exceptions import SessionNotFoundError


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


def test_session_idle_timeout():
    """
    Tests that an idle session is automatically cleaned up after its timeout expires.
    """
    config = {
        "flows": [
            {
                "name": "test_timeout_flow",
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
                            # Set a very short timeout for the test
                            "session_timeout_seconds": 1,
                        },
                    }
                ],
            }
        ]
    }

    connector, flows = create_test_flows(config)
    component = flows[0]["flow"].component_groups[0][0]

    try:
        # 1. Create a session
        session_id = component.create_request_response_session()
        assert len(component.list_request_response_sessions()) == 1

        # 2. Wait for longer than the session timeout.
        # The cleanup thread checks at intervals, so wait a bit longer to be safe.
        time.sleep(2)

        # 3. Verify the session has been cleaned up
        assert len(component.list_request_response_sessions()) == 0

        # 4. Verify using the expired session raises an error
        with pytest.raises(SessionNotFoundError):
            component.do_broker_request_response(
                Message(payload="test"), session_id=session_id
            )

    finally:
        dispose_connector(connector)
