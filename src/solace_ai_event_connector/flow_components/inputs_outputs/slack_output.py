import base64
from copy import deepcopy
from datetime import datetime, timedelta


from solace_ai_event_connector.flow_components.inputs_outputs.slack_base import (
    SlackBase,
)
from solace_ai_event_connector.common.message import Message
from solace_ai_event_connector.common.log import log


info = {
    "class_name": "SlackOutput",
    "description": (
        "Slack output component. The component sends messages to Slack channels using the Bolt API."
    ),
    "config_parameters": [
        {
            "name": "slack_bot_token",
            "type": "string",
            "description": "The Slack bot token to connect to Slack.",
        },
        {
            "name": "slack_app_token",
            "type": "string",
            "description": "The Slack app token to connect to Slack.",
        },
        {
            "name": "share_slack_connection",
            "type": "string",
            "description": "Share the Slack connection with other components in this instance.",
        },
    ],
    "input_schema": {
        "type": "object",
        "properties": {
            "message_info": {
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                    },
                    "type": {
                        "type": "string",
                    },
                    "user_email": {
                        "type": "string",
                    },
                    "client_msg_id": {
                        "type": "string",
                    },
                    "ts": {
                        "type": "string",
                    },
                    "subtype": {
                        "type": "string",
                    },
                    "event_ts": {
                        "type": "string",
                    },
                    "channel_type": {
                        "type": "string",
                    },
                    "user_id": {
                        "type": "string",
                    },
                    "session_id": {
                        "type": "string",
                    },
                },
                "required": ["channel", "session_id"],
            },
            "content": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                    },
                    "stream": {
                        "type": "boolean",
                    },
                    "uuid": {
                        "type": "string",
                    },
                    "files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                },
                                "content": {
                                    "type": "string",
                                },
                                "mime_type": {
                                    "type": "string",
                                },
                                "filetype": {
                                    "type": "string",
                                },
                                "size": {
                                    "type": "number",
                                },
                            },
                        },
                    },
                },
                "required": ["text"],
            },
        },
        "required": ["message_info", "content"],
    },
}


class SlackOutput(SlackBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.stream_manager = StreamManager(self.app)

    def invoke(self, message, data):
        message_info = data.get("message_info")
        content = data.get("content")
        text = content.get("text")
        stream = content.get("stream")
        uuid = content.get("uuid")
        channel = message_info.get("channel")
        thread_ts = message_info.get("ts")
        ack_msg_ts = message_info.get("ack_msg_ts")

        return {
            "channel": channel,
            "text": text,
            "files": content.get("files"),
            "thread_ts": thread_ts,
            "ack_msg_ts": ack_msg_ts,
            "stream": stream,
            "uuid": uuid,
        }

    def send_message(self, message):
        try:
            channel = message.get_data("previous:channel")
            messages = message.get_data("previous:text")
            stream = message.get_data("previous:stream")
            uuid = message.get_data("previous:uuid")
            files = message.get_data("previous:files") or []
            thread_ts = message.get_data("previous:ts")
            ack_msg_ts = message.get_data("previous:ack_msg_ts")

            if not isinstance(messages, list):
                if messages is not None:
                    messages = [messages]
                else:
                    messages = []

            for text in messages:
                if stream:
                    if ack_msg_ts:
                        self.stream_manager.stream_message(
                            channel, thread_ts, ack_msg_ts, uuid, text
                        )
                else:
                    self.app.client.chat_postMessage(
                        channel=channel, text=text, thread_ts=thread_ts
                    )

            for file in files:
                file_content = base64.b64decode(file["content"])
                self.app.client.files_upload_v2(
                    channel=channel,
                    file=file_content,
                    thread_ts=thread_ts,
                    filename=file["name"],
                )
        except Exception as e:
            log.error(f"Error sending slack message: {e}")

        super().send_message(message)

        try:
            if ack_msg_ts and not stream:
                self.app.client.chat_delete(channel=channel, ts=ack_msg_ts)
                self.stream_manager.add_stream(ack_msg_ts, uuid)
        except Exception:
            pass


# This class manages streaming partial messages back to the user. It
# handles cases where the orginal 'ack_msg' has been deleted when there
# are multiple messages sent back to the user for a single request.
class StreamManager:
    """Keeps information to handle streamed messages"""

    def __init__(self, slack_app):
        # This is indexed by a uuid that is in the message_info
        self.app = slack_app
        self.stream_ts = {}
        self.streams = []

    def stream_message(self, channel, thread_ts, ack_msg_ts, msg_uuid, message):
        # If the message is a stream message, we need to keep track of the
        # original message that was sent to the user so we can update it
        # with the new message
        msg_uuid = msg_uuid or ack_msg_ts
        ts = self.stream_ts.get(msg_uuid).get("ts")
        if ts:
            return self.update_message(channel, ts, message)

        if not self.update_message(channel, ack_msg_ts, message):
            ts = self.post_message(channel, thread_ts, message)
            self.add_stream(ts, msg_uuid)

        self.age_out_streams()

    def update_message(self, channel, ts, message):
        try:
            self.app.client.chat_update(channel=channel, ts=ts, text=message)
        except Exception:
            return False
        return True

    def post_message(self, channel, thread_ts, message):
        try:
            response = self.app.client.chat_postMessage(
                channel=channel, text=message, thread_ts=thread_ts
            )
            return response["ts"]
        except Exception:
            return None

    def add_stream(self, ts, msg_uuid):
        if self.stream_ts.get(msg_uuid):
            return
        now = datetime.now()
        stream_info = {"ts": ts, "time": now, "msg_uuid": msg_uuid}
        self.stream_ts[msg_uuid] = {"ts": ts, "time": now}
        self.streams.append(stream_info)

    def age_out_streams(self):
        now = datetime.now()
        while len(self.streams) > 0:
            stream = self.streams[0]
            if stream["time"] < now - timedelta(seconds=300):
                self.streams.pop(0)
                del self.stream_ts[stream["msg_uuid"]]
            else:
                break
