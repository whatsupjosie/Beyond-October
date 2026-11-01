/* Collect live mono audio without posting arbitrary file uploads. */
class BlackboxPCM extends AudioWorkletProcessor {
  constructor() {
    super(); this.samples = new Int16Array(4096); this.used = 0;
    this.port.onmessage = event => {
      if (event.data === 'flush') {
        if (this.used) {
          const tail = this.samples.slice(0, this.used);
          this.port.postMessage(tail.buffer, [tail.buffer]); this.used = 0;
        }
        this.port.postMessage('flushed');
      }
    };
  }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (input) for (const sample of input) {
      this.samples[this.used++] = Math.round(Math.max(-1, Math.min(1, sample)) * 32767);
      if (this.used === this.samples.length) {
        this.port.postMessage(this.samples.buffer, [this.samples.buffer]);
        this.samples = new Int16Array(4096); this.used = 0;
      }
    }
    return true;
  }
}
registerProcessor('blackbox-pcm', BlackboxPCM);
