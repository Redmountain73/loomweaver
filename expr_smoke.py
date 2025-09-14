from src.expr import parse_expr
import json
cases = ["1..5", "\"Hi, \" + name", "result * i"]
for c in cases:
    print("--", c)
    print(json.dumps(parse_expr(c), indent=2))
