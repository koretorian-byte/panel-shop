"""
Notion API 최소 클라이언트 (requests 기반, 외부 SDK 불필요)
- 환경변수: NOTION_TOKEN
"""
import os
import time
import requests

NOTION_VERSION = "2022-06-28"
TIMEOUT = 30


class NotionError(RuntimeError):
    pass


class Notion:
    def __init__(self, token=None):
        self.token = token or os.environ["NOTION_TOKEN"]
        self.http = requests.Session()
        self.http.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })

    def _req(self, method, path, **kw):
        for attempt in range(5):
            r = self.http.request(method, f"https://api.notion.com/v1{path}", timeout=TIMEOUT, **kw)
            if r.status_code == 429:  # rate limit
                time.sleep(float(r.headers.get("Retry-After", "1")))
                continue
            if r.status_code >= 400:
                raise NotionError(f"{method} {path} -> {r.status_code}: {r.text[:500]}")
            return r.json()
        raise NotionError(f"{method} {path}: 재시도 초과")

    # ---------- 데이터베이스 ----------
    def create_database(self, parent_page_id, title, properties, icon=None):
        body = {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": [{"type": "text", "text": {"content": title}}],
            "properties": properties,
        }
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        return self._req("POST", "/databases", json=body)

    def get_database(self, database_id):
        return self._req("GET", f"/databases/{database_id}")

    def search_databases(self, query):
        data = self._req("POST", "/search", json={"query": query, "filter": {"property": "object", "value": "database"}})
        return data.get("results", [])

    def update_database(self, database_id, properties):
        return self._req("PATCH", f"/databases/{database_id}", json={"properties": properties})

    def query_all(self, database_id, filter_=None, page_size=100):
        results, cursor = [], None
        while True:
            body = {"page_size": page_size}
            if filter_:
                body["filter"] = filter_
            if cursor:
                body["start_cursor"] = cursor
            data = self._req("POST", f"/databases/{database_id}/query", json=body)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                return results
            cursor = data.get("next_cursor")

    # ---------- 페이지 ----------
    def create_page(self, database_id, properties, icon=None):
        body = {"parent": {"database_id": database_id}, "properties": properties}
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        return self._req("POST", "/pages", json=body)

    def update_page(self, page_id, properties):
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": properties})

    def append_blocks(self, block_id, children):
        return self._req("PATCH", f"/blocks/{block_id}/children", json={"children": children})


# ---------- 속성 값 빌더 ----------
def title(text):
    return {"title": [{"type": "text", "text": {"content": str(text)[:2000]}}]}


def rich(text):
    return {"rich_text": [{"type": "text", "text": {"content": str(text)[:2000]}}]} if text not in (None, "") else {"rich_text": []}


def number(v):
    return {"number": (None if v in (None, "") else float(v))}


def select(name):
    return {"select": ({"name": str(name)} if name not in (None, "") else None)}


def date(iso):
    return {"date": ({"start": iso} if iso else None)}


def relation(page_ids):
    return {"relation": [{"id": p} for p in page_ids]}


def checkbox(v):
    return {"checkbox": bool(v)}


# ---------- 속성 값 읽기 ----------
def get_text(page, prop):
    p = page["properties"].get(prop) or {}
    t = p.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in p["title"])
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in p["rich_text"])
    if t == "select":
        return (p.get("select") or {}).get("name", "")
    if t == "formula":
        f = p["formula"]
        return f.get(f["type"])
    return ""


def get_number(page, prop):
    p = page["properties"].get(prop) or {}
    if p.get("type") == "number":
        return p.get("number")
    if p.get("type") == "formula":
        return p["formula"].get("number")
    if p.get("type") == "rollup":
        return p["rollup"].get("number")
    return None
