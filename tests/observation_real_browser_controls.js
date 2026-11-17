"use strict";
// Test-only buttons in generated output; production verification is never replaced.
async function rawProof() {
  const bytes = new TextEncoder().encode(document.getElementById("out").value);
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  let digest = "";
  for (const value of hash) digest += value.toString(16).padStart(2,"0");
  document.getElementById("raw-proof").textContent = JSON.stringify({bytes:bytes.length,sha256:digest});
}
function testMutation(event) {
  const image = document.getElementById("r1-context") || window.testDetached;
  if (event.target.id === "css-zero") image.style.width = "0px";
  if (event.target.id === "css-restore") image.style.width = "";
  if (event.target.id === "ref-change") image.dataset.ref = "assets/changed.png";
  if (event.target.id === "ref-restore") image.dataset.ref = "assets/a1.png";
  if (event.target.id === "src-change") { window.testSrc = image.src; image.src = "data:image/png;base64,AA=="; }
  if (event.target.id === "src-restore") image.src = window.testSrc;
  if (event.target.id === "detach") { window.testDetached = image; image.remove(); }
  if (event.target.id === "reattach") document.querySelector("article").append(image);
}
document.getElementById("test-actions").addEventListener("click",testMutation);
document.getElementById("start-test").addEventListener("click",initialize);
document.getElementById("proof-test").addEventListener("click",rawProof);
document.getElementById("environment").textContent = JSON.stringify({userAgent:navigator.userAgent,viewport:[innerWidth,innerHeight],dpr:devicePixelRatio,secureContext:isSecureContext});
