from pathlib import Path


def source(name: str) -> str:
    return Path('static', name).read_text(encoding='utf-8')


def test_dropdown_menus_and_commands_are_wired():
    html = source('pubpartner.html')
    js = source('pubpartner.js')
    assert html.count('class="menu-root"') == 8
    for command in (
        'focus-files', 'focus-preview', 'focus-memory', 'focus-setup',
        'save-workspace', 'import-layout', 'export-layout', 'undo-layout',
        'compact-layout', 'verify-receipts', 'restore-source', 'provider-test',
        'preflight',
    ):
        assert f'data-command="{command}"' in html
        assert f"registerCommand('{command}'" in js or f"registerCommand(`focus-${{name}}`" in js
    assert "registerCommand('focus-memory',focus('wardrobe'))" in js
    assert "const CommandRegistry = new Map()" in js


def test_workspace_state_is_pubpartner_namespaced_and_versioned():
    js = source('pubpartner.js')
    assert "const storeKey = 'pubpartner.workspace.v1'" in js
    assert "const workspaceSchema = 'pubpartner.workspace.layout.v1'" in js
    assert 'iteration-wallet-' not in js
    assert 'iw.theme' not in js
    assert 'passkey' not in js.lower()
    assert 'labcopy' not in js.lower()
    assert 'promotion' not in js.lower()


def test_layout_import_rejects_wrong_schema_and_recovers_corruption():
    js = source('pubpartner.js')
    assert "value.schema !== workspaceSchema" in js
    assert "Unsupported PubPartner layout file." in js
    assert "Corrupt layout ignored" in js
    assert "localStorage.removeItem(storeKey)" in js


def test_accessibility_and_responsive_contracts_exist():
    html = source('pubpartner.html')
    css = source('pubpartner.css')
    js = source('pubpartner.js')
    assert 'aria-haspopup="menu"' in html
    assert 'aria-expanded="false"' in html
    assert "['ArrowLeft','ArrowRight','ArrowUp','ArrowDown']" in js
    assert "e.key.toLowerCase()==='s'" in js
    assert 'html[data-motion="reduced"]' in css
    assert '@media(max-width:760px)' in css
