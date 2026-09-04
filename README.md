# 판재 주문 계산기 (외부 공개용)

- `index.html` : 고객이 품목을 고르면 총액(공급가·부가세·합계)이 나오고, 견적 요청서를 복사/공유할 수 있는 페이지
- `stock.json` : Notion 「외부 공개 재고」에서 자동으로 뽑은 품목·판매가·현재고 (매시 35분 갱신)
- 갱신은 Actions → "재고 갱신(stock.json)" 에서 수동 실행도 가능. Secrets 에 `NOTION_TOKEN` 필요.

## Worker(온라인 접수) 배포
- `worker.js` 를 고쳐서 main 에 push 하면 `Worker 배포(panel-order)` 워크플로가 Cloudflare 에 자동 배포합니다.
- 1회 준비: 저장소 **Settings → Secrets and variables → Actions → New repository secret** 에 `CLOUDFLARE_API_TOKEN`
  (Cloudflare 대시보드 → 프로필 → API 토큰 → *Cloudflare Workers 편집* 템플릿). 토큰이 없으면 워크플로는 실패하고 기존 배포는 그대로 유지됩니다.
- 재고 갱신(stock.json)은 매시 35분 (panel-sync 가 20분에 외부 공개 재고를 가용재고로 맞춘 뒤).
