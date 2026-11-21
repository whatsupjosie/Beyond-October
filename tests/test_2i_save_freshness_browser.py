"""Real-browser regression: an in-flight workspace save cannot falsely cover later edits.

The independent oracle reads the actual host workspace file through its GET API,
not the 2i editor's IndexedDB state or save indicator. No mocked save response.
"""
import base64
from tests.test_2i_adversarial_saves import open_2i_file, _frame, page  # noqa: F401


def test_workspace_disk_save_reports_stale_revision_and_can_be_retried(page):
    editor = open_2i_file(page, "initial")
    frame = _frame(page)
    pane = frame.locator(".ff-workspace")

    # Establish a real disk target in the authenticated PubCast workspace.
    page.once("dialog", lambda dialog: dialog.accept("Scripts/save-race.txt"))
    pane.get_by_role("button", name="Save As…").click()
    frame.wait_for_function(
        "() => document.querySelector('.ff-workspace [role=status]').textContent.includes('Saved local file:')"
    )

    editor.fill("version one")
    page.wait_for_timeout(700)  # Allow the independent browser recovery autosave to settle.

    # Delay the real POST without replacing its implementation or response.
    frame.evaluate("""() => {
        const realFetch = window.fetch.bind(window);
        window.__heldWorkspaceWrite = null;
        window.fetch = (url, opts = {}) => {
            if (String(url).includes('/api/foresight/workspace/file') && opts.method === 'POST') {
                return new Promise((resolve, reject) => {
                    window.__heldWorkspaceWrite = {
                        release: () => realFetch(url, opts).then(resolve, reject)
                    };
                });
            }
            return realFetch(url, opts);
        };
    }""")

    pane.get_by_role("button", name="Save", exact=True).click()
    frame.wait_for_function("() => !!window.__heldWorkspaceWrite")
    editor.fill("version one plus late edits")
    frame.evaluate("() => window.__heldWorkspaceWrite.release()")
    frame.wait_for_function(
        "() => document.querySelector('.ff-workspace [role=status]').textContent.includes('Newer edits are not in that file')"
    )

    # Raw disk storage, read through a separate GET endpoint, must still contain
    # only the version submitted before the hold. No false Saved claim is allowed.
    def disk_text():
        result = frame.evaluate("""async () => {
            const r = await fetch('/api/foresight/workspace/file?path=Scripts%2Fsave-race.txt');
            if (!r.ok) throw new Error('workspace GET failed: ' + r.status);
            return (await r.json()).data;
        }""")
        return base64.b64decode(result).decode("utf-8")

    assert disk_text() == "version one"
    assert editor.input_value() == "version one plus late edits"

    # Restore normal fetch and retry the explicit Save. Both disk and UI must
    # now agree on the final revision.
    frame.evaluate("() => { window.__heldWorkspaceWrite = null; }")
    # The wrapper only holds POSTs; release the next one promptly.
    pane.get_by_role("button", name="Save", exact=True).click()
    frame.wait_for_function("() => !!window.__heldWorkspaceWrite")
    frame.evaluate("() => window.__heldWorkspaceWrite.release()")
    frame.wait_for_function(
        "() => document.querySelector('.ff-workspace [role=status]').textContent.includes('Saved local file:')"
    )
    assert disk_text() == "version one plus late edits"
