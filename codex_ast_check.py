import ast, pathlib, sys
for raw in sys.argv[1:]:
    p=pathlib.Path(raw)
    try:
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        print("PY AST OK " + str(p))
    except Exception as exc:
        print("PY AST FAIL " + str(p) + ": " + type(exc).__name__ + ": " + str(exc))
