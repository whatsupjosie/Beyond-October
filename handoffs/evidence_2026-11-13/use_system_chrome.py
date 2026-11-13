"""Sandbox-only pytest plugin: launch the installed Chrome for Testing because the
Playwright browser download is blocked here. Not part of the repository."""
from playwright.sync_api import BrowserType as _S
try:
    from playwright.async_api import BrowserType as _A
except Exception:  # pragma: no cover
    _A = None
CHROME = "/usr/bin/google-chrome"
def _wrap(cls):
    orig = cls.launch
    def launch(self, *a, **k):
        if self.name == "chromium" and "executable_path" not in k:
            k["executable_path"] = CHROME
        return orig(self, *a, **k)
    cls.launch = launch
_wrap(_S)
if _A is not None:
    _wrap(_A)
