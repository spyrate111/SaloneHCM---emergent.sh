"""Auth endpoints: login, logout, me."""
from fastapi import APIRouter, HTTPException, Depends, Response
from core import db, get_current_user, verify_password, make_access
from models import LoginIn

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(resp: Response, token: str):
    resp.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )


@router.post("/login")
async def login(body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    token = make_access(user["id"], user["email"], user["role"])
    _set_cookie(response, token)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "employee_id": user.get("employee_id"),
        "token": token,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return user
