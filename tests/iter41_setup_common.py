import time
import requests
from pymongo import MongoClient

BASE = open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=")[1].split()[0].rstrip("/")
API = f"{BASE}/api"
env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l)
db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]


def login(e, p):
    for _ in range(8):
        r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=20)
        if r.status_code != 429:
            break
        time.sleep(5)
    r.raise_for_status()
    return r.json()
