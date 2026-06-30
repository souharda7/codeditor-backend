from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email:str

class UserCreate(UserBase):
    password:str

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

class CodeSubmission(BaseModel):
    language: str
    code: str

class ScriptCreate(BaseModel):
    title: str
    code: str
    language: str

class ScriptResponse(ScriptCreate):
    id: int
    user_id: int

    class Config:
        from_attributes = True