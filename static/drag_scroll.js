/* Optional grab scrolling for remote viewers that translate touch into mouse input.
 * Native touch/pen scrolling and interactive controls keep their browser behavior.
 */
(function () {
  'use strict';
  const root = document.documentElement;
  if (!document.body.hasAttribute('data-drag-scroll')) return;
  const interactive = 'input,textarea,select,button,a,label,canvas,iframe,summary,[contenteditable]:not([contenteditable="false"]),[role="slider"],[data-no-drag-scroll]';
  const surfaces = new Set(['BODY', 'MAIN', 'SECTION', 'ARTICLE', 'ASIDE', 'FORM', 'FIELDSET', 'DIV']);
  let gesture = null, suppressClick = false;
  function finish() {
    if (!gesture) return;
    const old = gesture; gesture = null;
    root.classList.remove('drag-scroll-active');
    if (old.active) {
      suppressClick = true;
      try { old.target.releasePointerCapture(old.id); } catch (_) { /* already released */ }
    }
  }
  document.addEventListener('pointerdown', event => {
    suppressClick = false;
    if (gesture || event.pointerType !== 'mouse' || event.button !== 0 || !event.isPrimary || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const target = event.target;
    if (!(target instanceof Element) || !surfaces.has(target.tagName) || target.closest(interactive)) return;
    if (event.clientX >= root.clientWidth || event.clientY >= root.clientHeight) return;
    const scrollers = [];
    for (let el = target; el && el !== document.scrollingElement; el = el.parentElement) {
      const css = getComputedStyle(el);
      if (/(auto|scroll)/.test(css.overflowY) && el.scrollHeight > el.clientHeight) scrollers.push(el);
    }
    if (document.scrollingElement) scrollers.push(document.scrollingElement);
    if (!scrollers.some(el => el.scrollHeight > el.clientHeight)) return;
    gesture = {id:event.pointerId, target, scrollers, startY:event.clientY, y:event.clientY, active:false};
  });
  document.addEventListener('pointermove', event => {
    const g = gesture;
    if (!g || event.pointerId !== g.id) return;
    if (!(event.buttons & 1)) { finish(); return; }
    if (!g.active) {
      if (Math.abs(event.clientY - g.startY) < 8) return;
      g.active = true;
      try { g.target.setPointerCapture(g.id); } catch (_) { /* document listeners still track */ }
      root.classList.add('drag-scroll-active');
    }
    let remaining = g.y - event.clientY;
    g.y = event.clientY;
    for (const el of g.scrollers) {
      const before = el.scrollTop;
      el.scrollTop += remaining;
      remaining -= el.scrollTop - before;
      if (Math.abs(remaining) < 1) break;
    }
    event.preventDefault();
  }, {passive:false});
  for (const type of ['pointerup','pointercancel','lostpointercapture']) document.addEventListener(type, event => {
    if (gesture && event.pointerId === gesture.id) finish();
  });
  addEventListener('blur', finish);
  document.addEventListener('click', event => {
    if (!suppressClick || event.detail === 0) return;
    suppressClick = false; event.preventDefault(); event.stopPropagation();
  }, true);
})();
