"""Broker Adapter for the Command Control system.

This module provides the interface between the command control system and the
Solace Event Mesh.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional, Callable

from ..common.message import Message

# Configure logger
log = logging.getLogger(__name__)


class BrokerAdapter:
    """Interfaces with the Solace Event Mesh for command and control.
    
    This class handles receiving commands from the event mesh and publishing
    responses, status updates, and metrics.
    """

    def __init__(self, connector, command_control_service):
        """Initialize the BrokerAdapter.
        
        Args:
            connector: The SolaceAiConnector instance.
            command_control_service: The CommandControlService instance.
        """
        self.connector = connector
        self.command_control_service = command_control_service
        self.namespace = "solace"  # Default namespace
        self.topic_prefix = "sac-control/v1"
        self.command_flow_name = None
        self.response_flow_name = None
        self.command_handler = None
        
        # Configure from connector settings if available
        if connector and hasattr(connector, 'config'):
            command_control_config = connector.config.get('command_control', {})
            self.namespace = command_control_config.get('namespace', self.namespace)
            self.topic_prefix = command_control_config.get('topic_prefix', self.topic_prefix)
        
        log.info("Broker Adapter initialized with namespace: %s, topic prefix: %s",
                self.namespace, self.topic_prefix)

    def setup_command_flow(self, flow_name: str) -> None:
        """Set up the command flow for receiving commands.
        
        Args:
            flow_name: The name of the flow to use for receiving commands.
        """
        self.command_flow_name = flow_name
        log.info("Command flow set to: %s", flow_name)

    def setup_response_flow(self, flow_name: str) -> None:
        """Set up the response flow for sending responses.
        
        Args:
            flow_name: The name of the flow to use for sending responses.
        """
        self.response_flow_name = flow_name
        log.info("Response flow set to: %s", flow_name)

    def set_command_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Set the handler for incoming commands.
        
        Args:
            handler: The function to call when a command is received.
        """
        self.command_handler = handler
        log.info("Command handler set")

    def handle_message(self, message: Message) -> None:
        """Handle an incoming message from the broker.
        
        Args:
            message: The message received from the broker.
        """
        try:
            # Extract the topic and payload
            topic = message.get_topic()
            payload = message.get_payload()
            
            # Check if this is a command topic
            if not self._is_command_topic(topic):
                log.warning("Received message on non-command topic: %s", topic)
                return
                
            # Parse the method and endpoint from the topic
            method, endpoint = self._parse_command_topic(topic)
            if not method or not endpoint:
                log.warning("Could not parse method and endpoint from topic: %s", topic)
                return
                
            # Create a request object
            request = self._create_request(method, endpoint, payload, message)
            
            # Handle the request
            if self.command_handler:
                self.command_handler(request)
            else:
                log.warning("No command handler set, ignoring request")
                
        except Exception as e:
            log.error("Error handling message: %s", str(e), exc_info=True)

    def _is_command_topic(self, topic: str) -> bool:
        """Check if a topic is a command topic.
        
        Args:
            topic: The topic to check.
            
        Returns:
            bool: True if the topic is a command topic, False otherwise.
        """
        # Command topics have the format: <namespace>/sac-control/v1/<method>/<endpoint>
        parts = topic.split('/')
        if len(parts) < 4:
            return False
            
        return (parts[0] == self.namespace and 
                parts[1] == "sac-control" and 
                parts[2].startswith("v"))

    def _parse_command_topic(self, topic: str) -> tuple:
        """Parse a command topic to extract the method and endpoint.
        
        Args:
            topic: The topic to parse.
            
        Returns:
            tuple: (method, endpoint) or (None, None) if parsing fails.
        """
        # Command topics have the format: <namespace>/sac-control/v1/<method>/<endpoint>
        parts = topic.split('/')
        if len(parts) < 5:
            return None, None
            
        # The method is the 4th part
        method = parts[3]
        
        # The endpoint is everything after the method, joined with slashes
        endpoint = '/' + '/'.join(parts[4:])
        
        return method, endpoint

    def _create_request(self, 
                       method: str, 
                       endpoint: str, 
                       payload: Dict[str, Any],
                       message: Message) -> Dict[str, Any]:
        """Create a request object from a message.
        
        Args:
            method: The HTTP method (GET, POST, PUT, DELETE).
            endpoint: The endpoint path.
            payload: The message payload.
            message: The original message.
            
        Returns:
            Dict[str, Any]: The request object.
        """
        # Generate a request ID if not provided
        request_id = payload.get('request_id', str(uuid.uuid4()))
        
        # Extract query parameters and body from the payload
        query_params = payload.get('query_params', {})
        body = payload.get('body')
        
        # Get the reply topic prefix from the payload or user properties
        reply_to_topic_prefix = payload.get('reply_to_topic_prefix')
        if not reply_to_topic_prefix:
            user_props = message.get_user_properties() or {}
            reply_to_topic_prefix = user_props.get('reply_to_topic_prefix')
            
        # Create the request object
        request = {
            'request_id': request_id,
            'method': method,
            'endpoint': endpoint,
            'query_params': query_params,
            'body': body,
            'timestamp': payload.get('timestamp'),
            'source': payload.get('source', 'unknown'),
            'reply_to_topic_prefix': reply_to_topic_prefix
        }
        
        return request

    def publish_response(self, response: Dict[str, Any]) -> None:
        """Publish a response to the event mesh.
        
        Args:
            response: The response to publish.
        """
        if not self.response_flow_name:
            log.warning("No response flow set, cannot publish response")
            return
            
        try:
            request_id = response.get('request_id', 'unknown')
            reply_to_topic_prefix = response.get('reply_to_topic_prefix')
            
            if not reply_to_topic_prefix:
                log.warning("No reply_to_topic_prefix in response, cannot publish")
                return
                
            # Create the response topic
            topic = f"{reply_to_topic_prefix}/{self.topic_prefix}/response/{request_id}"
            
            # Create a message to send
            message = Message(
                payload=response,
                topic=topic,
                user_properties={}
            )
            
            # Send the message to the response flow
            self.connector.send_message_to_flow(self.response_flow_name, message)
            log.debug("Published response to topic: %s", topic)
            
        except Exception as e:
            log.error("Error publishing response: %s", str(e), exc_info=True)

    def publish_status(self, 
                      entity_id: str, 
                      entity_type: str, 
                      status: str, 
                      details: Dict[str, Any]) -> None:
        """Publish a status update to the event mesh.
        
        Args:
            entity_id: The ID of the entity.
            entity_type: The type of entity.
            status: The current status of the entity.
            details: Additional status details.
        """
        if not self.response_flow_name:
            log.warning("No response flow set, cannot publish status")
            return
            
        try:
            # Create the status topic
            topic = f"{self.namespace}/{self.topic_prefix}/status/{entity_id}"
            
            # Create the status message
            import datetime
            status_message = {
                'entity_id': entity_id,
                'entity_type': entity_type,
                'status': status,
                'details': details,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Create a message to send
            message = Message(
                payload=status_message,
                topic=topic,
                user_properties={}
            )
            
            # Send the message to the response flow
            self.connector.send_message_to_flow(self.response_flow_name, message)
            log.debug("Published status to topic: %s", topic)
            
        except Exception as e:
            log.error("Error publishing status: %s", str(e), exc_info=True)

    def publish_metrics(self, 
                       entity_id: str, 
                       entity_type: str, 
                       metrics: Dict[str, Dict[str, Any]]) -> None:
        """Publish metrics to the event mesh.
        
        Args:
            entity_id: The ID of the entity.
            entity_type: The type of entity.
            metrics: The metrics to publish.
        """
        if not self.response_flow_name:
            log.warning("No response flow set, cannot publish metrics")
            return
            
        try:
            # Create the metrics topic
            topic = f"{self.namespace}/{self.topic_prefix}/metrics/{entity_id}"
            
            # Create the metrics message
            import datetime
            metrics_message = {
                'entity_id': entity_id,
                'entity_type': entity_type,
                'metrics': metrics,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Create a message to send
            message = Message(
                payload=metrics_message,
                topic=topic,
                user_properties={}
            )
            
            # Send the message to the response flow
            self.connector.send_message_to_flow(self.response_flow_name, message)
            log.debug("Published metrics to topic: %s", topic)
            
        except Exception as e:
            log.error("Error publishing metrics: %s", str(e), exc_info=True)

    def publish_registry(self, 
                        instance_id: str, 
                        entities: Dict[str, Dict[str, Any]]) -> None:
        """Publish the entity registry to the event mesh.
        
        Args:
            instance_id: The ID of the connector instance.
            entities: The entities to publish.
        """
        if not self.response_flow_name:
            log.warning("No response flow set, cannot publish registry")
            return
            
        try:
            # Create the registry topic
            topic = f"{self.namespace}/{self.topic_prefix}/registry"
            
            # Create a simplified view of the entities for the registry
            simplified_entities = []
            for entity_id, entity in entities.items():
                simplified_entity = {
                    'entity_id': entity_id,
                    'entity_type': entity.get('entity_type', 'unknown'),
                    'entity_name': entity.get('entity_name', entity_id),
                    'description': entity.get('description', ''),
                    'version': entity.get('version', '1.0.0'),
                    'endpoints': []
                }
                
                # Add simplified endpoints
                for endpoint in entity.get('endpoints', []):
                    simplified_endpoint = {
                        'path': endpoint.get('path', ''),
                        'methods': list(endpoint.get('methods', {}).keys())
                    }
                    simplified_entity['endpoints'].append(simplified_endpoint)
                    
                simplified_entities.append(simplified_entity)
            
            # Create the registry message
            import datetime
            registry_message = {
                'instance_id': instance_id,
                'entities': simplified_entities,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            # Create a message to send
            message = Message(
                payload=registry_message,
                topic=topic,
                user_properties={}
            )
            
            # Send the message to the response flow
            self.connector.send_message_to_flow(self.response_flow_name, message)
            log.debug("Published registry to topic: %s", topic)
            
        except Exception as e:
            log.error("Error publishing registry: %s", str(e), exc_info=True)
            
    def publish_trace(self,
                     entity_id: str,
                     trace_level: str,
                     trace_event: Dict[str, Any]) -> None:
        """Publish a trace event to the event mesh.
        
        Args:
            entity_id: The ID of the entity emitting the trace.
            trace_level: The trace level (DEBUG, INFO, WARN, ERROR).
            trace_event: The trace event to publish.
        """
        if not self.response_flow_name:
            log.warning("No response flow set, cannot publish trace")
            return
            
        try:
            # Create the trace topic
            topic = f"{self.namespace}/{self.topic_prefix}/trace/{entity_id}/{trace_level}"
            
            # Create a message to send
            message = Message(
                payload=trace_event,
                topic=topic,
                user_properties={}
            )
            
            # Send the message to the response flow
            self.connector.send_message_to_flow(self.response_flow_name, message)
            log.debug("Published trace to topic: %s", topic)
            
        except Exception as e:
            log.error("Error publishing trace: %s", str(e), exc_info=True)
