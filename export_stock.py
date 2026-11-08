"""외부 공개 재고(Notion) → stock.json  (온라인 견적 페이지가 읽는 파일)
환경변수 NOTION_TOKEN 필요. 한 시간마다 GitHub Actions가 자동 실행합니다.
"""
import datetime as dt
import json
import sys
import zoneinfo

from notion_api import Notion, get_text, get_number

KST = zoneinfo.ZoneInfo("Asia/Seoul")

# 샘플 상품 표기 (이름 → (규격 문구, 단위)). 새 샘플을 Notion에 추가하면 여기에도 한 줄 넣어 주세요.
SAMPLE_INFO = {
    "무늬목 보드 샘플북": ("무늬목 12종 컬렉션 · 12.25x15cm", "권"),
    "패브릭 보드 박스 샘플": ("패브릭 22종 컬렉션 · 개별 10x10cm", "박스"),
}


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
        # 온라인 견적 탭용 세부 분류: 우드보드 10T/19T, 패브릭 보드 10T/19T (우드 엣지는 그대로)
        sub = cat
        if cat in ("우드", "우드보드"):
            sub = "우드보드 10T" if "10T" in spec else "우드보드 19T"
        elif cat == "우드 엣지":
            sub = "우드 엣지 24mm" if "24mm" in name else "우드 엣지 50mm"
            spec = ("24mm" if "24mm" in name else "50mm") + " x 50m롤 · 두께 0.8mm"
        elif cat in ("패브릭", "패브릭 보드", "패브릭 완성보드"):
            import re
            num = int((re.search(r"(\d+)", name) or [0, 0])[1])
            if name.endswith("보드 10T"):
                sub = "패브릭 보드 10T"
                if "단면" not in spec:
                    spec = (spec or "10T 1220x3000") + " 단면"
            else:
                sub = "패브릭 보드 19T"
                # 19T 접착품은 단면. 뒷면 클린터치보드 색은 임시 배정(홀수=Chocolate, 짝수=Oatmeal) — 추후 정리 예정
                back = "Chocolate" if num % 2 else "Oatmeal"
                spec = f"19T 단면 · 뒷면 클린터치 {back}"
        unit = "롤" if cat == "우드 엣지" else "장"
        if cat == "샘플":
            # 샘플 상품(샘플북/박스): 규격 문구와 단위는 이름으로 결정. 샘플만 주문하면 택배/쇼룸 픽업 배송 옵션이 적용됨(index.html)
            sub = "샘플"
            info = SAMPLE_INFO.get(name) or next((v for k, v in SAMPLE_INFO.items() if k.split(" ")[0] in name), None)
            if info:
                spec, unit = info
        # 재고 수량은 외부에 내보내지 않는다 (경쟁사 노출 방지). 있음/없음만.
        items.append({"name": name, "category": sub, "spec": spec,
                      "unit": unit,
                      "price": get_number(pg, "판매가") or 0,
                      "available": (get_number(pg, "현재고") or 0) > 0,
                      "eta": (((pg["properties"].get("입고예정일") or {}).get("date") or {}).get("start") or "")[:10],
                      "photo": photo})
    order = {"우드보드 19T": 0, "우드보드 10T": 1, "우드 엣지 24mm": 2, "우드 엣지 50mm": 3, "패브릭 보드 19T": 4, "패브릭 보드 10T": 5, "샘플": 6}
    items.sort(key=lambda i: (order.get(i["category"], 9), i["name"]))
    with open("stock.json", "w", encoding="utf-8") as f:
        json.dump({"updated": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "items": items}, f, ensure_ascii=False, indent=1)
    print(f"stock.json {len(items)}건 저장")


if __name__ == "__main__":
    main()
