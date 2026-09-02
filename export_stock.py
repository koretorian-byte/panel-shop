"""외부 공개 재고(Notion) → stock.json  (주문 계산기 페이지가 읽는 파일)
환경변수 NOTION_TOKEN 필요. 한 시간마다 GitHub Actions가 자동 실행합니다.
"""
import datetime as dt
import json
import sys
import zoneinfo

from notion_api import Notion, get_text, get_number

KST = zoneinfo.ZoneInfo("Asia/Seoul")


def find_db(n, name):
    for d in n.search_databases(name):
        if "".join(x["plain_text"] for x in d.get("title", [])).strip() == name:
            return d["id"]
    sys.exit(f"DB '{name}' 을 찾지 못했습니다. Notion 페이지 ⋯ → 연결 에 통합이 추가돼 있는지 확인하세요.")


def main():
    n = Notion()
    db = find_db(n, "외부 공개 재고")
    items = []
    for pg in n.query_all(db):
        name = get_text(pg, "이름").strip()
        if not name:
            continue
        cat = get_text(pg, "분류")
        thick = get_number(pg, "두께(mm)")
        spec = " ".join(x for x in [f"{thick:g}T" if thick else "", get_text(pg, "규격"), get_text(pg, "면")] if x)
        photo = ""
        files = pg["properties"].get("사진", {}).get("files") or []
        if files:
            photo = files[0].get("external", {}).get("url") or ""  # Notion 업로드 파일은 1시간 만료라 외부 링크만 사용
        items.append({"name": name, "category": cat, "spec": spec,
                      "unit": "롤" if cat == "우드 엣지" else "장",
                      "price": get_number(pg, "판매가") or 0,
                      "stock": get_number(pg, "현재고") or 0, "photo": photo})
    order = {"우드": 0, "우드보드": 0, "우드 엣지": 1, "패브릭": 2, "패브릭 보드": 2}
    items.sort(key=lambda i: (order.get(i["category"], 9), i["name"]))
    with open("stock.json", "w", encoding="utf-8") as f:
        json.dump({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}, f, ensure_ascii=False, indent=1)
    print(f"stock.json {len(items)}건 저장")


if __name__ == "__main__":
    main()
