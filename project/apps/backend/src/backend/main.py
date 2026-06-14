from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.broker import broker

# ВАЖНО:
# просто импортируем файлы чтобы зарегистрировались subscriber'ы
import backend.consumers
import backend.event_consumer

from backend.routes.event_stream import router as event_router
from backend.routes.tasks import router as tasks_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Connecting RabbitMQ...")
    await broker.start()
    print("RabbitMQ connected")
    yield
    print("Stopping RabbitMQ...")
    await broker.stop()


app = FastAPI(
    title="Agent Testing Platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # потом заменить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    event_router,
    prefix="/api"
)
app.include_router(
    tasks_router,
    prefix="/api"
)


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }