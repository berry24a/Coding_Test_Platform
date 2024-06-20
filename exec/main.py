from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import databases
import sqlalchemy
import subprocess
import os
import requests
import asyncio

DATABASE_URL = "mysql+mysqlconnector://ubuntu:ubuntu123@localhost/submission_db"  # 실제 서버에서는 변경된 db주소 입력
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()
answer = open('answer.txt', 'r').read()

submissions = sqlalchemy.Table(
    "submissions",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String),
    sqlalchemy.Column("password", sqlalchemy.String),
    sqlalchemy.Column("code", sqlalchemy.Text),
    sqlalchemy.Column("created_at", sqlalchemy.DateTime),
    sqlalchemy.Column("updated_at", sqlalchemy.DateTime),
    sqlalchemy.Column("status", sqlalchemy.String),
    sqlalchemy.Column("result", sqlalchemy.Text),
)

engine = sqlalchemy.create_engine(DATABASE_URL)
metadata.create_all(engine)

app = FastAPI()

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

class Submission(BaseModel):
    id: int

@app.get("/new")
async def get_new_submission():
    query = submissions.select().where(submissions.c.status == "SUBMITTED")
    submission = await database.fetch_one(query)
    if submission:
        update_query = submissions.update().where(submissions.c.id == submission["id"]).values(status="PROCESSING")
        await database.execute(update_query)
        return submission
    else:
        return {"message": "No new submissions"}

MANAGE_SERVER_URL = "http://localhost:8000"  # 관리 서버의 URL, 실제 서버에서는 변경된 관리 서버의 URL 입력

@app.post("/execute")
async def execute_submission(submission: Submission):
    query = submissions.select().where(submissions.c.id == submission.id)
    result = await database.fetch_one(query)
    if not result:
        raise HTTPException(status_code=404, detail="Submission not found")

    code_path = f"code/{submission.id}.py"
    with open(code_path, "w") as code_file:
        code_file.write(result["code"])

    try:
        output = subprocess.check_output(["python3", code_path], stderr=subprocess.STDOUT, timeout=10)
        status = "CORRECT" if output.strip().decode('utf-8') == answer.strip() else "INCORRECT"
    except subprocess.TimeoutExpired:
        output = b"Execution timed out"
        status = "TIMEOUT"
    except subprocess.CalledProcessError as e:
        output = e.output
        status = "ERROR"

    update_query = submissions.update().where(submissions.c.id == submission.id).values(
        status=status, updated_at=datetime.utcnow(), result=output.decode("utf-8")
    )
    await database.execute(update_query)

    # 실행 결과를 관리 서버로 전송
    response = requests.patch(f"{MANAGE_SERVER_URL}/submission", json={"id": submission.id, "status": status})
    await asyncio.sleep(10)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to update submission status on manage server")

    return {"id": submission.id, "status": status, "output": output.decode("utf-8")}
