from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import text

from src.db.main import engine, init_db
from src.routes.auth import router as auth_router
from src.routes.transaction import router as transaction_router
from src.routes.user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print('=' * 50, ' Starting up... ', '=' * 50)
    await init_db()
    yield

    # Exécute le checkpoint WAL pour forcer la sauvegarde de la db
    async with engine.begin() as conn:
        await conn.execute(text('PRAGMA wal_checkpoint(FULL);'))
        print('✅ WAL checkpoint effectué.')

    print('=' * 50, ' Shutting down... ', '=' * 50)


app = FastAPI(lifespan=lifespan)

origins = [
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    # Add more origins here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


app.include_router(user_router)
app.include_router(auth_router)
app.include_router(transaction_router)
