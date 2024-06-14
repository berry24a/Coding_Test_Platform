from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
import databases
import sqlalchemy
import requests
import os
import asyncio

DATABASE_URL = "mysql+mysqlconnector://ubuntu:ubuntu123@localhost/submission_db"  # 실제 서버에서는 변경된 db주소 입력
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

submissions = sqlalchemy.Table(
    "submissions",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String(32)),
    sqlalchemy.Column("password", sqlalchemy.String(64)),
    sqlalchemy.Column("code", sqlalchemy.Text),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime),
    sqlalchemy.Column("status", sqlalchemy.String(16)),
    sqlalchemy.Column("result", sqlalchemy.Text),
)

engine = sqlalchemy.create_engine(DATABASE_URL)
metadata.create_all(engine)

app = FastAPI()
# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

class Submission(BaseModel):
    username: str
    password: str
    code: str

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/submit", response_class=HTMLResponse)
async def create_submission(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    code = form.get("code")

    query = submissions.insert().values(
        username=username,
        password=password,
        code=code,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        status="SUBMITTED"
    )
    submission_id = await database.execute(query)

    # 실행 요청
    send_submission_to_exec_server(submission_id)
    return templates.TemplateResponse("result.html", {"request": request, "submission_id": submission_id})

EXEC_SERVER_URL = "http://localhost:8001"  # 실행 서버의 URL, 실제 서버에서는 변경된 실행 서버 주소 입력

@app.patch("/submission")
async def update_submission_status(status_dict: dict):
    id = status_dict['id']
    status = status_dict['status']
    query = submissions.update().where(submissions.c.id == id).values(
        status=status, updated_at=datetime.utcnow()
    )
    await database.execute(query)
    return {"message": "Submission status updated"}

@app.post("/submission/{id}/execute")
async def send_submission_to_exec_server(id: int):
    query = submissions.select().where(submissions.c.id == id)
    submission = await database.fetch_one(query)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # 실행 서버로 제출을 전송
    response = requests.post(f"{EXEC_SERVER_URL}/execute", json={"id": id})
    await asyncio.sleep(10)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to send submission to execution server")

    return {"message": "Submission sent to execution server"}

@app.get("/result/{id}")
async def get_result(id: int):
    query = submissions.select().where(submissions.c.id == id)
    submission = await database.fetch_one(query)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return {"status": submission.status, "result": submission.result}
