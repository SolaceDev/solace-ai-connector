"""
Manages multiple independent request/response sessions for a component.
"""

import threading
import time
import weakref
from typing import Dict, Any, List, Optional

from ..common.log import log
from ..common.exceptions import SessionLimitExceededError
from ..common.session_config import SessionConfig
from .session_registry import SessionRegistry
from .request_response_session import RequestResponseSession


class MultiSessionRequestResponseManager:
    """
    Manages multiple independent request/response sessions for a component.
    """

    def __init__(
        self,
        component: Any,
        default_session_config: Optional[SessionConfig] = None,
        max_sessions: int = 50,
    ):
        """
        Initializes the MultiSessionRequestResponseManager.

        Args:
            component: A weak reference to the parent component.
            default_session_config: The default session configuration.
            max_sessions: The maximum number of concurrent sessions allowed.
        """
        self.component_ref = weakref.ref(component)
        self.session_registry = SessionRegistry()
        self.default_session_config = default_session_config
        self.max_sessions = max_sessions
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

        self._cleanup_thread = threading.Thread(
            target=self._cleanup_expired_sessions_loop, daemon=True
        )
        self._cleanup_thread.start()

    def create_session(
        self, session_config_overrides: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Creates a new request/response session, applies overrides to the default
        configuration, registers it, and returns its unique ID.

        Args:
            session_config_overrides: A dictionary of configuration values to
                                      override the defaults.

        Returns:
            The unique session ID of the newly created session.

        Raises:
            SessionLimitExceededError: If the maximum number of sessions is reached.
            RuntimeError: If the parent component reference is lost.
        """
        with self._lock:
            if len(self.session_registry.list_sessions()) >= self.max_sessions:
                raise SessionLimitExceededError(
                    "Cannot create new session. Maximum session limit of "
                    f"{self.max_sessions} reached."
                )

            session_config_overrides = session_config_overrides or {}

            final_config = SessionConfig.from_dict(
                session_config_overrides, self.default_session_config
            )

            component = self.component_ref()
            if not component:
                raise RuntimeError(
                    "Component reference is lost. Cannot create session."
                )

            session_id = self.session_registry.generate_session_id()
            session = RequestResponseSession(
                session_id=session_id,
                config=final_config,
                connector=component.connector,
            )
            self.session_registry.register_session(session)
            log.info(f"Created request/response session: {session_id}")
            return session_id

    def destroy_session(self, session_id: str) -> bool:
        """
        Destroys a session and cleans up its associated resources.

        Args:
            session_id: The ID of the session to destroy.

        Returns:
            True if the session was found and destroyed, False otherwise.
        """
        session = self.session_registry.unregister_session(session_id)
        if session:
            log.info(f"Destroying request/response session: {session_id}")
            session.cleanup()
            return True
        log.warning(f"Attempted to destroy non-existent session: {session_id}")
        return False

    def get_session(self, session_id: str) -> "RequestResponseSession":
        """
        Retrieves an active session by its ID.

        Args:
            session_id: The ID of the session to retrieve.

        Returns:
            The RequestResponseSession instance.
        """
        return self.session_registry.get_session(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        Returns a list of dictionaries containing detailed status for each
        active session.

        Returns:
            A list of session status dictionaries.
        """
        sessions = self.session_registry.list_sessions()
        return [session.get_status() for session in sessions]

    def _cleanup_expired_sessions_loop(self):
        """
        Background thread loop that periodically checks for and removes
        expired sessions based on their idle timeout.
        """
        while not self._shutdown_event.is_set():
            try:
                # Use a copy of the list to avoid issues with concurrent modification
                sessions_to_check = self.session_registry.list_sessions()
                for session in sessions_to_check:
                    if session.is_expired():
                        log.info(f"Session {session.session_id} has expired. Cleaning up.")
                        self.destroy_session(session.session_id)
            except Exception as e:
                log.error(f"Error in session cleanup loop: {e}", trace=e)

            # Determine a sensible wait interval.
            # Use a fraction of the shortest timeout, or a default.
            all_timeouts = [
                s.config.session_timeout_seconds
                for s in self.session_registry.list_sessions()
                if s.config.session_timeout_seconds > 0
            ]
            wait_interval = min(all_timeouts) / 10 if all_timeouts else 60
            wait_interval = max(1, wait_interval)

            self._shutdown_event.wait(timeout=wait_interval)

    def shutdown(self):
        """
        Gracefully stops the cleanup thread and destroys all active sessions.
        """
        log.info("Shutting down MultiSessionRequestResponseManager.")
        self._shutdown_event.set()

        if self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5.0)

        all_sessions = self.session_registry.clear()
        for session in all_sessions:
            log.info(f"Shutting down session during manager shutdown: {session.session_id}")
            session.cleanup()
        log.info("MultiSessionRequestResponseManager shut down complete.")
