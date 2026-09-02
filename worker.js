/**
 * 판재 주문 계산기 → Notion 자동 접수 (Cloudflare Worker)
 *
 * 하는 일: 계산기에서 "요청 보내기"를 누르면
 *   1) 「자재 프로젝트 보드」에 프로젝트 1건 생성 (업체명·연락처·배송지·요청사항)
 *   2) 「자재 사용 계획」에 품목별 행 생성 (판재 연결 + 수량, 유형=사용예정)
 *   → Notion 견적서 수식이 자동으로 견적을 만들어 줍니다.
 *
 * 설정 (Cloudflare 대시보드 → Workers → 이 워커 → Settings → Variables and Secrets)
 *   NOTION_TOKEN   (Secret)  Notion 통합 토큰 ntn_...
 *   ALLOW_ORIGIN   (Text, 선택) 기본 https://koretorian-byte.github.io
 */
const NOTION = "https://api.notion.com/v1";
const VER = "2022-06-28";
const DB_PROJECT = "자재 프로젝트 보드";
const DB_PLAN = "자재 사용 계획";
const DB_INV = "판재 재고 현황";

export default {
  async fetch(req, env) {
    const origin = env.ALLOW_ORIGIN || "https://koretorian-byte.github.io";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    if (req.method !== "POST") return json({ ok: false, error: "POST only" }, 405, cors);
    try {
      const body = await req.json();
      const company = str(body.company), contact = str(body.contact);
      const items = Array.isArray(body.items) ? body.items.slice(0, 60) : [];
      if (!company || !contact) return json({ ok: false, error: "업체명/연락처 필요" }, 400, cors);
      if (!items.length) return json({ ok: false, error: "품목 없음" }, 400, cors);

      const n = notion(env.NOTION_TOKEN);
      const [proj, plan, inv] = await Promise.all([findDb(n, DB_PROJECT), findDb(n, DB_PLAN), findDb(n, DB_INV)]);

      const today = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10); // KST
      const title = `[웹요청] ${company} ${today}`;
      const note = [str(body.note) && `요청사항: ${str(body.note)}`, str(body.address) && `배송지: ${str(body.address)}`,
        "── 웹 계산기 요청 원문 ──", str(body.text, 1800)].filter(Boolean).join("\n");

      const projProps = {
        "이름": { title: [{ text: { content: title } }] },
        "업체명": { rich_text: [{ text: { content: company } }] },
        "연락처": { phone_number: contact.slice(0, 100) },
        "현장/고객": { rich_text: [{ text: { content: str(body.address) || company } }] },
        "비고": { rich_text: [{ text: { content: note.slice(0, 2000) } }] },
      };
      if (proj.properties["입금상태"]) projProps["입금상태"] = { select: { name: "🔴 미입금" } };
      if (proj.properties["진행상태"]) projProps["진행상태"] = { select: { name: "01_접수" } }; // 웹 요청은 '접수' 단계로 들어옴
      const page = await n("POST", "/pages", { parent: { database_id: proj.id }, properties: projProps });

      const created = [], missing = [];
      for (const it of items) {
        const name = str(it.name), qty = Number(it.qty) || 0;
        if (!name || qty <= 0) continue;
        const panel = await findPanel(n, inv.id, name);
        if (!panel) { missing.push(name); continue; }
        await n("POST", "/pages", {
          parent: { database_id: plan.id },
          properties: {
            "이름": { title: [{ text: { content: `${company} - ${name}` } }] },
            "판재": { relation: [{ id: panel }] },
            "프로젝트": { relation: [{ id: page.id }] },
            "수량": { number: qty },
            "유형": { select: { name: "사용예정" } },
            "상태": { select: { name: "계획" } },
          },
        });
        created.push(name);
      }
      if (missing.length) {
        await n("PATCH", `/pages/${page.id}`, { properties: { "비고": { rich_text: [{ text: { content: (`⚠ 품목 매칭 실패: ${missing.join(", ")}\n` + note).slice(0, 2000) } }] } } });
      }
      return json({ ok: true, project: title, created: created.length, missing }, 200, cors);
    } catch (e) {
      return json({ ok: false, error: String(e.message || e).slice(0, 300) }, 500, cors);
    }
  },
};

function str(v, max = 500) { return (v == null ? "" : String(v)).trim().slice(0, max); }
function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), { status, headers: { ...headers, "Content-Type": "application/json; charset=utf-8" } });
}
function notion(token) {
  return async (method, path, body) => {
    const r = await fetch(NOTION + path, {
      method, headers: { Authorization: `Bearer ${token}`, "Notion-Version": VER, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const j = await r.json();
    if (!r.ok) throw new Error(`${path}: ${j.message || r.status}`);
    return j;
  };
}
async function findDb(n, name) {
  const r = await n("POST", "/search", { query: name, filter: { property: "object", value: "database" } });
  const db = r.results.find(d => (d.title || []).map(t => t.plain_text).join("").trim() === name);
  if (!db) throw new Error(`DB '${name}' 없음 (통합 연결 확인)`);
  return db;
}
async function findPanel(n, dbId, name) {
  // 계산기 품목명 → 판재 재고 현황 이름. 패브릭은 '패브릭N' → '패브릭N 원단'
  const candidates = [name, `${name} 원단`];
  for (const c of candidates) {
    const r = await n("POST", `/databases/${dbId}/query`, { filter: { property: "이름", title: { equals: c } }, page_size: 1 });
    if (r.results.length) return r.results[0].id;
  }
  return null;
}
