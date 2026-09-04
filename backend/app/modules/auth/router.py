"""Auth routes: thin handlers delegating to service."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import create_access_token
from app.modules.auth import schemas, service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: schemas.RegisterIn, db: Session = Depends(get_db)):
    try:
        user = service.register_user(db, body.email, body.password, body.display_name)
    except ValueError:
        raise HTTPException(status_code=400, detail="email_taken")
    return schemas.TokenOut(access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=schemas.TokenOut)
def login(body: schemas.LoginIn, db: Session = Depends(get_db)):
    user = service.authenticate(db, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid_credentials")
    return schemas.TokenOut(access_token=create_access_token(str(user.id)))
