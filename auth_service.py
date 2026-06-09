import time
import jwt
import os
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from database import get_db_connection

from dotenv import load_dotenv

# Loading environment variables from file
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security_scheme = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

# Connection path
@router.post("/login")
async def login(request: LoginRequest):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, role FROM users WHERE username = ?", (request.username,))
        row = cursor.fetchone()
        
    if not row or not pwd_context.verify(request.password, row[0]):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    token_payload = {
        "sub": request.username,
        "role": row[1],
        "exp": time.time() + 86400
    }
    token = jwt.encode(token_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    return {"status": "success", "token": token, "role": row[1]}
