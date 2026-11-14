/* Collect live mono audio without posting arbitrary file uploads. */
class BlackboxPCM extends AudioWorkletProcessor {
  constructor(options) {
    super(); this.samples = new Int16Array(4096); this.used = 0;
    this.measure = options?.processorOptions?.measure === true;
    this.startedAt = null;
    this.inputFrames = 0;
    this.missingBlocks = 0;
    this.nextReport = 0;
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
    if (this.measure) {
      this.startedAt ??= currentFrame;
      if (currentFrame >= this.nextReport) {
        this.nextReport = currentFrame + 5 * sampleRate;
        this.port.postMessage({type: 'sender-timing', sampleRate, startFrame: this.startedAt,
          frame: currentFrame, inputFrames: this.inputFrames, missingBlocks: this.missingBlocks});
      }
      this.inputFrames += input?.length ?? 0;
      if (!input?.length) this.missingBlocks++;
    }
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
