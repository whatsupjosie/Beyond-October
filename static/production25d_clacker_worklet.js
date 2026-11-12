/* A recording-only reference on the shared Web Audio sample clock. */
class PubCastClackerProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const origin = options.processorOptions?.originFrame;
    if (!Number.isSafeInteger(origin)) throw Error('Invalid clacker origin');
    this.origin = origin;
    this.interval = sampleRate * 15;
    this.duration = Math.round(sampleRate * .05);
    this.lastSequence = -1;
    this.active = true;
    this.port.onmessage = event => { if (event.data === 'stop') this.active = false; };
  }
  process(inputs, outputs) {
    if (!this.active) return false;
    const channel = outputs[0][0];
    for (let i = 0; i < channel.length; i++) {
      const elapsed = currentFrame + i - this.origin;
      if (elapsed < 0) { channel[i] = 0; continue; }
      const sequence = Math.floor(elapsed / this.interval);
      if (sequence < 1) { channel[i] = 0; continue; }
      const phase = elapsed - sequence * this.interval;
      if (phase === 0 && sequence !== this.lastSequence) {
        this.lastSequence = sequence;
        this.port.postMessage({sequence, frame:currentFrame + i});
      }
      // A short attack/release avoids clicks; the reference never enters Program.
      const envelope = Math.min(1, phase / (sampleRate * .002),
        (this.duration - phase) / (sampleRate * .002));
      channel[i] = phase < this.duration ? .25 * Math.max(0, envelope) *
        Math.sin(2 * Math.PI * 1000 * phase / sampleRate) : 0;
    }
    return true;
  }
}
registerProcessor('pubcast-clacker', PubCastClackerProcessor);
