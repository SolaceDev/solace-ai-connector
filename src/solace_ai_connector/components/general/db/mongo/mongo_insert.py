"""MongoDB Agent Component for handling database insert."""

from .mongo_handler import MongoDBHandler
from ....component_base import ComponentBase


info = {
    "class_name": "MongoDBInsertComponent",
    "description": "Inserts given JSON data into a MongoDB database.",
    "config_parameters": [
        {
            "name": "database_host",
            "required": True,
            "description": "MongoDB host",
            "type": "string",
        },
        {
            "name": "database_port",
            "required": True,
            "description": "MongoDB port",
            "type": "integer",
        },
        {
            "name": "database_user",
            "required": False,
            "description": "MongoDB user",
            "type": "string",
        },
        {
            "name": "database_password",
            "required": False,
            "description": "MongoDB password",
            "type": "string",
        },
        {
            "name": "database_name",
            "required": True,
            "description": "Database name",
            "type": "string",
        },
        {
            "name": "database_collection",
            "required": False,
            "description": "Collection name - if not provided, all collections will be used",
        },
    ],
}


class MongoDBInsertComponent(ComponentBase):
    """Component for handling MongoDB database operations."""

    def __init__(self, **kwargs):
        """Initialize the MongoDB component.

        Args:
            **kwargs: Additional keyword arguments.

        Raises:
            ValueError: If required database configuration is missing.
        """
        super().__init__(info, **kwargs)

        # Initialize MongoDB handler
        self.db_handler = MongoDBHandler(
            self.get_config("database_host"),
            self.get_config("database_port"),
            self.get_config("database_user"),
            self.get_config("database_password"),
            self.get_config("database_collection"),
            self.get_config("database_name"),
        )

    def invoke(self, message, data):
        if not data:
            raise ValueError(
                "Invalid data provided for MongoDB insert. Expected a dictionary or a list of dictionary."
            )
        return self.db_handler.insert_documents(data)
