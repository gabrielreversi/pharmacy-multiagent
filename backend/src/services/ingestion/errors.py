import httpx
import openai
import redis
from azure.core.exceptions import HttpResponseError, ServiceRequestError, ServiceResponseError
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse
from sqlalchemy.exc import OperationalError


class IngestionError(Exception):
    transient = False

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class PermanentError(IngestionError):
    transient = False


class TransientError(IngestionError):
    transient = True


TRANSIENT_OPENAI = (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError, openai.InternalServerError)
TRANSIENT_NETWORK = (
    httpx.TransportError,
    ServiceRequestError,
    ServiceResponseError,
    ResponseHandlingException,
    OperationalError,
    redis.ConnectionError,
    redis.TimeoutError,
    ConnectionError,
    TimeoutError,
)


def classify(exc: Exception) -> IngestionError:
    if isinstance(exc, IngestionError):
        return exc
    message = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, TRANSIENT_OPENAI):
        return TransientError("EMBEDDING_UNAVAILABLE", message)
    if isinstance(exc, UnexpectedResponse) and (exc.status_code is None or exc.status_code >= 500):
        return TransientError("VECTOR_DB_UNAVAILABLE", message)
    if isinstance(exc, HttpResponseError) and (exc.status_code is None or exc.status_code == 429 or exc.status_code >= 500):
        return TransientError("STORAGE_UNAVAILABLE", message)
    if isinstance(exc, TRANSIENT_NETWORK):
        return TransientError("DEPENDENCY_UNAVAILABLE", message)
    return PermanentError("UNEXPECTED_ERROR", message)
