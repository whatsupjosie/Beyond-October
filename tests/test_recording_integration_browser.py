"""Integrated journal keeps ordinary short-stop and immediate PANIC contracts."""
from tests.test_production25d_browser import production_browser, production_server, studio, wait_for_actors


def delay_first_delivery(page, timeslice):
    # Use the real encoder; suppress explicit flushing and choose its delivery
    # timeslice to exercise Stop before the first dataavailable notification.
    page.evaluate("""timeslice => {
      const Native = MediaRecorder;
      window.MediaRecorder = class extends Native {
        constructor(...args) { super(...args); window.integrationRecorder = this;
          (window.integrationRecorders = window.integrationRecorders || []).push(this); }
        start() { return super.start(timeslice); }
        requestData() {}
      };
    }""", timeslice)
    wait_for_actors(page)
    page.click('#start')
    page.click('#record')
    page.wait_for_function('PubCast25DStudio.state().recording')


def test_short_stop_waits_for_native_media_and_commits_journal(studio):
    page, _ = studio
    delay_first_delivery(page, 1400)
    result = page.evaluate("""async () => {
      const started = performance.now();
      await PubCast25DStudio.stopRecording();
      const session = (await PubCast25DStore.list())[0];
      const saved = await PubCast25DStore.read(session.id);
      return {elapsed:performance.now()-started, bytes:saved.blob.size,
        incomplete:session.media.incomplete, journals:(await PubCast25DStore.listCaptures()).length};
    }""")
    assert result['elapsed'] >= 500
    assert result['bytes'] > 1000
    assert not result['incomplete'] and result['journals'] == 0
    assert page.problems == []


def test_panic_interrupts_an_already_waiting_ordinary_stop(studio):
    page, _ = studio
    delay_first_delivery(page, 60000)
    page.wait_for_timeout(500)  # encoder has frames, but has delivered no chunks
    result = page.evaluate("""async () => {
      const ordinary = PubCast25DStudio.stopRecording();
      await new Promise(resolve => setTimeout(resolve, 50));
      const started = performance.now();
      const immediate = PubCast25DStudio.stopRecording({immediate:true});
      while (integrationRecorder.state !== 'inactive') {
        if (performance.now()-started > 1000) throw Error('PANIC waited for encoder delivery');
        await new Promise(resolve => setTimeout(resolve, 10));
      }
      const elapsed = performance.now()-started;
      await Promise.all([ordinary, immediate]);
      return {elapsed, bytes:(await PubCast25DStore.read((await PubCast25DStore.list())[0].id)).blob.size};
    }""")
    assert result['elapsed'] < 1000
    assert result['bytes'] > 1000
    assert page.problems == []


def test_panic_stops_the_encoder_without_waiting_for_any_timer(studio):
    """2026-11-13: PANIC used to rely on the ordinary Stop's 100 ms poll noticing a
    flag. Browsers slow timers in background tabs, so that poll can take a second or
    longer. Here every short timer is held for five seconds; PANIC must still stop
    every encoder (program and independent sources) inside the PANIC call itself."""
    page, _ = studio
    delay_first_delivery(page, 60000)
    page.wait_for_timeout(500)
    result = page.evaluate("""async () => {
      const nativeTimeout = window.setTimeout;
      window.setTimeout = (fn, ms, ...rest) => nativeTimeout(fn, ms <= 200 ? 5000 : ms, ...rest);
      try {
        const ordinary = PubCast25DStudio.stopRecording();
        await Promise.resolve();
        const before = integrationRecorders.map(r => r.state);
        const immediate = PubCast25DStudio.stopRecording({immediate:true});
        const after = integrationRecorders.map(r => r.state);
        window.setTimeout = nativeTimeout;
        await Promise.all([ordinary, immediate]);
        const sessions = await PubCast25DStore.list();
        return {before, after, sessions: sessions.length,
          bytes:(await PubCast25DStore.read(sessions[0].id)).blob.size};
      } finally { window.setTimeout = nativeTimeout; }
    }""")
    # The program encoder and every independent voice/reference encoder.
    assert len(result['before']) >= 2 and set(result['before']) == {'recording'}
    assert set(result['after']) == {'inactive'}
    assert result['sessions'] == 1 and result['bytes'] > 1000
    assert page.problems == []
