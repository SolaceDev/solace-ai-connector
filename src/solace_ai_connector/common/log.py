import sys
import logging
import logging.handlers
import json
import os
from datetime import datetime, timezone
import time
import traceback


log = logging.getLogger("solace_ai_connector")


class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON format.
    """

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


class JsonlFormatter(logging.Formatter):
    """
    Custom formatter to output logs in JSON Lines (JSONL) format.
    """

    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        return json.dumps(log_record)


class DatadogJsonFormatter(logging.Formatter):
    """
    Custom formatter for Datadog-compatible JSON logs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, datefmt='%Y-%m-%dT%H:%M:%S', **kwargs)
        self.converter = time.gmtime  # Use UTC

    def formatTime(self, record, datefmt=None):
        dt_utc = datetime.fromtimestamp(record.created, tz=timezone.utc)
        time_str_main_part = dt_utc.strftime(datefmt if datefmt else '%Y-%m-%dT%H:%M:%S')
        return f"{time_str_main_part}.{int(record.msecs):03d}Z"

    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "status": record.levelname,
            "message": record.getMessage(),
            "ddsource": "python",
            "service": os.getenv("DD_SERVICE", record.name),
        }
        env_val = os.getenv("DD_ENV")
        if env_val: log_record["env"] = env_val
        version_val = os.getenv("DD_VERSION")
        if version_val: log_record["version"] = version_val

        standard_attrs = {
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'message', 'module',
            'msecs', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName',
            *log_record.keys() 
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_record[key] = value
        
        log_record["logger.name"] = record.name
        log_record["logger.thread_name"] = record.threadName
        log_record["logger.method_name"] = record.funcName
        log_record["logger.lineno"] = record.lineno
        log_record["logger.module"] = record.module

        if record.exc_info:
            if record.exc_info[0] is not None:
                log_record["error.kind"] = record.exc_info[0].__name__
            log_record["error.message"] = str(record.exc_info[1])
            log_record["error.stack"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_record["error.stack"] = record.exc_text
            
        return json.dumps(log_record)


def convert_to_bytes(size_str):
    size_str = size_str.upper()
    size_units = {"KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4, "B": 1}
    for unit in size_units:
        if size_str.endswith(unit):
            return int(size_str[: -len(unit)]) * size_units[unit]
    return int(size_str)


def get_log_level_from_env(env_var_name, default_level_str):
    """Gets a logging level from an environment variable, with a default."""
    level_str = os.getenv(env_var_name, default_level_str).upper()
    level_map = {
        "DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING,
        "ERROR": logging.ERROR, "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str, logging.INFO) # Default to INFO if invalid string


# Helper function to handle trace formatting
def _format_with_trace(message, trace):
    try:
        if isinstance(trace, Exception):
            # If it's an Exception object
            stack_trace = traceback.format_exception(
                type(trace), trace, trace.__traceback__
            )
            full_message = f"{message} | TRACE: {trace}\n{''.join(stack_trace)}"
        else:
            # Regular trace info
            full_message = f"{message} | TRACE: {trace}"
    except Exception:
        # Fallback if there's an issue with the trace handling
        full_message = f"{message} | TRACE: {trace}"
    return full_message


def setup_log(
    logFilePath,
    stdOutLogLevel,
    fileLogLevel,
    logFormat,
    logBack,
    enableTrace=False,
):
    """
    Set up the configuration for the logger.

    Parameters:
        logFilePath (str): Path to the log file.
        stdOutLogLevel (int): Logging level for standard output.
        fileLogLevel (int): Logging level for the log file.
        logFormat (str): Format of the log output ('jsonl' or 'pipe-delimited').
        logBack (dict): Rolling log file configuration.
    """

    # Set the global logger level to the lowest of the two levels
    log.setLevel(min(stdOutLogLevel, fileLogLevel))

    # Clear existing handlers to prevent duplication if setup_log is called multiple times
    if log.hasHandlers():
        log.handlers.clear()

    is_datadog_enabled = os.getenv("DATADOG_LOGGING_ENABLED", "false").lower() == "true"

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(stdOutLogLevel)
    
    # This will be the formatter for the file_handler if file logging is enabled
    file_formatter_for_file_handler = None

    if is_datadog_enabled:
        datadog_formatter = DatadogJsonFormatter()
        stream_handler.setFormatter(datadog_formatter)
        file_formatter_for_file_handler = datadog_formatter # Use for file too if Datadog enabled
    else:
        stream_formatter = logging.Formatter("%(message)s")
        stream_handler.setFormatter(stream_formatter)
        if logFormat == "jsonl":
            file_formatter_for_file_handler = JsonlFormatter()
        else:
            file_formatter_for_file_handler = logging.Formatter("%(asctime)s |  %(levelname)s: %(message)s")
    
    log.addHandler(stream_handler) # Add stream handler

    # Configure File Handler (if logFilePath is provided)
    if logFilePath: # Check if logFilePath is provided
        # Ensure a formatter is selected for the file
        if not file_formatter_for_file_handler: # Should be set if Datadog is off
             if logFormat == "jsonl": file_formatter_for_file_handler = JsonlFormatter()
             else: file_formatter_for_file_handler = logging.Formatter("%(asctime)s |  %(levelname)s: %(message)s")
        
        # Define file_handler within this block
        _file_handler = None # Initialize to avoid UnboundLocalError if logic below fails
        if logBack: 
            rollingpolicy = logBack.get("rollingpolicy", {}) 
            if rollingpolicy:
                if "file-name-pattern" not in rollingpolicy:
                    log.warning(
                        "file-name-pattern is required in rollingpolicy. Continuing with default value '{LOG_FILE}.%d{yyyy-MM-dd}.%i'."
                    )
                file_name_pattern = rollingpolicy.get(
                    "file-name-pattern", "{LOG_FILE}.%d{yyyy-MM-dd}.%i.gz"
                )
                if "max-file-size" not in rollingpolicy:
                    log.warning(
                        "max-file-size is required in rollingpolicy. Continuing with default value '1GB'."
                    )
                max_file_size = rollingpolicy.get("max-file-size", "1GB")
                if "max-history" not in rollingpolicy:
                    log.warning(
                        "max-history is required in rollingpolicy. Continuing with default value '7'."
                    )
                max_history = rollingpolicy.get("max-history", 7)
                if "total-size-cap" not in rollingpolicy:
                    log.warning(
                        "total-size-cap is required in rollingpolicy. Continuing with default value '1TB'."
                    )
                total_size_cap = rollingpolicy.get("total-size-cap", "1TB")

                max_file_size = convert_to_bytes(max_file_size)
                total_size_cap = convert_to_bytes(total_size_cap) # total_size_cap not currently used by RotatingFileHandler
                
                log_file_name = logFilePath # logFilePath is guaranteed to be truthy here
                _file_handler = logging.handlers.RotatingFileHandler(
                    filename=log_file_name,
                    backupCount=max_history,
                    maxBytes=max_file_size,
                )
                _file_handler.namer = (
                    lambda name: file_name_pattern.replace("${LOG_FILE}", logFilePath)
                    .replace("%d{yyyy-MM-dd}", datetime.now().strftime("%Y-%m-%d"))
                    .replace("%i", str(name.split(".")[-1]))
                )
            else: # logBack is true, but no rollingpolicy
                log.warning("logBack is true but no rollingpolicy provided. Defaulting to standard FileHandler.")
                _file_handler = logging.FileHandler(filename=logFilePath, mode="a") # logFilePath is truthy
        else: # logBack is false (or None)
            _file_handler = logging.FileHandler(filename=logFilePath, mode="a") # logFilePath is truthy

        # Configure and add the file_handler if it was successfully created
        if _file_handler:
            _file_handler.setFormatter(file_formatter_for_file_handler) 
            _file_handler.setLevel(fileLogLevel)
            log.addHandler(_file_handler)
        else:
            log.error("File handler could not be initialized despite logFilePath being set.")

    # --- Log Method Wrappers (Updated) ---
    original_debug = log.debug
    original_info = log.info
    original_warning = log.warning
    original_error = log.error
    original_critical = log.critical

    def log_wrapper(original_method, message, *args, trace=None, extra=None, **kwargs):
        # kwargs passed to log_wrapper by the lambda should not contain 'trace' or 'extra',
        # as they are popped by the lambda and passed as named arguments.
        # This is an additional safeguard in case log_wrapper is called differently.
        kwargs.pop('trace', None)
        kwargs.pop('extra', None)

        # Initialize processed_extra from the 'extra' named argument.
        processed_extra = {}
        if isinstance(extra, dict):
            processed_extra = extra.copy()
        elif extra is not None: 
            sys.stderr.write(
                f"WARNING: Logger 'extra' argument (named parameter) was not a dict, received: {type(extra)}. Ignoring.\n"
            )

        # Use enableTrace parameter from setup_log's scope for the wrapper's trace logic
        # This was passed into setup_log.
        _effective_enable_trace = enableTrace 

        if isinstance(trace, Exception):
            kwargs['exc_info'] = trace # Standard way to pass exception info
            if _effective_enable_trace: # If trace string also needs to be in the message
                formatted_message_for_trace = message % args if args and isinstance(message, str) else message
                message = _format_with_trace(formatted_message_for_trace, trace)
                args = () # Message is now fully formed
        elif trace and _effective_enable_trace: # If trace is a string and tracing is enabled
            # Add as a custom field in the processed_extra dictionary
            processed_extra['custom_trace'] = str(trace) 
        
        if processed_extra: # Pass 'extra' to the original method only if it's not empty
            kwargs['extra'] = processed_extra
        
        if args and isinstance(message, str):
             original_method(message, *args, **kwargs)
        else:
             original_method(message, **kwargs)

    log.debug = lambda msg, *a, **kw: log_wrapper(original_debug, msg, *a, trace=kw.pop('trace', None), extra=kw.pop('extra', None), **kw)
    log.info = lambda msg, *a, **kw: log_wrapper(original_info, msg, *a, trace=kw.pop('trace', None), extra=kw.pop('extra', None), **kw)
    log.warning = lambda msg, *a, **kw: log_wrapper(original_warning, msg, *a, trace=kw.pop('trace', None), extra=kw.pop('extra', None), **kw)
    log.error = lambda msg, *a, **kw: log_wrapper(original_error, msg, *a, trace=kw.pop('trace', None), extra=kw.pop('extra', None), **kw)
    log.critical = lambda msg, *a, **kw: log_wrapper(original_critical, msg, *a, trace=kw.pop('trace', None), extra=kw.pop('extra', None), **kw)


# --- Simplified Auto-configuration on Import ---
# This block runs once when the module is imported.
# It calls setup_log with basic console parameters derived from environment variables.
_auto_setup_done = False
if not _auto_setup_done:
    try:
        _std_out_log_level = get_log_level_from_env("LOG_STDOUT_LEVEL", "INFO")
        _enable_trace = os.getenv("LOG_ENABLE_TRACE", "false").lower() == "true"
        
        # Call setup_log with minimal console configuration
        # Applications needing file logging or specific rolling policies should call setup_log() again.
        setup_log(
            logFilePath=None, 
            stdOutLogLevel=_std_out_log_level,
            fileLogLevel=logging.INFO, # Not used if logFilePath is None
            logFormat="pipe-delimited", # Not critical if Datadog is enabled, as it uses its own format
            logBack=None, 
            enableTrace=_enable_trace
        )
        _auto_setup_done = True
    except Exception as e:
        sys.stderr.write(f"ERROR: Initial simplified log auto-configuration failed. Exception type: {type(e)}, Message: {e}\n")
        # Print full traceback for the auto-setup failure
        import traceback as tb_module # Alias to avoid conflict if 'traceback' is used as a var name elsewhere
        sys.stderr.write("Traceback for auto-setup failure (within log.py):\n")
        tb_module.print_exc(file=sys.stderr)
        
        _basic_handler = logging.StreamHandler(sys.stderr)
        _basic_formatter = logging.Formatter("[%(levelname)s] %(message)s")
        _basic_handler.setFormatter(_basic_formatter)
        
        _fallback_log = logging.getLogger("solace_ai_connector")
        if not _fallback_log.handlers: 
            _fallback_log.addHandler(_basic_handler)
            _fallback_log.setLevel(logging.WARNING) 
        _fallback_log.warning("Logging system fell back to basic stderr output due to simplified auto-setup error.")
