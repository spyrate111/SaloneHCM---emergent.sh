"""Auth endpoints: login, logout, me."""
from fastapi import APIRouter, HTTPException, Depends, Request, Response

from core import db, get_current_user, verify_password, make_access, limiter
from models import LoginIn

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookie(resp: Response, token: str):
    resp.set_cookie(
        key="access_token", value=token, httponly=True, secure=True,
        samesite="none", max_age=43200, path="/",
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginIn, response: Response):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("company_id"):
        raise HTTPException(401, "User has no company assigned — contact your admin")
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    token = make_access(user["id"], user["email"], user["role"])
    _set_cookie(response, token)
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "employee_id": user.get("employee_id"),
        "company_id": user["company_id"],
        "company": {
            "id": company["id"],
            "name": company["name"],
            "tier": company["tier"],
            "label": company.get("label"),
            "features": company.get("features", []),
        } if company else None,
        "token": token,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    company = await db.companies.find_one({"id": user["company_id"]}, {"_id": 0})
    if company:
        user["company"] = {
            "id": company["id"],
            "name": company["name"],
            "tier": company["tier"],
            "label": company.get("label"),
            "features": company.get("features", []),
        }
    return user
