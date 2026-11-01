/* Pete sprite player: 8-direction walk resolver + emotion portrait picker. */
(function (root) {
  'use strict';
  const DIR_ORDER = ['E', 'SE', 'S', 'SW', 'W', 'NW', 'N', 'NE']; // screen coords, y down

  function directionFromVector(dx, dy) {
    if (!dx && !dy) return null;
    const a = Math.atan2(dy, dx);                       // 0 = east, +pi/2 = south
    const i = ((Math.round(a / (Math.PI / 4)) % 8) + 8) % 8;
    return DIR_ORDER[i];
  }

  class PetePlayer {
    constructor(manifest, base) {
      this.m = manifest; this.base = base || '';
      this.dir = 'S'; this.dist = 0; this.walking = false;
      this.emotion = 'neutral'; this.lastPortrait = {};
    }
    move(dx, dy) {                                      // call every tick with movement in px
      const d = directionFromVector(dx, dy);
      this.walking = !!d;
      if (d) { this.dir = d; this.dist += Math.hypot(dx, dy); }
      return this.body();
    }
    stop() { this.walking = false; return this.body(); }
    body() {                                            // -> {src, mirror, phase}
      const cfg = this.m.directions[this.dir], set = cfg.set;
      const w = this.m.walk[set];
      if (this.walking && w.frames.length) {
        const n = w.frames.length;
        const phase = Math.floor(((this.dist / this.m.stridePx) % 1) * n) % n;
        return { src: this.base + w.frames[phase], mirror: cfg.mirror, phase, still: false };
      }
      const src = this.walking && w.still ? w.still : this.m.idle[set];
      return { src: this.base + src, mirror: cfg.mirror, phase: 0, still: true };
    }
    setEmotion(e) { if (this.m.portraits[e]) this.emotion = e; return this.emotion; }
    portrait(e) {                                       // random variant, never the same twice in a row
      e = this.m.portraits[e || this.emotion] ? (e || this.emotion) : 'neutral';
      const pool = this.m.portraits[e];
      let pick = pool[0];
      if (pool.length > 1) {
        do { pick = pool[Math.floor(Math.random() * pool.length)]; } while (pick === this.lastPortrait[e]);
      }
      this.lastPortrait[e] = pick;
      return this.base + pick;
    }
  }
  root.PetePlayer = PetePlayer; root.directionFromVector = directionFromVector;
  if (typeof module !== 'undefined') module.exports = { PetePlayer, directionFromVector };
})(typeof window !== 'undefined' ? window : globalThis);
