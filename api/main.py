from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers import Auth, User, Message, Group
from api.db.database import Base, engine

Base.metadata.create_all(bind=engine)
app = FastAPI()
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.include_router(Auth.router)
app.include_router(User.router)
app.include_router(Message.router)
app.include_router(Group.router)

