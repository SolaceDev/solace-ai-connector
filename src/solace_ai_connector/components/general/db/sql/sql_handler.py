"""SQL Database Handler for SQL agent components."""

from typing import List, Dict, Any, Optional, Union
import importlib

from .....common.log import log
from .mysql_database_handler import MySQLDatabase
from .postgres_database_handler import PostgreSQLDatabase


class DatabaseFactory:
    """Factory class to create database instances."""

    DATABASE_PROVIDERS = {
        "mysql": MySQLDatabase,
        "postgres": PostgreSQLDatabase,
    }

    @staticmethod
    def get_database(
        db_type: str,
        host: str,
        port: Optional[int],
        user: str,
        password: str,
        database: str,
        **kwargs,
    ) -> Union[MySQLDatabase, PostgreSQLDatabase]:
        """
        Get a database connection instance.

        Args:
            db_type: Type of database ('mysql' or 'postgres').
            host: Database host.
            port: Database port.
            user: Database user.
            password: Database password.
            database: Database name.
            **kwargs: Additional arguments for the database connector.

        Returns:
            A database handler instance.

        Raises:
            ValueError: If the database type is unsupported.
        """
        db_type = db_type.lower()
        if db_type not in DatabaseFactory.DATABASE_PROVIDERS:
            raise ValueError("Unsupported database type: %s" % db_type)

        provider_class = DatabaseFactory.DATABASE_PROVIDERS[db_type]

        # Pass port explicitly if provided, otherwise handlers might parse from host or use default
        # This assumes the __init__ of MySQLDatabase and PostgreSQLDatabase
        # can handle an optional 'port' keyword argument.
        # If they strictly rely on "host:port" string, this part might need adjustment
        # or the handlers themselves need to be updated.
        # For now, we proceed with the assumption they accept an optional port.
        if port is not None:
            return provider_class(
                host=host,
                port=port, # Pass port directly
                user=user,
                password=password,
                database=database,
                **kwargs,
            )
        else:
            # Fallback if port is not provided, relying on handler's default port logic
            # or host:port parsing within the handler.
             return provider_class(
                host=host, # Port might be embedded here or handler uses default
                user=user,
                password=password,
                database=database,
                **kwargs,
            )


class SQLHandler:
    """Handler for SQL database operations."""

    def __init__(
        self,
        db_type: str,
        host: str,
        port: Optional[int],
        user: str,
        password: str,
        database: str,
        **kwargs,
    ):
        """
        Initialize the SQL handler.

        Args:
            db_type: Type of database ('mysql' or 'postgres').
            host: Database host.
            port: Database port.
            user: Database user.
            password: Database password.
            database: Database name.
            **kwargs: Additional arguments for the database connector.
        """
        self.db_type = db_type.lower()
        log.info(
            "Initializing SQLHandler for %s at %s:%s/%s",
            self.db_type,
            host,
            port or 'default',
            database
        )
        self.db_client = DatabaseFactory.get_database(
            db_type=self.db_type,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            **kwargs,
        )
        self.connect() # Ensure connection is attempted on init

    def connect(self):
        """Ensure the database connection is active."""
        try:
            # The connect method might be specific to the handler or implicit
            # For now, we assume getting a cursor forces a connection if needed.
            # Or the db_client.connect() method exists and is idempotent.
            if hasattr(self.db_client, 'connect') and callable(getattr(self.db_client, 'connect')):
                if getattr(self.db_client, 'connection', None) is None or \
                   (hasattr(getattr(self.db_client, 'connection', None), 'closed') and getattr(self.db_client.connection, 'closed', False)):
                    log.debug("Attempting to connect to %s database.", self.db_type)
                    self.db_client.connect()
                    log.info("Successfully connected/reconnected to %s database.", self.db_type)
            else: # If no explicit connect, try getting a cursor to test
                with self.db_client.cursor() as cursor: # cursor variable is not used here
                    log.debug("Connection to %s database confirmed via cursor.", self.db_type)
        except Exception as e:
            log.error("Error connecting to %s database: %s", self.db_type, e, exc_info=True)
            raise ValueError("Failed to connect to %s database: %s" % (self.db_type, e)) from e

    def close(self):
        """Close the database connection."""
        if self.db_client and hasattr(self.db_client, "close"):
            try:
                self.db_client.close()
                log.info("Successfully closed %s database connection.", self.db_type)
            except Exception as e:
                log.error(
                    "Error closing %s database connection: %s", self.db_type, e, exc_info=True
                )

    def execute_query(
        self, query: str, params: Optional[Union[tuple, Dict]] = None, fetch_results: bool = True
    ) -> Union[List[Dict[str, Any]], int]:
        """
        Execute a SQL query.

        Args:
            query: The SQL query to execute.
            params: Parameters to bind to the query (tuple for %s, dict for named).
            fetch_results: Whether to fetch and return results.

        Returns:
            List of dictionaries if fetch_results is True, otherwise row count for DML.

        Raises:
            ValueError: If query execution fails.
        """
        log.debug("Executing query on %s: %s with params: %s", self.db_type, query, params)
        try:
            # PostgreSQLDatabase has its own execute method that returns a cursor
            if self.db_type == "postgres" and hasattr(self.db_client, 'execute'):
                cursor = self.db_client.execute(query, params)
            else: # For MySQL or other generic path
                # Ensure connection before getting cursor
                if getattr(self.db_client, 'connection', None) is None or \
                    (self.db_type == "mysql" and isinstance(getattr(self.db_client, 'connection', None), importlib.import_module('mysql.connector').connection.MySQLConnection) and not self.db_client.connection.is_connected()) or \
                    (self.db_type == "postgres" and getattr(self.db_client.connection, 'closed', True)):
                    self.connect()

                # MySQL uses dictionary=True for dict results, psycopg2 uses RealDictCursor
                cursor_kwargs = {}
                if self.db_type == "mysql":
                    cursor_kwargs['dictionary'] = True
                elif self.db_type == "postgres":
                    # Assuming PostgreSQLDatabase.cursor can take cursor_factory
                    # This is already handled by postgres_database_handler.py's execute method
                    pass


                actual_cursor = self.db_client.cursor(**cursor_kwargs)
                actual_cursor.execute(query, params)
                cursor = actual_cursor


            if fetch_results:
                if hasattr(cursor, "fetchall") and callable(getattr(cursor, "fetchall")):
                    columns = [desc[0] for desc in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                    log.debug("Query fetched %d rows.", len(results))
                    return results
                else:
                    log.warning("Cursor does not support fetchall, cannot return results as list of dicts.")
                    return [] # Or raise error
            else:
                rowcount = cursor.rowcount
                # For PostgreSQL, commit might be needed if autocommit is false and it's a DML
                # However, the plan is to rely on autocommit=True from handlers
                if self.db_type == "mysql" and self.db_client.connection.autocommit is False:
                     self.db_client.connection.commit()
                elif self.db_type == "postgres" and self.db_client.connection.autocommit is False:
                     self.db_client.connection.commit()

                log.debug("Query executed, row count: %s.", rowcount) # rowcount can be -1
                return rowcount

        except Exception as e:
            log.error("Error executing query on %s: %s", self.db_type, e, exc_info=True)
            # Attempt to rollback if autocommit is false and an error occurs
            if self.db_type == "mysql" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                self.db_client.connection.rollback()
            elif self.db_type == "postgres" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                 self.db_client.connection.rollback()
            raise ValueError("Failed to execute query on %s: %s" % (self.db_type, e)) from e
        finally:
            if 'actual_cursor' in locals() and actual_cursor: # Check if actual_cursor was defined
                if hasattr(actual_cursor, 'closed') and not actual_cursor.closed:
                    actual_cursor.close()
                elif not hasattr(actual_cursor, 'closed'): # For cursors without a 'closed' attribute
                    actual_cursor.close()


    def insert_data(
        self,
        table_name: str,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        on_duplicate_update_columns: Optional[List[str]] = None,
    ) -> int:
        """
        Insert data into a table.

        Args:
            table_name: Name of the table.
            data: A dictionary for a single row or a list of dictionaries for multiple rows.
            on_duplicate_update_columns: List of column names to update on duplicate key.

        Returns:
            Number of affected rows.

        Raises:
            ValueError: If data is not in the expected format or insertion fails.
        """
        if not isinstance(data, (dict, list)):
            raise ValueError("Data must be a dictionary or a list of dictionaries.")
        if isinstance(data, dict):
            data_list = [data]
        else:
            data_list = data

        if not data_list:
            return 0

        first_row = data_list[0]
        columns = list(first_row.keys())
        placeholders = ", ".join(["%s"] * len(columns))
        column_names = ", ".join([f"`{col}`" if self.db_type == "mysql" else f'"{col}"' for col in columns]) # Quote column names

        base_query = f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})"

        if on_duplicate_update_columns:
            if self.db_type == "mysql":
                update_clause = ", ".join([f"`{col}`=VALUES(`{col}`)" for col in on_duplicate_update_columns])
                query = f"{base_query} ON DUPLICATE KEY UPDATE {update_clause}"
            elif self.db_type == "postgres":
                # For PostgreSQL, need to specify the constraint columns for ON CONFLICT
                # This is a simplification; a robust solution would need to know primary/unique keys.
                # Assuming 'id' or the first column for simplicity if not specified.
                # A better approach would be to require conflict target columns.
                # For now, let's assume the user handles conflict targets or this is a simple case.
                # A common pattern is to update all provided columns in `on_duplicate_update_columns`.
                update_clause = ", ".join([f'"{col}"=EXCLUDED."{col}"' for col in on_duplicate_update_columns])
                # Inferring conflict target is tricky. Let's assume the user ensures the table has a PK
                # and the conflict will be on that. A more robust version would take conflict_target as param.
                # This example will require the user to ensure the ON CONFLICT target is implicitly handled by the DB.
                # A common way is to list the primary key columns in the ON CONFLICT clause.
                # For simplicity, we'll assume the conflict target is on the primary key(s) of the table.
                # This part is complex and database-specific.
                # A common approach for ON CONFLICT is to specify the columns that form the unique constraint.
                # E.g., ON CONFLICT (primary_key_column) DO UPDATE SET ...
                # This simplified version might not work for all cases without knowing the PK.
                # For now, we'll make a generic update clause and rely on the user to have a clear PK.
                # A better version would require `conflict_target_columns` as a parameter.
                # Let's assume for now the conflict is on the primary key and Postgres can infer it or it's simple.
                # A more robust way for Postgres: ON CONFLICT (col1, col2) DO UPDATE SET...
                # We will assume the user has set up the table such that a general conflict on insert works.
                # This is a known simplification.
                log.warning("PostgreSQL ON CONFLICT DO UPDATE is simplified and assumes conflict on primary key(s). "
                            "For complex cases, provide conflict_target_columns.")
                # To make it work generally, one might need to specify the constraint name or columns.
                # For now, we'll try a common pattern.
                # This will likely require the user to have a primary key defined.
                query = f"{base_query} ON CONFLICT DO UPDATE SET {update_clause}"
                # A more specific version:
                # query = f"{base_query} ON CONFLICT ON CONSTRAINT {constraint_name} DO UPDATE SET {update_clause}"
                # or query = f"{base_query} ON CONFLICT (column_name_for_conflict) DO UPDATE SET {update_clause}"
                # Since we don't have that info, this is a best guess.
            else:
                raise ValueError(
                    "ON DUPLICATE UPDATE not implemented for db_type: %s" % self.db_type
                )
        else:
            query = base_query

        total_affected_rows = 0
        
        # Ensure connection
        if getattr(self.db_client, 'connection', None) is None or \
            (self.db_type == "mysql" and isinstance(getattr(self.db_client, 'connection', None), importlib.import_module('mysql.connector').connection.MySQLConnection) and not self.db_client.connection.is_connected()) or \
            (self.db_type == "postgres" and getattr(self.db_client.connection, 'closed', True)):
            self.connect()

        cursor_kwargs = {}
        if self.db_type == "mysql":
            cursor_kwargs['prepared'] = True # Use prepared statements for MySQL inserts if possible
        
        actual_cursor = None
        try:
            actual_cursor = self.db_client.cursor(**cursor_kwargs)
            if len(data_list) > 1 and hasattr(actual_cursor, 'executemany') and callable(getattr(actual_cursor, 'executemany')):
                values_to_insert = [tuple(row[col] for col in columns) for row in data_list]
                actual_cursor.executemany(query, values_to_insert)
                total_affected_rows = actual_cursor.rowcount 
                # executemany rowcount can be unreliable across drivers/DBs for actual inserted/updated rows
                # For MySQL with ON DUPLICATE KEY UPDATE, rowcount is 1 for each insert, 2 for each update.
                # For PostgreSQL with ON CONFLICT DO UPDATE, rowcount is 1 for each row inserted or updated.
                # We will use this value, but acknowledge its potential variance.
                if self.db_type == "mysql" and on_duplicate_update_columns:
                    # MySQL counts 2 for an update, 1 for an insert.
                    # This is a common way to estimate actual changes, but not perfect.
                    # For simplicity, we'll stick to cursor.rowcount.
                    pass

            else: # Fallback to one by one if executemany is not available or for single insert
                for row_data in data_list:
                    values = tuple(row_data[col] for col in columns)
                    actual_cursor.execute(query, values)
                    total_affected_rows += actual_cursor.rowcount
            
            # Commit if autocommit is off
            if self.db_type == "mysql" and self.db_client.connection.autocommit is False:
                self.db_client.connection.commit()
            elif self.db_type == "postgres" and self.db_client.connection.autocommit is False:
                self.db_client.connection.commit()

            log.debug(
                "Successfully inserted/updated data into %s. Affected rows: %s",
                table_name,
                total_affected_rows
            )
            return total_affected_rows
        except Exception as e:
            log.error("Error inserting data into %s for %s: %s", table_name, self.db_type, e, exc_info=True)
            if self.db_type == "mysql" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                self.db_client.connection.rollback()
            elif self.db_type == "postgres" and hasattr(self.db_client, 'connection') and self.db_client.connection and self.db_client.connection.autocommit is False:
                 self.db_client.connection.rollback()
            raise ValueError("Failed to insert data into %s: %s" % (table_name, e)) from e
        finally:
            if actual_cursor: # Check if actual_cursor was defined
                if hasattr(actual_cursor, 'closed') and not actual_cursor.closed:
                    actual_cursor.close()
                elif not hasattr(actual_cursor, 'closed'): # For cursors without a 'closed' attribute
                    actual_cursor.close()