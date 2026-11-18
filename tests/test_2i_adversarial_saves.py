"""Adversarial save tests for 2i file mode, against the served 2i page in a real browser.

Oracles are independent of the code under test:
- write count: a browser-level hook on IDBObjectStore.put (Foresight's own counters are not used);
- stored text: raw IndexedDB reads of the 'files' store and of the exit journal, not Foresight's record().

Each test was run against the parent commit 7e70e05 to confirm it can fail; see
docs/2i-adversarial-save-findings-2026-11-18.md for the before/after evidence.
"""

from tests.test_foresight_file_workspace import editor, page  # noqa: F401  (fixture re-used on purpose)

COUNT_PUTS = """
(() => {
  const put = IDBObjectStore.prototype.put;
  window.__idbPuts = 0; window.__exitPuts = 0;
  IDBObjectStore.prototype.put = function (...args) {
    if (this.name === 'files') window.__idbPuts++;
    if (this.name === 'exit') window.__exitPuts++;
    return put.apply(this, args);
  };
})();
"""

RAW_GET = """
async ([prefix, store, id, write]) => {
  const dbs = (await indexedDB.databases()).filter(d => d.name && d.name.startsWith(prefix));
  for (const info of dbs) {
    const db = await new Promise((ok, no) => { const r = indexedDB.open(info.name); r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error); });
    if (!db.objectStoreNames.contains(store)) { db.close(); continue; }
    const rec = await new Promise((ok, no) => {
      const t = db.transaction(store, write ? 'readwrite' : 'readonly'), s = t.objectStore(store);
      const q = s.get(id);
      q.onsuccess = () => {
        if (write && q.result) s.put({ ...q.result, ...write.fields, revision: (q.result.revision || 0) + write.bump });
      };
      t.oncomplete = () => ok(q.result); t.onerror = () => no(t.error);
    });
    db.close();
    if (rec) return { draft: rec.draft ?? null, revision: rec.revision ?? null, baseRevision: rec.baseRevision ?? null };
  }
  return null;
}
"""


def open_2i_file(page, text="start\n"):
    page.context.add_init_script(COUNT_PUTS)
    page.evaluate(f"openFile('notes.txt', {text!r})")
    ed = editor(page)
    ed.wait_for()
    wait_status(page, "ready")
    return ed


def wait_status(page, fragment, timeout=15000):
    page.wait_for_function(
        "f => document.querySelector('#host iframe')?.contentWindow.document.querySelector('.ff-workspace [role=status]')?.textContent.includes(f)",
        arg=fragment,
        timeout=timeout,
    )


def wait_settled(page, timeout=15000):
    """The file pane finished opening: either the normal ready message or the exit-journal recovery message."""
    page.wait_for_function(
        "() => { const t = document.querySelector('#host iframe')?.contentWindow.document.querySelector('.ff-workspace [role=status]')?.textContent || ''; return t.includes('ready') || t.includes('Recovered your last edits'); }",
        timeout=timeout,
    )


def status(page):
    return _frame(page).evaluate("document.querySelector('.ff-workspace [role=status]')?.textContent || ''")


def _frame(page):
    return next(f for f in page.frames if f.parent_frame is not None and "writers-room" in f.url)


def stored(page, fid):
    return _frame(page).evaluate(RAW_GET, ["pubcast-foresight-files-v1", "files", fid, None])


def journal(page, fid):
    return _frame(page).evaluate(RAW_GET, ["pubcast-foresight-exit-v1", "exit", fid, None])


def file_id(page):
    return page.evaluate("c.data.fileId")


def test_forty_keystrokes_do_not_cause_forty_storage_writes(page):
    """Real keyboard input, real debounce. Writes must be bounded and the stored text must be the typed text."""
    ed = open_2i_file(page)
    fid = file_id(page)
    before = _frame(page).evaluate("window.__idbPuts")
    ed.click()
    ed.press_sequentially("abcdefghij" * 4, delay=5)  # 40 keystrokes, 5 ms apart
    expected = "start\n" + "abcdefghij" * 4
    page.wait_for_timeout(1500)  # longer than the 350 ms debounce, so every pending save has run
    writes = _frame(page).evaluate("window.__idbPuts") - before
    rec = stored(page, fid)
    print({"keystrokes": 40, "storage_puts": writes})
    assert ed.input_value() == expected
    assert rec is not None and rec["draft"] == expected, "stored text is not the typed text"
    assert writes <= 3, f"40 keystrokes caused {writes} storage writes (budget 3)"


def test_edit_then_reload_inside_debounce_window_is_recovered_and_stored(page):
    """Type, then reload before the 350 ms debounce fires. The whole edit must come back and be stored."""
    ed = open_2i_file(page)
    fid = file_id(page)
    ed.click()
    ed.press_sequentially("LAST-EDIT-BEFORE-RELOAD", delay=2)
    page.reload()
    page.evaluate("restore()")
    # Either path is acceptable (recovered from the exit journal, or already saved normally); the text is what counts.
    wait_settled(page)
    expected = "start\nLAST-EDIT-BEFORE-RELOAD"
    assert editor(page).input_value() == expected
    rec = stored(page, fid)
    assert rec is not None and rec["draft"] == expected, f"stored after recovery: {rec!r}"
    assert journal(page, fid) is None, "exit journal must be removed once its text is stored"


def test_clean_save_then_reload_leaves_no_journal_and_no_recovery(page):
    """A save that finished before the reload must not be 'recovered' again or leave journal residue."""
    ed = open_2i_file(page)
    fid = file_id(page)
    ed.click()
    ed.press_sequentially("saved normally", delay=2)
    page.wait_for_timeout(1200)
    assert stored(page, fid)["draft"] == "start\nsaved normally"
    page.reload()
    page.evaluate("restore()")
    wait_status(page, "ready")
    assert "Recovered" not in status(page)
    assert journal(page, fid) is None
    assert editor(page).input_value() == "start\nsaved normally"


HIDE_THEN_SHOW = """
() => {
  const set = v => Object.defineProperty(document, 'hidden', { configurable: true, get: () => v });
  set(true); document.dispatchEvent(new Event('visibilitychange'));
  set(false); document.dispatchEvent(new Event('visibilitychange'));
}
"""


def test_journal_written_on_hide_is_removed_after_the_next_save(page):
    """Hide the tab with unsaved text (journal written), come back, keep typing, let it save, reopen.
    The journal must be gone, and no false 'closed window' warning may appear."""
    ed = open_2i_file(page)
    fid = file_id(page)
    ed.click()
    ed.press_sequentially("before hide", delay=2)
    _frame(page).evaluate(HIDE_THEN_SHOW)
    # Hiding also runs the normal flush, which (page alive) completes and removes the journal, so the journal's
    # existence cannot be asserted here; the browser-level put counter proves it was written.
    assert _frame(page).evaluate("window.__exitPuts") >= 1, "hiding the tab with unsaved text must write the exit journal"
    ed.press_sequentially(" and after", delay=2)
    page.wait_for_timeout(1200)
    assert stored(page, fid)["draft"] == "start\nbefore hide and after"
    assert journal(page, fid) is None, "a completed save must remove this session's exit journal"
    page.reload()
    page.evaluate("restore()")
    wait_status(page, "ready")
    assert page.frame_locator("#host iframe").get_by_role("alert").count() == 0
    assert editor(page).input_value() == "start\nbefore hide and after"


def test_closing_stale_window_never_overwrites_a_newer_save(page):
    """Another window saved first. This window's unsaved text must be kept aside, not written over it."""
    ed = open_2i_file(page)
    fid = file_id(page)
    # Simulate another window: a newer revision with different text, written directly to storage.
    _frame(page).evaluate(
        RAW_GET,
        ["pubcast-foresight-files-v1", "files", fid, {"fields": {"draft": "OTHER WINDOW SAVED THIS"}, "bump": 1}],
    )
    other = stored(page, fid)
    ed.click()
    ed.press_sequentially("stale window text", delay=2)
    # The debounced save must refuse (stale revision) and say so in 2i's own top bar, not only in the file pane.
    _frame(page).wait_for_function(
        "document.getElementById('saveIndicator').textContent.startsWith('Save failed')", timeout=5000
    )
    page.reload()
    page.evaluate("restore()")
    wait_status(page, "ready")
    rec = stored(page, fid)
    assert rec["draft"] == "OTHER WINDOW SAVED THIS" and rec["revision"] == other["revision"], f"newer save was overwritten: {rec!r}"
    kept = journal(page, fid)
    assert kept is not None and kept["draft"] == "start\nstale window text", f"unsaved edits not kept: {kept!r}"
    frame = page.frame_locator("#host iframe")
    assert "Nothing was overwritten" in frame.get_by_role("alert").inner_text()
    with page.expect_download() as download:
        frame.get_by_role("button", name="Download unsaved edits").click()
    assert open(download.value.path(), encoding="utf-8").read() == "start\nstale window text"


def test_reach_manuscript_edit_then_reload_with_host_unreachable_is_kept(page):
    """Ordinary (non-file) manuscript: type, then reload while the host refuses saves (network lost at close).
    Only the browser recovery copy can bring the text back.

    Without the refusal this test passed even with writeRecovery() disabled: the hide-time PUT reached the
    host through the test harness's request interception, which a real closing page may not achieve
    (reach.js does not use fetch keepalive). So the host boundary is failed on purpose."""
    page.goto("http://localhost/writers-room")
    text = page.locator("#soloTextarea")
    text.wait_for()
    page.wait_for_function("document.querySelector('#saveBtn').disabled===false")
    text.fill("Saved base")
    page.locator("#saveBtn").click()
    page.wait_for_function("document.querySelector('#saveIndicator').textContent.includes('Saved to Reach · revision 1')")
    refused = []

    def refuse_document_writes(route):
        if route.request.method == "PUT":
            refused.append(route.request.url)
            route.abort()
        else:
            route.fallback()

    page.route("**/api/writers-room/documents/**", refuse_document_writes)
    text.click()
    text.press("End")
    text.press_sequentially(" plus TAIL-TYPED-JUST-BEFORE-RELOAD", delay=2)
    page.reload()
    page.locator("#soloTextarea").wait_for()
    page.wait_for_function(
        "document.querySelector('#soloTextarea').value.includes('TAIL-TYPED-JUST-BEFORE-RELOAD')", timeout=15000
    )
    assert page.locator("#soloTextarea").input_value() == "Saved base plus TAIL-TYPED-JUST-BEFORE-RELOAD"
    assert refused, "the fault was not injected: no document save reached the refusal"
    # It must not claim the host has this text.
    assert "Saved to Reach · revision 2" not in page.locator("#saveIndicator").inner_text()


FILL_LOCAL_STORAGE = """() => { let n = 0;
  for (const size of [262144, 16384, 1024, 64, 8, 1]) { const v = 'x'.repeat(size); try { for (;;) localStorage.setItem('__fill' + (n++), v); } catch (e) {} }
  try { localStorage.setItem('__probe', 'y'); localStorage.removeItem('__probe'); return 'room left'; } catch (e) { return 'full'; } }"""


def test_reach_manuscript_with_host_down_and_browser_storage_full_is_never_silently_lost(page):
    """Host refuses saves and browser storage is full, so no copy exists anywhere. The writer must be told to
    export, and leaving must be guarded; staying keeps the text."""
    page.goto("http://localhost/writers-room")
    text = page.locator("#soloTextarea")
    text.wait_for()
    page.wait_for_function("document.querySelector('#saveBtn').disabled===false")
    text.fill("Saved base")
    page.locator("#saveBtn").click()
    page.wait_for_function("document.querySelector('#saveIndicator').textContent.includes('Saved to Reach · revision 1')")
    page.route("**/api/writers-room/documents/**", lambda r: r.abort() if r.request.method == "PUT" else r.fallback())
    assert page.evaluate(FILL_LOCAL_STORAGE) == "full", "fault not injected: browser storage still has room"
    text.click()
    text.press("End")
    text.press_sequentially(" plus QUOTA-TAIL", delay=2)
    page.wait_for_function(
        "document.querySelector('#saveIndicator').textContent.includes('Not saved')", timeout=10000
    )
    status = page.locator("#saveIndicator").inner_text()
    assert "Saved" not in status, f"claims a save: {status!r}"
    assert "export a copy" in status, f"writer is not told that no copy exists: {status!r}"
    assert page.evaluate("document.body.textContent.includes('the only copy of these changes')"), "no full explanation shown"
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.type), d.dismiss()))
    try:
        page.reload(timeout=4000)
    except Exception:  # a dismissed leave warning cancels the reload
        pass
    assert dialogs == ["beforeunload"], f"leaving was not guarded: {dialogs}"
    assert "QUOTA-TAIL" in text.input_value()


FAIL_FILES_PUT = """
(() => {
  const put = IDBObjectStore.prototype.put;
  IDBObjectStore.prototype.put = function (...args) {
    if (this.name === 'files' && localStorage.getItem('__failFilesPut')) throw new DOMException('Injected storage failure', 'QuotaExceededError');
    return put.apply(this, args);
  };
})();
"""


def test_recovery_write_failure_on_reopen_keeps_journal_and_record_and_says_so(page):
    """Reopen after a close with unsaved text, but the recovery write itself fails. The stored record must be
    unchanged, the journal kept, and the writer shown the kept-edits alert with a working download; it must not
    claim recovery or say close protection is unavailable."""
    page.context.add_init_script(FAIL_FILES_PUT)
    ed = open_2i_file(page)
    fid = file_id(page)
    before = stored(page, fid)
    ed.click()
    ed.press_sequentially("TEXT-WHOSE-RECOVERY-WRITE-FAILS", delay=2)
    page.reload()
    page.evaluate("localStorage.setItem('__failFilesPut', '1')")
    page.evaluate("restore()")
    frame = page.frame_locator("#host iframe")
    frame.get_by_role("alert").wait_for(timeout=15000)
    assert stored(page, fid) == before, "the stored record changed although the recovery write failed"
    kept = journal(page, fid)
    assert kept is not None and kept["draft"] == "start\nTEXT-WHOSE-RECOVERY-WRITE-FAILS"
    assert "Nothing was overwritten" in frame.get_by_role("alert").inner_text()
    assert "Recovered" not in status(page) and "cannot keep a recovery copy" not in status(page)
    with page.expect_download() as download:
        frame.get_by_role("button", name="Download unsaved edits").click()
    assert open(download.value.path(), encoding="utf-8").read() == "start\nTEXT-WHOSE-RECOVERY-WRITE-FAILS"
    page.evaluate("localStorage.removeItem('__failFilesPut')")
