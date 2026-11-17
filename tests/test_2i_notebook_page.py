"""The notebook page of 2i: numbers on their paragraphs, the spiral, blank lines, the live word count.

Found on 2026-11-16 by opening 2i and looking at it, on `f47b11b`:
- a blank line between paragraphs collapsed in Collab and its number was printed over the next one;
- in Write the numbers counted paragraphs at a fixed row height, so every wrapped paragraph pushed the numbers
  below it off their lines;
- switching to the notebook from the standard page left the spiral blank until the window was resized;
- the word count stood still while typing.

These run in real Chromium against the real page opened from disk with its companion files (no host, network
blocked), at laptop and phone size. They skip when Playwright or its browser is unavailable.
"""
from __future__ import annotations

from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PAGE = Path(__file__).resolve().parents[1] / "2i" / "writers-room-v22.html"
TEXT = ("The lamp over the counter had been burning since four.\n\n"
        "Marguerite set the cup down without looking at it, the way she set down everything she meant to come "
        "back to, and for a while neither of them said anything at all.\n\n"
        "\"You're early,\" she said.")
SIZES = {"laptop": dict(viewport={"width": 1280, "height": 800}),
         "phone": dict(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)}

# The height of each number's box, and the height the same text really takes in the writing box.
NUMBERS = """() => {
  const cs = getComputedStyle(soloTextarea);
  const marks = [...document.querySelectorAll('#lineNumbers .line-numbers-strip > div')];
  const kept = soloTextarea.style.height;
  soloTextarea.style.height = '0px';
  const text = soloTextarea.scrollHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom);
  soloTextarea.style.height = kept;
  return {count: marks.length, heights: marks.map(m => m.getBoundingClientRect().height),
          text, row: parseFloat(lineNumbers.style.getPropertyValue('--solo-row')),
          shown: marks.map(m => getComputedStyle(m, '::before').content)};
}"""


@pytest.fixture(params=sorted(SIZES))
def page(request):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:  # no browser installed here
            pytest.skip(f"Chromium is not available: {error}")
        context = browser.new_context(**SIZES[request.param])
        context.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else route.abort())
        pg = context.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(PAGE.as_uri())
        pg.wait_for_function("typeof initializing !== 'undefined' && !initializing && typeof twoiSetPresentation === 'function'", timeout=20000)
        yield pg
        assert errors == []
        browser.close()


def _write(page, text=TEXT):
    page.click("#soloTextarea")
    page.keyboard.insert_text(text)
    page.wait_for_timeout(150)


@pytest.mark.parametrize("look", ["standard", "notebook"])
def test_each_number_is_as_tall_as_its_own_paragraph(page, look):
    page.evaluate("look => twoiSetPresentation(look)", look)
    _write(page)
    n = page.evaluate(NUMBERS)
    assert n["count"] == 5
    # blank paragraphs take one row; the long paragraph wraps and takes a whole number of rows, more than one
    rows = [h / n["row"] for h in n["heights"]]
    assert all(abs(r - round(r)) < 0.02 for r in rows), rows
    assert round(rows[1]) == 1 and round(rows[3]) == 1 and round(rows[2]) > 1, rows
    # together the numbers are exactly as tall as the text they stand beside
    assert abs(sum(n["heights"]) - n["text"]) <= 1, n


def test_numbers_follow_an_edit_in_the_middle_and_a_change_of_text_size(page):
    page.evaluate("twoiSetPresentation('notebook')")
    _write(page)
    before = page.evaluate(NUMBERS)
    # add a paragraph in the middle, the way typing does
    page.evaluate("""() => { const at = soloTextarea.value.indexOf('Marguerite');
      soloTextarea.setSelectionRange(at, at); }""")
    page.keyboard.insert_text("A new paragraph, set in between.\n")
    page.wait_for_timeout(150)
    after = page.evaluate(NUMBERS)
    assert after["count"] == before["count"] + 1
    assert abs(sum(after["heights"]) - after["text"]) <= 1, after
    page.evaluate("adjustZoom('manuscript', 1)")
    page.wait_for_timeout(150)
    larger = page.evaluate(NUMBERS)
    assert larger["row"] > after["row"]
    assert abs(sum(larger["heights"]) - larger["text"]) <= 1, larger


def test_numbers_stay_beside_the_last_lines_when_scrolled_to_the_end(page):
    page.evaluate("twoiSetPresentation('notebook')")
    _write(page, "\n".join(f"Paragraph {i} of a long manuscript." for i in range(1, 121)))
    page.evaluate("soloTextarea.scrollTop = soloTextarea.scrollHeight")
    page.wait_for_timeout(150)
    gap = page.evaluate("""() => { const cs = getComputedStyle(soloTextarea);
      const last = document.querySelector('#lineNumbers .line-numbers-strip > div:last-child').getBoundingClientRect();
      const box = soloTextarea.getBoundingClientRect();
      const textBottom = box.top + parseFloat(cs.paddingTop) + (soloTextarea.scrollHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)) - soloTextarea.scrollTop;
      return Math.abs(last.bottom - textBottom); }""")
    assert gap <= 1.5, gap


def test_the_spiral_is_drawn_when_the_notebook_comes_on_screen(page):
    page.evaluate("twoiSetPresentation('standard')")
    page.wait_for_timeout(100)
    page.evaluate("twoiSetPresentation('notebook')")
    page.wait_for_function("spineCanvas.width > 0 && spineCanvas.height > 0", timeout=5000)
    lit = page.evaluate("""() => { const x = spineCanvas.getContext('2d');
      const d = x.getImageData(0, 0, spineCanvas.width, spineCanvas.height).data; let n = 0;
      for (let i = 0; i < d.length; i += 4) if (d[i] > 180 && d[i + 1] > 150) n++; return n; }""")
    assert lit > 200, lit                      # brass was drawn, not a blank strip
    over = page.evaluate("spineCanvas.getBoundingClientRect().right - spineCanvas.parentElement.getBoundingClientRect().right")
    assert over >= 8, over                     # the coil reaches over the paper's edge to its holes


def test_a_blank_line_keeps_its_row_in_collab(page):
    page.evaluate("twoiSetPresentation('notebook')")
    _write(page)
    page.evaluate("document.getElementById('modeBadge').click()")
    page.wait_for_timeout(250)
    rows = page.evaluate("""[...document.querySelectorAll('#manuscriptLines .m-line')].map(e => {
      const r = e.getBoundingClientRect(), n = e.querySelector('.line-num').getBoundingClientRect();
      return {top: r.top, height: r.height, numberTop: n.top, numberBottom: n.bottom, text: e.textContent}; })""")
    assert len(rows) == 5
    one = rows[4]["height"]                     # the short last paragraph: one row at either size
    assert one >= 18
    assert abs(rows[1]["height"] - one) < 0.6 and abs(rows[3]["height"] - one) < 0.6, rows   # blank lines are full rows
    assert all(abs(r["height"] / one - round(r["height"] / one)) < 0.05 for r in rows), rows  # every line a whole number of rows
    for earlier, later in zip(rows, rows[1:]):                                              # no number over another
        assert earlier["numberBottom"] <= later["numberTop"] + 0.5, rows
    for row in rows:                                                                        # each number inside its own row
        assert row["top"] - 0.5 <= row["numberTop"] and row["numberBottom"] <= row["top"] + row["height"] + 0.5, row
    # and the text survives the trip there and back unchanged
    page.evaluate("document.getElementById('modeBadge').click()")
    assert page.evaluate("soloTextarea.value") == TEXT


def test_the_word_count_moves_while_typing_in_write_and_in_the_draft(page):
    page.click("#soloTextarea")
    page.keyboard.type("four words right here")
    page.wait_for_function("document.getElementById('wordCount').textContent === '4 words'", timeout=3000)
    assert page.text_content("#mcWordProgress") == "4 words"   # on a phone this sits in a closed drawer
    page.evaluate("document.getElementById('modeBadge').click()")
    page.wait_for_timeout(200)
    page.evaluate("draftArea.focus()")
    page.keyboard.type("and three more")
    page.wait_for_function("document.getElementById('wordCount').textContent === '7 words'", timeout=3000)
