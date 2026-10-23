import os, sys
os.environ["DATABASE_URL"]="sqlite:///./test_tmp.db"
sys.path.insert(0,"api")
from fastapi.testclient import TestClient
import main
c=TestClient(main.app)
with c:
    H=lambda t:{"Authorization":"Bearer "+t}
    assert c.get("/check-username/alice").json()["available"]
    r=c.post("/register",json={"username":"alice","password":"password1"});assert r.status_code==201 and r.json()["role"]=="admin"
    assert c.post("/register",json={"username":"alice","password":"password1"}).status_code==409
    assert c.post("/register",json={"username":"bob","password":"password2"}).json()["role"]=="user"
    assert not c.get("/check-username/alice").json()["available"]
    assert c.post("/login",json={"username":"alice","password":"bad"}).status_code==401
    ta=c.post("/login",json={"username":"alice","password":"password1"}).json()["access_token"]
    tb=c.post("/login",json={"username":"bob","password":"password2"}).json()["access_token"]
    assert c.get("/me").status_code==401
    assert c.get("/me",headers=H(tb)).json()["username"]=="bob"
    assert c.get("/users",headers=H(tb)).status_code==403
    u=c.get("/users?page=1&page_size=1",headers=H(ta)).json();assert u["total"]==2 and len(u["items"])==1
    assert c.get("/users/1",headers=H(tb)).status_code==403
    assert c.put("/users/2",json={"display_name":"Bobby"},headers=H(tb)).json()["display_name"]=="Bobby"
    poses=[{"t":0,"x":1},{"t":1,"x":2}]
    assert c.post("/songs",json={"title":"Test","poses":poses},headers=H(tb)).status_code==403   # non-admin cannot add
    import base64
    r=c.post("/songs",json={"title":"Test","poses":poses,"tab_b64":base64.b64encode(b"GPDATA").decode(),"tab_name":"t.gp5","track":2,"track_name":"Lead"},headers=H(ta));assert r.status_code==201 and r.json()["num_keyframes"]==2
    sid=r.json()["id"]
    assert c.get("/status").json()["available"]
    it=c.get("/library").json()["items"];assert len(it)==1 and it[0]["id"]==str(sid) and it[0]["file"]=="t.gp5" and it[0]["track"]==2
    assert c.get(f"/jobs/{sid}/tab").content==b"GPDATA" and c.get(f"/jobs/{sid}/poses").json()==poses
    assert c.post("/convert").status_code==403 and "error" in c.post("/convert").json()
    assert c.post("/songs",json={"title":"x","poses":poses}).status_code==401
    assert c.get("/songs").json()["total"]==1 and c.get("/songs?q=zzz").json()["total"]==0
    assert c.get(f"/songs/{sid}/poses").json()==poses
    assert c.delete(f"/songs/{sid}",headers=H(ta)).status_code==200   # admin may delete
    assert c.post("/change-password",json={"old_password":"nope","new_password":"newpass123"},headers=H(tb)).status_code==400
    assert c.post("/change-password",json={"old_password":"password2","new_password":"newpass123"},headers=H(tb)).status_code==200
    assert c.get("/me",headers=H(tb)).status_code==401   # sessions revoked
    tb=c.post("/login",json={"username":"bob","password":"newpass123"}).json()["access_token"]
    assert c.post("/logout",headers=H(tb)).status_code==200
    assert c.get("/me",headers=H(tb)).status_code==401
    assert c.delete("/users/2",headers=H(ta)).status_code==200
    assert c.get("/users/2",headers=H(ta)).status_code==404
print("ALL TESTS PASSED")
