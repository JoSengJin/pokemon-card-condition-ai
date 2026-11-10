"use strict";
let packet, responses = Object.create(null);

function exactKeys(value, keys) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    JSON.stringify(Object.keys(value).sort()) === JSON.stringify(keys.slice().sort());
}

function pointFromClick(row, rect, clientX, clientY, bounds = row.box) {
  if (!(rect.width > 0 && rect.height > 0)) throw Error("원본 표시 크기를 확인하세요.");
  const u = (clientX - rect.left) / rect.width, v = (clientY - rect.top) / rect.height;
  if (![u, v].every(Number.isFinite) || u < 0 || u > 1 || v < 0 || v > 1) throw Error("구역 안의 위치를 선택하세요.");
  const point = {x: bounds[0] + u * (bounds[2] - bounds[0]),
    y: bounds[1] + v * (bounds[3] - bounds[1]),
    label: row.target ? "surface_defect" : "normal_explanation"};
  if (point.x < row.box[0] || point.x > row.box[2] || point.y < row.box[1] || point.y > row.box[3]) throw Error("구역 경계 안쪽을 선택하세요.");
  return point;
}

function validateAnswers(p, a) {
  if (!exactKeys(a, ["schema_version", "kind", "packet_id", "responses"]) || a.schema_version !== 1 ||
      a.kind !== "surface_grounding_human_evidence" || a.packet_id !== p.packet_id || !Array.isArray(a.responses)) throw Error("다른 근거 묶음이거나 응답 형식이 다릅니다.");
  const index = new Map(), seen = new Set();
  for (const e of p.entries) index.set(e.row.id, e);
  for (const r of a.responses) {
    if (!exactKeys(r, ["id", "image_sha256", "target", "status", "point", "category", "note"]) || typeof r.id !== "string" || !index.has(r.id) || seen.has(r.id)) throw Error("알 수 없거나 중복된 구역/응답입니다.");
    seen.add(r.id); const e = index.get(r.id), row = e.row;
    if (!e.selected || e.known_points.length || !Number.isInteger(r.target) || r.target !== row.target || r.image_sha256 !== row.image_sha256 || typeof r.note !== "string") throw Error("확정 정답·사진·기존 위치를 바꿀 수 없습니다.");
    if (r.status === "cannot_localize") {
      if (r.point !== null || r.category !== "unclear") throw Error("판단 불가는 미확인 상태로 남깁니다.");
    } else if (r.status === "located") {
      const allowed = row.target ? ["surface_mark", "other"] : ["print_pattern", "reflection_or_cover", "other"];
      if (!allowed.includes(r.category) || !exactKeys(r.point, ["x", "y", "label"]) || r.point.label !== (row.target ? "surface_defect" : "normal_explanation")) throw Error("위치 종류와 설명을 확인하세요.");
      const x = r.point.x, y = r.point.y;
      if (typeof x !== "number" || typeof y !== "number" || !Number.isFinite(x) || !Number.isFinite(y) || x < row.box[0] || x > row.box[2] || y < row.box[1] || y > row.box[3]) throw Error("원본 사진 기준 구역 안의 좌표가 필요합니다.");
    } else throw Error("명시적으로 위치 또는 판단 불가를 선택하세요.");
  }
  return a;
}

function drawPoint(card, point) {
  const image = card.querySelector("img[data-locate]"), bounds = image.dataset.viewBox.split(",").map(Number);
  const layer = image.parentElement.querySelector(".point-layer");
  let marker = layer.querySelector(".new-point");
  if (!marker) { marker = document.createElement("span"); marker.setAttribute("class", "new-point"); layer.appendChild(marker); }
  marker.style.left = `${100 * (point.x - bounds[0]) / (bounds[2] - bounds[0])}%`;
  marker.style.top = `${100 * (point.y - bounds[1]) / (bounds[3] - bounds[1])}%`;
}

function refreshExport() {
  const value = {schema_version: 1, kind: "surface_grounding_human_evidence", packet_id: packet.packet_id, responses: Object.values(responses)};
  validateAnswers(packet, value);
  document.getElementById("export").value = JSON.stringify(value, null, 2);
  document.getElementById("answered").textContent = String(value.responses.length);
  const download = document.getElementById("download");
  if (download.dataset.objectUrl) URL.revokeObjectURL(download.dataset.objectUrl);
  delete download.dataset.objectUrl; download.removeAttribute("href");
  download.setAttribute("aria-disabled", String(value.responses.length === 0));
  download.tabIndex = value.responses.length ? 0 : -1;
  if (value.responses.length) {
    download.href = URL.createObjectURL(new Blob([document.getElementById("export").value], {type: "application/json;charset=utf-8"}));
    download.dataset.objectUrl = download.href;
    const batch = packet.batch_name ? `-${packet.batch_name}` : "";
    download.download = `surface-grounding-${packet.packet_id.slice(0, 12)}${batch}-${value.responses.length}.json`;
  }
}

async function handleClick(event) {
  try {
    const button = event.target.closest("button"), card = event.target.closest("article[data-index]");
    if (button && button.id === "copy") {
      const field = document.getElementById("export"); field.focus(); field.select();
      if (navigator.clipboard && navigator.clipboard.writeText) await navigator.clipboard.writeText(field.value);
      document.getElementById("message").textContent = "아래 JSON을 복사해 보관하세요. 새로고침 전 복사가 필요합니다."; return;
    }
    if (!card) return;
    const entry = packet.entries[Number(card.dataset.index)], fields = card.querySelector("fieldset");
    if (button && button.dataset.action === "edit" && fields && !card.dataset.resumed) {
      delete responses[entry.row.id]; fields.disabled = false; button.hidden = true;
      card.querySelector(".response-state").textContent = "미복사 설명 수정 중 · 기존 정답 유지"; refreshExport(); return;
    }
    if (!fields || fields.disabled) return;
    const row = entry.row, image = event.target.closest("img[data-locate]");
    if (image) {
      const point = pointFromClick(row, image.getBoundingClientRect(), event.clientX, event.clientY, image.dataset.viewBox.split(",").map(Number));
      card.querySelector('[name="x"]').value = point.x; card.querySelector('[name="y"]').value = point.y; drawPoint(card, point);
    }
    if (button && button.dataset.action === "record") {
      const status = card.querySelector('[name="status"]').value;
      const rawX = card.querySelector('[name="x"]').value, rawY = card.querySelector('[name="y"]').value;
      const point = status === "located" && rawX !== "" && rawY !== "" ? {x: Number(rawX), y: Number(rawY), label: row.target ? "surface_defect" : "normal_explanation"} : null;
      const r = {id: row.id, image_sha256: row.image_sha256, target: row.target, status, point,
        category: status === "cannot_localize" ? "unclear" : card.querySelector('[name="category"]').value,
        note: card.querySelector('[name="note"]').value};
      validateAnswers(packet, {schema_version: 1, kind: "surface_grounding_human_evidence", packet_id: packet.packet_id, responses: [r]});
      responses[r.id] = r; if (r.point) drawPoint(card, r.point); fields.disabled = true; card.querySelector(".response-state").textContent = status === "located" ? "위치 설명 기록됨 · 학습 미반영" : "위치 판단 불가 기록됨 · 정답 유지";
      card.querySelector('[data-action="edit"]').hidden = false; refreshExport();
    }
  } catch (error) { document.getElementById("message").textContent = error.message + " 복사가 안 되면 아래 JSON을 직접 선택해 복사하세요."; }
}

async function handleChange(event) {
  try {
    if (event.target.id === "filter") {
      for (const card of document.querySelectorAll("article[data-index]")) card.hidden = event.target.value !== "all" && card.dataset.outcome !== event.target.value;
    }
    if (event.target.id === "resume" && event.target.files.length) {
      const a = validateAnswers(packet, JSON.parse(await event.target.files[0].text()));
      for (const r of a.responses) {
        if (Object.hasOwn(responses, r.id) && JSON.stringify(responses[r.id]) !== JSON.stringify(r)) throw Error("이미 기록한 응답과 다릅니다. 기존 응답을 덮어쓰지 않았습니다.");
      }
      for (const r of a.responses) responses[r.id] = r;
      for (const card of document.querySelectorAll("article[data-index]")) {
        const r = responses[packet.entries[Number(card.dataset.index)].row.id];
        if (!r) continue;
        card.querySelector('[name="status"]').value = r.status; card.querySelector('[name="category"]').value = r.category;
        card.querySelector('[name="note"]').value = r.note;
        if (r.point) {card.querySelector('[name="x"]').value = r.point.x; card.querySelector('[name="y"]').value = r.point.y;}
        card.dataset.resumed = "true"; card.querySelector('[data-action="edit"]').hidden = true;
        card.querySelector("fieldset").disabled = true; card.querySelector(".response-state").textContent = "저장한 설명 재사용 · 재요청 없음";
        if (r.point) drawPoint(card, r.point);
      }
      refreshExport(); document.getElementById("message").textContent = "같은 근거 묶음의 기존 설명을 불러왔습니다.";
    }
  } catch (error) { document.getElementById("message").textContent = error.message; }
}

if (typeof document !== "undefined") {
  packet = JSON.parse(document.getElementById("packet").textContent);
  document.addEventListener("click", handleClick); document.addEventListener("change", handleChange); refreshExport();
}
if (typeof module !== "undefined") module.exports = {pointFromClick, validateAnswers};
