/* One fifteen-second audio reference per local production. The pulse is generated
 * on the audio thread; video observations retain their measured frame timing.
 * This does not assert clock synchronization with another physical device. */
(function(global) {
  'use strict';
  async function create(context, session, onFailure, onMark) {
    await context.resume();
    await context.audioWorklet.addModule('/static/production25d_clacker_worklet.js');
    const originFrame = Math.round(context.sampleRate *
      (context.currentTime + (Date.parse(session.startedAt) - Date.now()) / 1000));
    const referenceId = global.PubCast25DCapture.id();
    const metadata = {
      id:referenceId, schema:'pubcast.clacker/1', intervalUs:15000000, sampleRate:context.sampleRate,
      originFrame, toneHz:1000, pulseUs:50000, videoPulseUs:500000, audioMarks:[], videoMarks:[],
      clockScope:'local-shared-audio-context', crossDeviceAlignment:'unmeasured'
    };
    (session.syncReferences || (session.syncReferences=[])).push(metadata);
    const destination = context.createMediaStreamDestination();
    const node = new AudioWorkletNode(context, 'pubcast-clacker', {
      numberOfInputs:0, numberOfOutputs:1, outputChannelCount:[1],
      processorOptions:{originFrame}
    });
    const silent = context.createGain(); silent.gain.value = 0;
    node.connect(destination); node.connect(silent); silent.connect(context.destination);
    let closed = false, lastVideo = -1, reference = null;
    const record = (list, mark) => {
      // Bounded to one day, matching the recording duration contract.
      if (list.length >= 5761) { onFailure(Error('Clacker reference exceeds one day')); return; }
      list.push(mark);
    };
    node.port.onmessage = event => {
      if (closed) return;
      record(metadata.audioMarks, {sequence:event.data.sequence, frame:event.data.frame,
        productionUs:event.data.sequence * 15000000});
      // A marker is a clock event, not a scene-render job. Paint it as soon as
      // the audio-thread notification arrives instead of waiting for another
      // complete Program/Preview render pass on the main thread.
      if (reference && onMark) {
        try { onMark(reference); }
        catch (error) { fail('Clacker video marker failed: ' + error.message); }
      }
    };
    const input = {id:'clacker-reference', label:'Clacker reference', kind:'sync-reference',
      reference:true, syncReferenceId:referenceId, rawStream:destination.stream};
    const fail = message => {
      if (closed || input.failure) return;
      input.failure = Error(message); onFailure(input.failure);
    };
    node.onprocessorerror = () => fail('Clacker audio processor failed');
    const clockChanged = () => { if (context.state !== 'running') fail('Recording audio clock stopped'); };
    context.addEventListener('statechange', clockChanged);
    reference = {
      input,
      get failed() { return !!input.failure; },
      paint(canvas, visible=true) {
        if (closed || !visible || context.state !== 'running') return;
        const frame = Math.round(context.currentTime * context.sampleRate);
        const elapsed = frame - originFrame;
        if (elapsed < 0) return;
        const sequence = Math.floor(elapsed / (context.sampleRate * 15));
        if (sequence < 1) return;
        const phase = elapsed / context.sampleRate - sequence * 15;
        if (phase >= .5) return;
        const first = lastVideo !== sequence;
        if (first) {
          lastVideo = sequence;
          record(metadata.videoMarks, {sequence, audioFrame:frame,
            productionUs:Math.round(elapsed * 1000000 / context.sampleRate),
            observedUnixMs:Date.now()});
        }
        const c = canvas.getContext('2d'); c.save(); c.setTransform(1,0,0,1,0,0);
        c.fillStyle='#ff2020'; c.fillRect(34,28,42,8);
        c.restore();
        return first;
      },
      close() {
        if (closed) return; closed = true;
        node.port.postMessage('stop'); node.port.onmessage=null; node.onprocessorerror=null;
        context.removeEventListener('statechange', clockChanged);
        node.disconnect(); silent.disconnect();
        destination.stream.getTracks().forEach(track => track.stop());
        node.port.close();
      }
    };
    return reference;
  }
  global.PubCast25DClacker = {create};
})(window);
