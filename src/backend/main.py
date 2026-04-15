from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="UNamur Medical Institute",
    description="Core API for the UNamur Medical Institute project",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

@app.get("/")
def root():
    return {"message": "Welcome to the UNamur Medical Institute API!"}