"""Tests for the RequestResponseFlowController class"""

import sys
import pytest
import threading
import queue
import time

sys.path.append("src")

from solace_ai_connector.flow.request_response_flow_controller import (
    RequestResponseFlowController,
    RequestResponseControllerOuputComponent,
)
from solace_ai_connector.solace_ai_connector import SolaceAiConnector
from solace_ai_connector.common.message import Message
from solace_ai_connector.common.event import Event, EventType


class MockConnector:
    """Mock connector for testing"""
    
    def __init__(self):
        self.apps = []
        self.flows = []
        self.flow_input_queues = {}
        self.stop_signal = threading.Event()
        self.error_queue = queue.Queue()
        self.trace_queue = None
        self.instance_name = "test_instance"
        
    def create_internal_app(self, app_name, flows):
        """Mock implementation of create_internal_app"""
        # Create a mock app
        app = MockApp(app_name, flows)
        self.apps.append(app)
        self.flows.extend(app.flows)
        
        # Add flow input queues
        for flow in app.flows:
            self.flow_input_queues[flow.name] = flow.input_queue
            
        return app


class MockApp:
    """Mock app for testing"""
    
    def __init__(self, name, flows):
        self.name = name
        self.flows = [MockFlow(flow["name"]) for flow in flows]


class MockFlow:
    """Mock flow for testing"""
    
    def __init__(self, name):
        self.name = name
        self.input_queue = queue.Queue()
        self.next_component = None
        
    def get_input_queue(self):
        return self.input_queue
        
    def set_next_component(self, component):
        self.next_component = component
        
    def run(self):
        # Start a thread to process messages
        self.thread = threading.Thread(target=self._process_messages, daemon=True)
        self.thread.start()
        
    def _process_messages(self):
        while True:
            try:
                event = self.input_queue.get(timeout=0.1)
                if self.next_component:
                    # Simulate processing and forward to next component
                    message = event.data
                    # Echo back the message with a small modification
                    message.set_payload(f"Response to: {message.get_payload()}")
                    self.next_component.enqueue(event)
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Error processing message: {e}")


def test_request_response_flow_controller_creation():
    """Test that a RequestResponseFlowController can be created"""
    connector = MockConnector()
    
    config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 5000,
    }
    
    controller = RequestResponseFlowController(config, connector)
    
    # Check that the controller was created correctly
    assert controller.request_expiry_ms == 5000
    assert controller.request_expiry_s == 5.0
    assert controller.flow is not None
    assert controller.input_queue is not None
    assert controller.response_queue is not None
    
    # Check that an internal app was created
    assert len(connector.apps) == 1
    assert connector.apps[0].name == "_internal_broker_request_response_app"
    
    # Check that a flow was created
    assert len(connector.flows) == 1
    assert connector.flows[0].name == "_internal_broker_request_response_flow"


def test_request_response_flow_controller_send_receive():
    """Test that a RequestResponseFlowController can send and receive messages"""
    connector = MockConnector()
    
    config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 5000,
    }
    
    controller = RequestResponseFlowController(config, connector)
    
    # Create a message to send
    message = Message(payload="Test message", topic="test/topic")
    
    # Send the message
    try:
        response = next(controller.do_broker_request_response(message))
        
        # Check that a response was received
        assert response is not None
        assert isinstance(response[0], Message)
        assert response[0].get_payload() == "Response to: Test message"
        assert response[1] is True  # is_last flag
    except Exception as e:
        pytest.fail(f"Error sending/receiving message: {e}")


def test_request_response_flow_controller_streaming():
    """Test that a RequestResponseFlowController can handle streaming responses"""
    connector = MockConnector()
    
    config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 5000,
    }
    
    controller = RequestResponseFlowController(config, connector)
    
    # Create a message to send
    message = Message(payload="Test message", topic="test/topic")
    
    # Modify the flow to send multiple responses
    flow = connector.flows[0]
    
    # Replace the _process_messages method to send multiple responses
    original_process_messages = flow._process_messages
    
    def mock_process_messages():
        try:
            event = flow.input_queue.get(timeout=0.1)
            if flow.next_component:
                # Send multiple responses
                message = event.data
                for i in range(3):
                    response_message = Message(
                        payload=f"Response {i+1} to: {message.get_payload()}",
                        topic=message.get_topic(),
                    )
                    # Set streaming.last_message to True for the last message
                    if i == 2:
                        response_message.set_user_properties({
                            "streaming": {"last_message": True}
                        })
                    response_event = Event(EventType.MESSAGE, response_message)
                    flow.next_component.enqueue(response_event)
                    time.sleep(0.1)  # Small delay between responses
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error processing message: {e}")
    
    flow._process_messages = mock_process_messages
    
    # Start a thread to run the mock process
    thread = threading.Thread(target=mock_process_messages, daemon=True)
    thread.start()
    
    # Send the message and get streaming responses
    try:
        responses = []
        for response, is_last in controller.do_broker_request_response(
            message, stream=True, streaming_complete_expression="input.user_properties:streaming.last_message"
        ):
            responses.append((response, is_last))
            if is_last:
                break
        
        # Check that all responses were received
        assert len(responses) == 3
        assert responses[0][0].get_payload() == "Response 1 to: Test message"
        assert responses[0][1] is None  # is_last is None for first message
        assert responses[1][0].get_payload() == "Response 2 to: Test message"
        assert responses[1][1] is None  # is_last is None for second message
        assert responses[2][0].get_payload() == "Response 3 to: Test message"
        assert responses[2][1] is True  # is_last is True for last message
    except Exception as e:
        pytest.fail(f"Error sending/receiving streaming messages: {e}")


def test_request_response_flow_controller_timeout():
    """Test that a RequestResponseFlowController handles timeouts correctly"""
    connector = MockConnector()
    
    config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 100,  # Very short timeout for testing
    }
    
    controller = RequestResponseFlowController(config, connector)
    
    # Create a message to send
    message = Message(payload="Test message", topic="test/topic")
    
    # Modify the flow to not respond
    flow = connector.flows[0]
    flow._process_messages = lambda: time.sleep(1)  # Do nothing, causing a timeout
    
    # Send the message and expect a timeout
    with pytest.raises(TimeoutError):
        next(controller.do_broker_request_response(message))


def test_request_response_controller_output_component():
    """Test the RequestResponseControllerOuputComponent"""
    # Create a mock controller
    class MockController:
        def __init__(self):
            self.response_queue = queue.Queue()
            self.received_events = []
            
        def enqueue_response(self, event):
            self.received_events.append(event)
            self.response_queue.put(event)
    
    controller = MockController()
    output_component = RequestResponseControllerOuputComponent(controller)
    
    # Create a test event
    message = Message(payload="Test message", topic="test/topic")
    event = Event(EventType.MESSAGE, message)
    
    # Send the event to the output component
    output_component.enqueue(event)
    
    # Check that the event was forwarded to the controller
    assert len(controller.received_events) == 1
    assert controller.received_events[0] is event
    
    # Check that the event was put in the response queue
    assert controller.response_queue.qsize() == 1
    assert controller.response_queue.get() is event


def test_create_broker_request_response_flow_config():
    """Test the create_broker_request_response_flow_config method"""
    config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 5000,
        "custom_option": "custom_value",
    }
    
    connector = MockConnector()
    controller = RequestResponseFlowController(config, connector)
    
    # Call the method
    flow_config = controller.create_broker_request_response_flow_config()
    
    # Check the flow configuration
    assert flow_config["name"] == "_internal_broker_request_response_flow"
    assert len(flow_config["components"]) == 1
    assert flow_config["components"][0]["component_name"] == "_internal_broker_request_response"
    assert flow_config["components"][0]["component_module"] == "broker_request_response"
    
    # Check that the broker config was merged with the controller config
    component_config = flow_config["components"][0]["component_config"]
    assert component_config["broker_url"] == "tcp://localhost:55555"
    assert component_config["broker_username"] == "default"
    assert component_config["broker_password"] == "default"
    assert component_config["broker_vpn"] == "default"
    assert component_config["request_expiry_ms"] == 5000
    assert component_config["custom_option"] == "custom_value"


def test_integration_with_solace_ai_connector():
    """Test integration with the SolaceAiConnector"""
    # Create a minimal configuration
    config = {
        "log": {},
    }
    
    # Create a connector
    connector = SolaceAiConnector(config)
    
    # Create a request-response controller
    controller_config = {
        "broker_config": {
            "broker_url": "tcp://localhost:55555",
            "broker_username": "default",
            "broker_password": "default",
            "broker_vpn": "default",
        },
        "request_expiry_ms": 5000,
    }
    
    # This should use the connector's create_internal_app method
    controller = RequestResponseFlowController(controller_config, connector)
    
    # Check that an app was created in the connector
    assert len(connector.apps) == 1
    assert connector.apps[0].name == "_internal_broker_request_response_app"
    
    # Check that a flow was created in the connector
    assert len(connector.flows) == 1
    assert connector.flows[0].name == "_internal_broker_request_response_flow"
    
    # Clean up
    connector.stop()
    connector.cleanup()
