"use strict";
const REVIEW = {packet: null, ready: false, proofs: [], bindings: new Map(), events: [], session: null, invalidated: false, observer: null};

async function sha256(bytes) {
  const result = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  let hex = "";
  for (const value of result) hex += value.toString(16).padStart(2, "0");
  return hex;
}

function observe(event, entryId = null, state = null) {
  if (!REVIEW.packet) return;
  const images = [];
  for (const image of document.querySelectorAll("img[data-ref]")) {
    const rect = image.getBoundingClientRect();
    const bound = REVIEW.bindings.get(image.id);
    images.push({ref: image.dataset.ref, element_id: image.id, css_size: [rect.width, rect.height],
      natural_size: [image.naturalWidth || 0, image.naturalHeight || 0],
      current_src_matches: Boolean(bound && bound.image === image && image.isConnected &&
        image.src === bound.url && (image.currentSrc || image.src) === bound.url)});
  }
  REVIEW.events.push({event, at: new Date().toISOString(), utc_offset_minutes: new Date().getTimezoneOffset(),
    viewport_css: [window.innerWidth, window.innerHeight], device_pixel_ratio: window.devicePixelRatio || null,
    visibility: document.visibilityState || "unknown", visual_viewport_scale: window.visualViewport ? window.visualViewport.scale : null,
    entry_id: entryId, state, image_sizes: images});
}

function invalidate(event) {
  if (Array.isArray(event) && event.length === 0) return;
  REVIEW.invalidated = true;
  REVIEW.ready = false;
  for (const proof of REVIEW.proofs) proof.verified = false;
  for (const input of document.querySelectorAll("[data-answer]")) input.disabled = true;
  document.getElementById("status").textContent = "표시 확인 무효 · 입력 잠김 · 원응답 보존";
  observe("invalidate");
}

async function verifyAssets() {
  const encoded = JSON.parse(document.getElementById("assets").textContent);
  const expected = new Map();
  for (const entry of REVIEW.packet.entries) for (const asset of entry.assets) expected.set(asset.ref, asset);
  if (Object.keys(encoded).length !== expected.size) throw new Error("asset set mismatch");
  for (const [ref, asset] of expected) {
    if (typeof encoded[ref] !== "string") throw new Error("asset missing");
    const binary = atob(encoded[ref]);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const measured = await sha256(bytes);
    const proof = {ref, expected_sha256: asset.sha256, measured_sha256: measured, verified: false, decoded: false, element_ids: []};
    REVIEW.proofs.push(proof);
    if (measured !== asset.sha256) throw new Error("asset SHA mismatch");
    const url = URL.createObjectURL(new Blob([bytes], {type: ref.endsWith(".png") ? "image/png" : "image/jpeg"}));
    for (const entry of REVIEW.packet.entries) for (const item of entry.assets) {
      if (item.ref !== ref) continue;
      const id = entry.entry_id + "-" + item.kind;
      const image = document.getElementById(id);
      if (!image || image.dataset.ref !== ref) throw new Error("asset element mismatch");
      const pending = REVIEW.observer.takeRecords();
      if (pending.length) invalidate(pending);
      if (REVIEW.invalidated) throw new Error("display invalidated during initialization");
      image.src = url;
      const own = REVIEW.observer.takeRecords();
      for (const mutation of own) {
        if (mutation.type !== "attributes" || mutation.target !== image || mutation.attributeName !== "src") invalidate(own);
      }
      await image.decode();
      if (REVIEW.invalidated) throw new Error("display invalidated during decode");
      if (image.naturalWidth !== asset.size[0] || image.naturalHeight !== asset.size[1]) throw new Error("decoded size mismatch");
      REVIEW.bindings.set(id, {image, url, ref});
      proof.element_ids.push(id);
    }
    proof.decoded = true;
    proof.verified = true;
  }
}

function displayReady() {
  if (!REVIEW.ready || REVIEW.invalidated) return false;
  if (!REVIEW.packet.profile.zoom_allowed && window.visualViewport && window.visualViewport.scale !== 1) return false;
  for (const [id, bound] of REVIEW.bindings) {
    if (document.getElementById(id) !== bound.image || !bound.image.isConnected || bound.image.dataset.ref !== bound.ref || bound.image.src !== bound.url ||
        (bound.image.currentSrc || bound.image.src) !== bound.url || !bound.image.complete || !bound.image.naturalWidth) return false;
  }
  let count = 0;
  const refs = new Set();
  for (const entry of REVIEW.packet.entries) for (const asset of entry.assets) { count++; refs.add(asset.ref); }
  for (const proof of REVIEW.proofs) if (!proof.verified || !proof.decoded || !refs.delete(proof.ref)) return false;
  return REVIEW.bindings.size === count && refs.size === 0;
}

function handleEnvironment(event) {
  if (REVIEW.packet && !REVIEW.packet.profile.zoom_allowed && window.visualViewport && window.visualViewport.scale !== 1) invalidate(event);
  observe(event.type === "visibilitychange" ? "visibility" : event.type);
}

async function initialize() {
  for (const input of document.querySelectorAll("[data-answer]")) input.disabled = true;
  try {
    REVIEW.packet = JSON.parse(document.getElementById("packet").textContent);
    if (REVIEW.packet.data_origin !== "synthetic_fixture" || REVIEW.packet.collection_status !== "not_executable_pending_collection_contract_approval") throw new Error("synthetic guard");
    REVIEW.session = crypto.randomUUID();
    observe("ready");
    REVIEW.observer = new MutationObserver(invalidate);
    REVIEW.observer.observe(document.getElementById("review"), {attributes: true, attributeFilter: ["src", "srcset", "data-ref"], childList: true, subtree: true});
    await verifyAssets();
    if (REVIEW.invalidated) throw new Error("initialization invalidated");
    REVIEW.ready = true;
    if (!displayReady()) throw new Error("display not ready");
    for (const input of document.querySelectorAll("[data-answer]")) input.disabled = false;
    document.getElementById("status").textContent = "합성 이미지 확인 완료 · 실제 수집 미승인";
    observe("presented");
    window.addEventListener("resize", handleEnvironment);
    window.addEventListener("scroll", handleEnvironment);
    document.addEventListener("visibilitychange", handleEnvironment);
    if (window.visualViewport) window.visualViewport.addEventListener("resize", handleEnvironment);
  } catch (error) { invalidate(error); }
}
