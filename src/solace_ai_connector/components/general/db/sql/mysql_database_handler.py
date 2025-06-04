"""Manage a MySQL database connection."""

import mysql.connector

class MySQLDatabase:
    def __init__(self, host: str, user: str, password: str, database: str):
        self.host = host
        self.user = user
        self.password = password
        self.database = database
        self.connection = None

        if ":" in self.host:
            self.host, self.port = self.host.split(":")
        else:
            self.port = 3306

    def cursor(self, **kwargs):
        if self.connection is None:
            self.connect()
        try:
            return self.connection.cursor(**kwargs)
        except mysql.connector.errors.OperationalError:
            self.connect()
            return self.connection.cursor(**kwargs)

    def connect(self):
        return mysql.connector.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            raise_on_warnings=False,
            connection_timeout=60,
            autocommit=True,
        )

    def close(self):
        self.connection.close()
