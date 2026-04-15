from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.database import engine, Base
from presentation.file import router as file_router
from presentation.auth import router as auth_router
import os

Base.metadata.create_all(bind=engine)

# Si le backend est derrière un reverse proxy, utilise root_path

app = FastAPI(
    title="UNamur Medical Institute",
    description="Core API for the UNamur Medical Institute project",
    version="1.0.0",
    root_path="/fastapi",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(file_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Welcome to the UNamur Medical Institute API!"}