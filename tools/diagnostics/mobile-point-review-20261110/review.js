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
    };
  if (point.x < row.box[0] || point.x > row.box[2] || point.y < row.box[1] || point.y > row.box[3]) throw Error("구역 경계 안쪽을 선택하세요.");
  return point;
}

function validateAnswers(p, a) {
  if (!exactKeys(a,["schema_version","kind","packet_id","responses"]) || a.schema_version !== 1 || a.kind !== "surface_point_review_answers" || a.packet_id !== p.packet_id || !Array.isArray(a.responses)) throw Error("현재 위치 확인 묶음의 JSON이 필요합니다.");
  const index = new Map(), seen = new Set(); for (const e of p.entries) index.set(e.id,e);
  for (const r of a.responses) {
    if (!exactKeys(r,["id","image_sha256","region_target","judgment","point","note"]) || typeof r.id !== "string" || !index.has(r.id) || seen.has(r.id)) throw Error("알 수 없거나 중복된 항목입니다.");
    seen.add(r.id); const e=index.get(r.id), row=e.row;
    if (e.completed || r.image_sha256 !== row.image_sha256 || !Number.isInteger(r.region_target) || r.region_target !== row.target || typeof r.note !== "string") throw Error("이미 끝난 위치·구역 정답·사진은 바꾸지 않습니다.");
    if (r.judgment === "unknown") {if (r.point !== null) throw Error("모르겠음은 위치 정답으로 저장하지 않습니다.");}
    else if (r.judgment === "normal" || r.judgment === "defect") {
      if (!exactKeys(r.point,["x","y"]) || typeof r.point.x !== "number" || typeof r.point.y !== "number" || !Number.isFinite(r.point.x) || !Number.isFinite(r.point.y) || r.point.x < row.box[0] || r.point.x > row.box[2] || r.point.y < row.box[1] || r.point.y > row.box[3]) throw Error("확인한 위치를 원본 구역 안에 찍어주세요.");
    } else throw Error("정상·결함·모르겠음 중 직접 선택하세요.");
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
  const value = {schema_version: 1, kind: "surface_point_review_answers", packet_id: packet.packet_id, responses: Object.values(responses)};
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
    download.download = `surface-points-${packet.packet_id.slice(0, 12)}${batch}-${value.responses.length}.json`;
  }
}

function handleClick(event) {
  try {
    const button=event.target.closest("button"), card=event.target.closest("article[data-index]");
    if (button && button.id === "copy") {
      const field=document.getElementById("export");field.focus();field.select();field.setSelectionRange(0,field.value.length);
      let copied=false;try{copied=document.execCommand("copy");}catch{}
      document.getElementById("message").textContent=copied ? "JSON을 복사했습니다. 채팅에 붙여넣으세요." : "아래 JSON을 길게 눌러 전체 선택 후 복사하세요.";return;
    }
    if (!card) return;
    const entry=packet.entries[Number(card.dataset.index)], fields=card.querySelector("fieldset");
    if (button && button.dataset.action === "edit" && fields && !card.dataset.resumed) {
      delete responses[entry.id];fields.disabled=false;button.hidden=true;card.querySelector(".response-state").textContent="입력 수정 중 · 기존 구역 정답 유지";refreshExport();return;
    }
    if (!fields || fields.disabled) return;
    if (button && button.dataset.judgment) {
      fields.dataset.judgment=button.dataset.judgment;
      for (const choice of fields.querySelectorAll("button[data-judgment]")) choice.setAttribute("aria-pressed",String(choice===button));
    }
    const image=event.target.closest("img[data-locate]");
    if (image) {
      const point=pointFromClick(entry.row,image.getBoundingClientRect(),event.clientX,event.clientY,image.dataset.viewBox.split(",").map(Number));
      card.querySelector('[name="x"]').value=point.x;card.querySelector('[name="y"]').value=point.y;drawPoint(card,point);
    }
    if (button && button.dataset.action === "record") {
      const judgment=fields.dataset.judgment || "", x=card.querySelector('[name="x"]').value, y=card.querySelector('[name="y"]').value;
      const point=judgment !== "unknown" && x !== "" && y !== "" ? {x:Number(x),y:Number(y)} : null;
      const r={id:entry.id,image_sha256:entry.row.image_sha256,region_target:entry.row.target,judgment,point,note:card.querySelector('[name="note"]').value};
      validateAnswers(packet,{schema_version:1,kind:"surface_point_review_answers",packet_id:packet.packet_id,responses:[r]});
      responses[r.id]=r;fields.disabled=true;
      if (point) drawPoint(card,point);else {const marker=card.querySelector(".new-point");if(marker)marker.remove();}
      card.querySelector(".response-state").textContent=judgment === "unknown" ? "모르겠음 기록 · 정답으로 추정하지 않음" : "확인한 위치 판정 기록 · 구역 정답 유지";
      card.querySelector('[data-action="edit"]').hidden=false;refreshExport();
    }
  } catch(error){document.getElementById("message").textContent=error.message;}
}

async function handleChange(event) {
  try {
    const card=event.target.closest("article[data-index]");
    if (event.target.hasAttribute("data-candidate") && card) card.querySelector(".candidate").hidden=!event.target.checked;
    if (event.target.id === "resume" && event.target.files.length) {
      const a=validateAnswers(packet,JSON.parse(await event.target.files[0].text()));
      for (const r of a.responses) if (Object.hasOwn(responses,r.id) && JSON.stringify(responses[r.id])!==JSON.stringify(r)) throw Error("기존 답과 다릅니다. 덮어쓰지 않았습니다.");
      for (const r of a.responses) responses[r.id]=r;
      for (const current of document.querySelectorAll("article[data-index]")) {
        const r=responses[packet.entries[Number(current.dataset.index)].id];if(!r)continue;
        const fields=current.querySelector("fieldset");fields.dataset.judgment=r.judgment;fields.disabled=true;current.dataset.resumed="true";
        current.querySelector('[name="note"]').value=r.note;
        if (r.point) {current.querySelector('[name="x"]').value=r.point.x;current.querySelector('[name="y"]').value=r.point.y;drawPoint(current,r.point);}
        for (const choice of fields.querySelectorAll("button[data-judgment]")) choice.setAttribute("aria-pressed",String(choice.dataset.judgment===r.judgment));
        current.querySelector('[data-action="edit"]').hidden=true;current.querySelector(".response-state").textContent="기존 확인 답 재사용 · 다시 묻지 않음";
      }
      refreshExport();
    }
  }catch(error){document.getElementById("message").textContent=error.message;}
}

if (typeof document !== "undefined") {
  packet = JSON.parse(document.getElementById("packet").textContent);
  document.addEventListener("click", handleClick); document.addEventListener("change", handleChange); refreshExport();
}
if (typeof module !== "undefined") module.exports = {pointFromClick, validateAnswers};
