"use strict";
const fs = require("node:fs");
const vm = require("node:vm");
const {webcrypto} = require("node:crypto");

function box() { return {width: this.width, height: this.height}; }
async function decode() {
  if (this.failDecode) throw new Error("synthetic decode failure");
  this.complete = true; this.naturalWidth = this.expected[0]; this.naturalHeight = this.expected[1];
}
function listen(type, handler) { this.listeners.set(type, handler); }
function byId(id) { return this.elements.get(id) || null; }
function query(selector) {
  if (selector === "img[data-ref]") return this.images;
  if (selector === "[data-answer]") return this.answers;
  if (selector === "select[data-entry]") return this.selects;
  if (selector === "textarea[data-entry]") return this.notes;
  throw new Error("unimplemented synthetic selector " + selector);
}
function Observer(callback) { this.callback = callback; this.listeners = new Map(); this.observe = listen; this.records = []; this.takeRecords = this.records.splice.bind(this.records, 0); }
function makeHarness(page) {
  const packet = JSON.parse(page.match(/<script id="packet" type="application\/json">([^]*?)<\/script>/)[1]);
  const encoded = page.match(/<script id="assets" type="application\/json">([^]*?)<\/script>/)[1];
  const elements = new Map();
  const doc = {elements, images: [], answers: [], selects: [], notes: [], visibilityState: "visible", listeners: new Map(),
    getElementById: byId, querySelectorAll: query, addEventListener: listen};
  for (const id of ["status", "review", "response-controls", "export", "out"]) elements.set(id, {id, value: "", textContent: "", listeners: new Map(), addEventListener: listen});
  elements.set("packet", {textContent: JSON.stringify(packet)}); elements.set("assets", {textContent: encoded});
  for (const entry of packet.entries) {
    for (const asset of entry.assets) {
      const image = {id: entry.entry_id + "-" + asset.kind, dataset: {ref: asset.ref}, expected: asset.size,
        width: asset.size[0], height: asset.size[1], naturalWidth: 0, naturalHeight: 0, complete: false,
        src: "", currentSrc: "", isConnected: true, decode, getBoundingClientRect: box};
      elements.set(image.id, image); doc.images.push(image);
    }
    const select = {id: "answer-" + entry.entry_id, tagName: "SELECT", dataset: {entry: entry.entry_id}, value: "unreviewed", disabled: true};
    const note = {id: "note-" + entry.entry_id, tagName: "TEXTAREA", dataset: {entry: entry.entry_id}, value: "", disabled: true};
    elements.set(select.id, select); elements.set(note.id, note); doc.selects.push(select); doc.notes.push(note); doc.answers.push(select, note);
  }
  const window = {innerWidth: 800, innerHeight: 600, devicePixelRatio: 1, visualViewport: null, listeners: new Map(), addEventListener: listen};
  const context = vm.createContext({document: doc, window, crypto: webcrypto, URL, Blob, atob, TextEncoder, Uint8Array, MutationObserver: Observer, console});
  vm.runInContext(page.match(/<script id="display-code">([^]*?)<\/script>/)[1], context);
  const response = page.match(/<script id="response-code">([^]*?)<\/script>/);
  if (response) vm.runInContext(response[1], context);
  return {context, doc, packet, state: vm.runInContext("REVIEW", context)};
}
module.exports = {makeHarness};
