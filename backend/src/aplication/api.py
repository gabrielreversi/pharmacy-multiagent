import logging
from contextlib import asynccontextmanager

import fastapi
import redis
import uvicorn
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from aplication.routes.ask import router, orchestrator

from aplication.routes.documents import router as documents_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    orchestrator.retrieval_service.repository.ensure_collection_with_retry()
    yield


app = fastapi.FastAPI(lifespan=lifespan)

app.include_router(router)
app.include_router(documents_router)


@app.exception_handler(OperationalError)
@app.exception_handler(redis.ConnectionError)
async def dependency_unavailable(request: fastapi.Request, exc: Exception):
    logging.getLogger(__name__).error("Dependência indisponível em %s: %s", request.url.path, exc)
    return JSONResponse(status_code=503, content={"detail": "Banco de dados ou fila indisponível no momento"})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
