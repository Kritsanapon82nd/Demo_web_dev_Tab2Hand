"""Tab2Hand REST API: auth + user management + song/pose storage (SQL)."""
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import (DateTime, ForeignKey, Integer, String, Text,
                        create_engine, func, select)
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column,
                            sessionmaker)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL.split("://", 1)[1]
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "24"))
MAX_POSES_BYTES = int(os.environ.get("MAX_POSES_BYTES", str(20 * 1024 * 1024)))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(10), default="user")  # user | admin
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


class AuthSession(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    revoked: Mapped[int] = mapped_column(Integer, default=0)


class Song(Base):
    __tablename__ = "songs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(String(500), default="")
    num_keyframes: Mapped[int] = mapped_column(Integer, default=0)
    poses_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=now)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000)
    return salt.hex() + "$" + h.hex()


def verify_password(pw: str, stored: str) -> bool:
    try:
        salt_hex, h_hex = stored.split("$")
        h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt_hex), 200_000)
        return hmac.compare_digest(h.hex(), h_hex)
    except ValueError:
        return False


def tok_hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def get_db():
    with SessionLocal() as db:
        yield db


def current_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == tok_hash(authorization[7:].strip())))
    if not s or s.revoked or s.expires_at < now():
        raise HTTPException(401, "invalid or expired token")
    u = db.get(User, s.user_id)
    if not u:
        raise HTTPException(401, "user not found")
    return u


def user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "display_name": u.display_name,
            "role": u.role, "created_at": u.created_at.isoformat()}


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(default="", max_length=64)


class LoginIn(BaseModel):
    username: str
    password: str


class ChangePw(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    username: Optional[str] = Field(default=None, min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: Optional[str] = Field(default=None, max_length=64)


class SongIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=500)
    poses: Any  # JSON produced by the converter (ik_poses_output.json)


app = FastAPI(title="Tab2Hand API")


@app.on_event("startup")
def init_db():
    Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return {"ok": True}


# ---------------- Authentication ----------------
@app.post("/register", status_code=201)
def register(body: Credentials, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(409, "username already taken")
    first = db.scalar(select(func.count(User.id))) == 0
    u = User(username=body.username, display_name=body.display_name or body.username,
             password_hash=hash_password(body.password), role="admin" if first else "user")
    db.add(u)
    db.commit()
    return user_out(u)


@app.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == body.username))
    if not u or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "wrong username or password")
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(token_hash=tok_hash(token), user_id=u.id,
                       expires_at=now() + dt.timedelta(hours=SESSION_HOURS)))
    db.commit()
    return {"access_token": token, "token_type": "bearer", "user": user_out(u)}


@app.post("/logout")
def logout(authorization: Optional[str] = Header(None), u: User = Depends(current_user),
           db: Session = Depends(get_db)):
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == tok_hash(authorization[7:].strip())))
    s.revoked = 1
    db.commit()
    return {"ok": True}


@app.post("/change-password")
def change_password(body: ChangePw, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, u.password_hash):
        raise HTTPException(400, "old password is wrong")
    u.password_hash = hash_password(body.new_password)
    # revoke all sessions so other devices must log in again
    for s in db.scalars(select(AuthSession).where(AuthSession.user_id == u.id)):
        s.revoked = 1
    db.commit()
    return {"ok": True, "detail": "password changed; please log in again"}


# ---------------- User management ----------------
@app.get("/me")
def me(u: User = Depends(current_user)):
    return user_out(u)


@app.get("/check-username/{name}")
def check_username(name: str, db: Session = Depends(get_db)):
    return {"username": name, "available": db.scalar(select(User).where(User.username == name)) is None}


@app.get("/users")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
               u: User = Depends(current_user), db: Session = Depends(get_db)):
    if u.role != "admin":
        raise HTTPException(403, "admin only")
    total = db.scalar(select(func.count(User.id)))
    rows = db.scalars(select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {"page": page, "page_size": page_size, "total": total, "items": [user_out(r) for r in rows]}


def _target(uid: int, u: User, db: Session) -> User:
    if u.id != uid and u.role != "admin":
        raise HTTPException(403, "not allowed")
    t = db.get(User, uid)
    if not t:
        raise HTTPException(404, "user not found")
    return t


@app.get("/users/{uid}")
def get_user(uid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return user_out(_target(uid, u, db))


@app.put("/users/{uid}")
def update_user(uid: int, body: UserUpdate, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _target(uid, u, db)
    if body.username and body.username != t.username:
        if db.scalar(select(User).where(User.username == body.username)):
            raise HTTPException(409, "username already taken")
        t.username = body.username
    if body.display_name is not None:
        t.display_name = body.display_name
    db.commit()
    return user_out(t)


@app.delete("/users/{uid}")
def delete_user(uid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _target(uid, u, db)
    for s in db.scalars(select(AuthSession).where(AuthSession.user_id == t.id)):
        db.delete(s)
    for sg in db.scalars(select(Song).where(Song.owner_id == t.id)):
        db.delete(sg)
    db.delete(t)
    db.commit()
    return {"ok": True}


# ---------------- Songs / poses (our own domain) ----------------
def song_out(s: Song, owner: str = "") -> dict:
    return {"id": s.id, "title": s.title, "note": s.note, "num_keyframes": s.num_keyframes,
            "owner_id": s.owner_id, "owner": owner, "created_at": s.created_at.isoformat()}


@app.post("/songs", status_code=201)
def create_song(body: SongIn, u: User = Depends(current_user), db: Session = Depends(get_db)):
    txt = json.dumps(body.poses, separators=(",", ":"))
    if len(txt.encode()) > MAX_POSES_BYTES:
        raise HTTPException(413, "poses too large")
    p = body.poses
    n = len(p) if isinstance(p, list) else len(p.get("keyframes", p.get("poses", []))) if isinstance(p, dict) else 0
    s = Song(owner_id=u.id, title=body.title, note=body.note, num_keyframes=n, poses_json=txt)
    db.add(s)
    db.commit()
    return song_out(s, u.username)


@app.get("/songs")
def list_songs(page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
               q: str = "", db: Session = Depends(get_db)):
    stmt = select(Song, User.username).join(User, User.id == Song.owner_id)
    cnt = select(func.count(Song.id))
    if q:
        stmt = stmt.where(Song.title.ilike(f"%{q}%"))
        cnt = cnt.where(Song.title.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Song.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"page": page, "page_size": page_size, "total": db.scalar(cnt),
            "items": [song_out(s, name) for s, name in rows]}


@app.get("/songs/{sid}")
def get_song(sid: int, db: Session = Depends(get_db)):
    s = db.get(Song, sid)
    if not s:
        raise HTTPException(404, "song not found")
    return song_out(s, db.get(User, s.owner_id).username)


@app.get("/songs/{sid}/poses")
def get_poses(sid: int, db: Session = Depends(get_db)):
    from fastapi.responses import Response
    s = db.get(Song, sid)
    if not s:
        raise HTTPException(404, "song not found")
    return Response(s.poses_json, media_type="application/json")


@app.delete("/songs/{sid}")
def delete_song(sid: int, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = db.get(Song, sid)
    if not s:
        raise HTTPException(404, "song not found")
    if s.owner_id != u.id and u.role != "admin":
        raise HTTPException(403, "not allowed")
    db.delete(s)
    db.commit()
    return {"ok": True}


# Single-container mode (Render etc.): serve web page at / and the API under /api
if os.environ.get("SERVE_WEB") == "1":
    from fastapi.staticfiles import StaticFiles
    Base.metadata.create_all(engine)
    _inner = app
    app = FastAPI(title="Tab2Hand")
    app.mount("/api", _inner)
    app.mount("/", StaticFiles(directory=os.environ.get("WEB_DIR", "/app/web"), html=True))
