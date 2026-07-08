# Deferred Items — Phase 01

| Found During | Item | Why Deferred |
|--------------|------|--------------|
| 01-03 Task 2 | `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` emitted by fastapi/testclient internals during pytest | Third-party dependency internals, not project code; suite is green. Revisit when bumping fastapi/starlette (swap test dep `httpx` -> `httpx2` if still advised). |
