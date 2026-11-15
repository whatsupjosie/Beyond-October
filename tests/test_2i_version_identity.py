"""Version identity, branch isolation and revision-specific review."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from modules.writers_room import create_writers_room_router
from modules.route_security import current_identity

def test_version_family(tmp_path):
    app=FastAPI()
    app.include_router(create_writers_room_router(tmp_path))
    identity={"user_id":"a","role":"owner"}
    app.dependency_overrides[current_identity]=lambda:identity.copy()
    root="/api/writers-room/documents"
    def doc(text,rev):
        return {"title":"Story","state":{"committed":[text],"conversationIds":{"alex":"old"}},"expected_revision":rev}
    with TestClient(app) as c:
        assert c.put(root+"/story",json=doc("original",0)).status_code==200
        def get(id): return c.get(root+"/"+id+"/versions").json()
        def act(id,action):
            v=get(id)["current"]
            return c.post(root+"/"+id+"/version-action",json={"action":action,"expected_epoch":v["epoch"],"expected_revision":v["revision"]})
        assert get("story")["current"]["main_id"]=="story"
        assert act("story","reviewed").status_code==200
        assert get("story")["current"]["review_status"]=="reviewed"
        assert c.put(root+"/story",json=doc("changed",1)).status_code==200
        assert get("story")["current"]["review_status"]=="needs_review"
        first=c.post(root+"/story/fork",json={"source_revision":1,"title":"Alternate A"}).json()
        second=c.post(root+"/story/fork",json={"source_revision":2,"title":"Alternate B"}).json()
        a,b=first["id"],second["id"]
        assert first["state"]["committed"]==["original"]
        assert first["state"]["conversationIds"]=={}
        assert [v["ordinal"] for v in get(a)["versions"]]==[1,2,3]
        assert act(a,"working").status_code==200
        assert get(a)["current"]["main_id"]=="story"
        assert get(b)["current"]["working_id"]==a
        assert act(b,"depart").status_code==200
        assert act(b,"main").status_code==409
        assert act(b,"reactivate").status_code==200
        assert act(b,"main").status_code==200
        assert get(a)["current"]["main_id"]==b
        assert act(a,"depart").status_code==409
        assert c.get(root+"/story").json()["state"]["committed"]==["changed"]
        v=get(a)["current"]
        assert act(a,"reviewed").status_code==200
        assert c.post(root+"/"+a+"/version-action",json={"action":"main","expected_epoch":v["epoch"],"expected_revision":v["revision"]}).status_code==409
        identity["user_id"]="other"
        assert c.get(root+"/"+a+"/versions").status_code==404
        assert c.post(root+"/story/fork",json={"source_revision":1,"title":"not mine"}).status_code==404
