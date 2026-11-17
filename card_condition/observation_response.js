"use strict";
const STATES = ["unreviewed", "normal", "defect", "unassessable"];

function handleResponse(event) {
  const input = event.target;
  if (!input.dataset || !input.dataset.entry) return;
  if (!displayReady()) { invalidate(event); return; }
  const selected = document.getElementById("answer-" + input.dataset.entry);
  if (!selected || !STATES.includes(selected.value)) { invalidate(event); return; }
  observe("change", input.dataset.entry, selected.value);
}

function buildResponse() {
  if (!REVIEW.packet) throw new Error("packet not initialized");
  if (!displayReady()) invalidate({type: "export"});
  observe("export");
  const entries = [];
  for (const entry of REVIEW.packet.entries) {
    const state = document.getElementById("answer-" + entry.entry_id).value;
    if (!STATES.includes(state)) throw new Error("unknown state");
    entries.push({entry_id: entry.entry_id, photo_sha256: entry.photo_sha256, state,
      note: document.getElementById("note-" + entry.entry_id).value});
  }
  return {schema_version: 1, kind: "whole_surface_region_observation_response", packet_id: REVIEW.packet.packet_id,
    scope: "whole_surface_region", observation_mode: REVIEW.packet.observation_mode, session_id: REVIEW.session,
    data_origin: "synthetic_fixture", collection_status: "not_executable_pending_collection_contract_approval", entries,
    observations: {profile: JSON.parse(JSON.stringify(REVIEW.packet.profile)), instructions_sha256: REVIEW.packet.instructions_sha256,
      renderer_version: "synthetic-observation-v1", clock_source: "browser_self_report",
      assets: JSON.parse(JSON.stringify(REVIEW.proofs)), events: JSON.parse(JSON.stringify(REVIEW.events)),
      limitations: ["browser_self_report", "device_identity_unverified", "external_information_unverified", "attention_unverified", "zoom_detection_limited"]}};
}

function exportResponse(event) {
  const raw = JSON.stringify(buildResponse(), null, 2);
  document.getElementById("out").value = raw;
  return raw;
}

function attachResponseControls() {
  const root = document.getElementById("response-controls");
  root.addEventListener("change", handleResponse);
  root.addEventListener("input", handleResponse);
  document.getElementById("export").addEventListener("click", exportResponse);
}
