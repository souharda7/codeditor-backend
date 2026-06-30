from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional
import subprocess
import os
import uuid

import models
import schemas
import auth
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeSubmission(BaseModel):
    language: str
    code: str
    stdin: Optional[str] = ""

@app.get("/")
def read_root():
    return {"status": "Online Code Editor API is running"}

@app.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, password=hashed_password)

    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@app.post("/login")
def login_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()

    if not db_user or not auth.verify_password(user.password, db_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token_expires=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.email},
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return users

@app.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == request.email).first()

    if user:
        reset_token = auth.create_access_token(
            data={"sub": user.email},
            expires_delta=timedelta(minutes=15)
        )

        reset_link = f"https://codeditorcompiler.vercel.app/?reset_token={reset_token}"
        print("\n" + "="*50)
        print(f"EMAIL TO: {user.email}")
        print(f"SUBJECT: Reset your CodeditoR password")
        print(f"BODY: Click this secure link to reset your password")
        print(f"{reset_link}")
        print("="*50 + "\n")

    return {"message" : "If the email exists in our system, a reset link has been sent."}

@app.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    email = auth.verify_password

@app.post("/execute")
def execute_code(submission: CodeSubmission):
    unique_id = str(uuid.uuid4())

    if submission.language == "python":
        file_name = f"{unique_id}.py"
        with open (file_name, "w") as f:
            f.write(submission.code)

        try:
            result = subprocess.run(
                ["python3", file_name],
                input=submission.stdin,
                capture_output=True,
                text=True,
                timeout=5
            )            
            return {
                "stdout" : result.stdout,
                "stderr" : result.stderr,
                "exit_code" : result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error": "Execution timed out (5s limit)"}
        finally:
            if os.path.exists(file_name):
                os.remove(file_name)

    elif submission.language == "cpp":
        source_file = f"{unique_id}.cpp"
        binary_file = f"{unique_id}.out"

        with open(source_file, "w") as f:
            f.write(submission.code)

        compile_result = subprocess.run(
            ["g++", source_file, "-o", binary_file],
            capture_output=True,
            text=True
        )

        if compile_result.returncode!=0:
            if os.path.exists(source_file):
                os.remove(source_file)
            return {
                "stdout" : "",
                "stderr" : compile_result.stderr,
                "exit_code" : compile_result.returncode
            }

        try:
            result = subprocess.run(
                [f"./{binary_file}"],
                input=submission.stdin,
                capture_output=True,
                text=True,
                timeout=5
            )
            return {
                "stdout" : result.stdout,
                "stderr" : result.stderr,
                "exit_code" : result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"error" : "Execution timed out (5s limit)"}
        finally:
            if os.path.exists(source_file):
                os.remove(source_file)
            if os.path.exists(binary_file):
                os.remove(binary_file)

    else :
        raise HTTPException(status_code=400, detail="Unsupported language!")