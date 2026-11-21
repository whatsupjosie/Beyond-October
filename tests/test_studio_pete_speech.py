"""Local synthesized audio drives the bundled Pete face in the real studio."""
import pytest

from tests.test_production25d_browser import (
    production_browser, production_server, studio, wait_for_actors,
)


def test_pete_speaks_and_returns_to_neutral(studio):
    page, _ = studio
    if not page.evaluate("async () => (await (await fetch('/api/tts/status')).json()).available"):
        pytest.skip("The host has no local speech provider")
    wait_for_actors(page)
    actor = page.locator('#performer').input_value()
    page.click('#castPete')
    page.wait_for_function("document.querySelector('#peteStatus').textContent.includes('is cast')")
    assert page.evaluate('id => PubCastGLB.info(id).hasJaw', actor)
    page.evaluate('''id => {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 500;
        const context = canvas.getContext('2d');
        const image = () => {
            context.clearRect(0, 0, 500, 500);
            PubCastGLB.draw(context, id, 250, 470, 430, {});
            return canvas.toDataURL();
        };
        const neutral = image();
        window.petePixelsChanged = () => image() !== neutral;
    }''', actor)
    page.click('#start')
    page.evaluate('''() => {
        const mixer = PubcastProgramAudio;
        mixer.ensureContext();
        const source = mixer.context.createMediaStreamSource(mixer.captureOutputStream());
        const meter = mixer.context.createAnalyser();
        source.connect(meter);
        const samples = new Float32Array(meter.fftSize);
        window.peteProgramAudible = () => {
            meter.getFloatTimeDomainData(samples);
            return samples.some(sample => Math.abs(sample) > .04);
        };
    }''')
    page.fill('#peteLine', 'The studio is live. This is Pete, speaking for the local recording test. '
              'We are checking that the stage performer moves and that the motion stops on cue.')
    page.click('#speakPete')
    page.wait_for_function('id => PubCastGLB.info(id).jaw > .02 && petePixelsChanged()', arg=actor)
    page.wait_for_function('peteProgramAudible()')
    page.click('#stopPete')
    page.wait_for_function('id => PubCastGLB.info(id).jaw === 0 && !petePixelsChanged()', arg=actor)
    assert page.locator('#peteStatus').inner_text() == 'Line stopped.'
    page.fill('#peteLine', 'This line will finish.')
    page.click('#speakPete')
    page.wait_for_function("document.querySelector('#peteStatus').textContent === 'Line finished.'")
    assert page.evaluate('id => PubCastGLB.info(id).jaw === 0', actor)
    assert not page.problems
    page.fill('#peteLine', 'Another line to stop during production shutdown.')
    page.click('#speakPete')
    page.wait_for_function('id => PubCastGLB.info(id).jaw > .02', arg=actor)
    page.click('#stop')
    page.wait_for_function('!PubCast25DStudio.state().session')
    assert page.locator('#speakPete').is_disabled()
    assert page.evaluate('id => PubCastGLB.info(id).jaw === 0', actor)
