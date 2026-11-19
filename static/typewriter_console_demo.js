/*
 * Bench page for the typewriter hotspots: puts what is typed onto the paper
 * and nothing more. The real typewriter mode listens to the same
 * "pubcast:key" event, so this file is the whole contract in miniature:
 *   detail.text    what to insert ("" for Shift and the blank key)
 *   detail.char    the key legend (A, 7, SPACE, RETURN, SHIFT, BACKSPACE ...)
 *   detail.source  "pointer" (finger, pen, mouse) or "keyboard"
 */
(function () {
  "use strict";

  document.addEventListener("pubcast:console-ready", function (ready) {
    const frame = ready.detail.frame;
    const paperBox = ready.detail.manifest.paper;
    if (!paperBox) return;

    const paper = document.createElement("div");
    paper.className = "pc-typewriter-paper";
    paper.setAttribute("data-typewriter-paper", "");
    paper.style.left = (paperBox.x * 100) + "%";
    paper.style.top = (paperBox.y * 100) + "%";
    paper.style.width = (paperBox.w * 100) + "%";
    paper.style.height = (paperBox.h * 100) + "%";
    frame.appendChild(paper);

    // Type size follows the width of the painted paper, so it looks the same on
    // a phone, a tablet and a desktop and in either orientation.
    const sizeType = function () {
      const px = Math.max(10, frame.clientWidth * paperBox.w * 0.052);
      paper.style.fontSize = px + "px";
    };
    sizeType();
    if (typeof ResizeObserver === "function") new ResizeObserver(sizeType).observe(frame);

    // The margin bell rings eight characters before the end of a line, once
    // per line, the way a typewriter warns that the carriage is nearly out.
    const measure = document.createElement("span");
    measure.textContent = "MMMMMMMMMM";
    measure.style.cssText = "position:absolute;left:0;top:0;visibility:hidden;white-space:pre;pointer-events:none";
    frame.appendChild(measure);
    const lineLength = function () {
      const style = getComputedStyle(paper);
      measure.style.font = style.font;
      const inner = paper.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
      const charWidth = measure.getBoundingClientRect().width / 10;
      return charWidth > 0 ? Math.floor(inner / charWidth) : 0;
    };
    const ringIfNearMargin = function (before, after) {
      const sound = window.PubCastTypewriterSound;
      const cols = lineLength();
      if (!sound || cols < 16) return;
      const column = (text) => text.length - text.lastIndexOf("\n") - 1;
      const warn = cols - 8;
      if (column(before) < warn && column(after) >= warn) sound.bell();
    };

    let typed = "";
    const render = function () {
      paper.textContent = typed;
      paper.classList.add("pc-typewriter-caret");
      paper.scrollTop = paper.scrollHeight;
    };

    frame.addEventListener("pubcast:key", function (event) {
      const key = event.detail;
      const before = typed;
      if (key.char === "BACKSPACE") typed = typed.slice(0, -1);
      else if (key.text) typed += key.text;
      ringIfNearMargin(before, typed);
      render();
    });
    render();
  });
})();
