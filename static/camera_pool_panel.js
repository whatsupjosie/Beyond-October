/* Consent-based camera preview allocation and measured relay traffic. */
(function(){
"use strict";
const sheet=document.createElement("link");sheet.rel="stylesheet";sheet.href=new URL("camera_pool_panel.css",document.currentScript.src).href;document.head.appendChild(sheet);
const section=document.createElement("section");section.id="cameraPoolPanel";
section.style.cssText="position:relative;max-width:1400px;margin:18px auto;padding:16px;background:#142130;color:#edf1f7;border:1px solid #59718a;border-radius:9px;font:14px system-ui;overflow:auto";
section.innerHTML=`<h2>SESSION CAMERA POOL</h2>
<p>Share camera preview rendering with people who opt in. Program recording stays on the studio device. Previews use 640×360 JPEG frames; they are not a full-rate recording feed.</p>
<div><button type="button" id="poolCreate">Create preview pool from this studio</button>
<label>Pool <select id="poolSessions"><option value="">Choose a pool</option></select></label><button type="button" id="poolOpen">Open pool</button></div>
<p id="poolMessage" role="status" aria-live="polite">No pool selected. Participation is off by default.</p>
<label>Invite participants <input id="poolInvite" readonly style="width:min(90%,760px)" aria-label="Camera pool invitation link"></label>
<button type="button" id="poolContribute">Contribute from this device</button><div id="poolLocalWorker"></div>
<p>Traffic: participant → PubCast relay → operator monitors. Rates below measure JPEG payload over the last 5 seconds; render time is reported by the participant, not whole-device CPU usage.</p>
<div class="pool-table-scroll" tabindex="0" role="region" aria-label="Participant traffic and capacity"><table style="width:100%;text-align:left"><thead><tr><th>Participant / state</th><th>Consent limits</th><th>Assignments</th><th>Upload → relay</th><th>Relay → monitors</th><th>Frames / bytes</th><th>Last render</th></tr></thead><tbody id="poolMembers"></tbody></table></div>
<fieldset id="poolAssignment"><legend>Assign a camera preview</legend>
<label>Camera <select id="poolSource"></select></label> <label>Participant <select id="poolPerson"></select></label>
<label>Frames/s <input id="poolFps" type="number" min="1" max="4" value="2" style="width:65px"></label>
<button type="button" id="poolAssign">Assign task</button></fieldset><button type="button" id="poolClose">Close pool</button>
<div id="poolTasks" style="display:flex;gap:12px;flex-wrap:wrap"></div>`;
const flows=document.createElement("p");flows.id="poolFlows";section.appendChild(flows);
document.body.appendChild(section);
window.PubCastPoolPanelController.mount(section,flows);
})();
