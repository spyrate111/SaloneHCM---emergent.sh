import re, os

MAP = {
    # greens -> Sierra Leone flag green ramp
    "0a1f17": "04270E", "0f2c24": "073A16", "0f281e": "063514", "133326": "0A4A1E",
    "143b30": "0B5222", "1a3a2a": "0C4F20", "1f4a38": "0F6428", "1f5a40": "117030",
    "215d46": "127530", "256449": "148231", "256048": "137D30", "1f6f55": "128A2C",
    "2d7a5d": "17A035",
    "e6f4ec": "E4F7E7", "e6f2ec": "E2F5E5", "c9e2d2": "BFEBC8", "c2e5d2": "B8E9C2",
    "d6ebe0": "CDF0D4", "d2eadd": "C9EED1", "9cc8b1": "90D8A0", "8fbca8": "83CF95",
    "eff6f2": "EDF8EE", "f4fbf5": "F2FBF3", "f2f8f5": "F0F9F1", "f1f8f4": "EFF9F0",
    "f0f5f2": "EEF7EF", "6e8a7c": "6B9E77",
    # reds/maroons -> Sierra Leone flag blue ramp
    "c02719": "0072C6", "9c1f14": "005A9C", "b83a3a": "3A7CB8", "8c2f2f": "2F6390",
    "9c2e2e": "34689A", "8e2727": "2C5E8E", "8b2418": "00568F", "7a2f26": "245683",
    "9a2a52": "2A5C9C",
    "fbeaea": "E9F2FB", "ffe9e5": "E5F1FD", "e9c2c2": "C2D9E9", "f2d0d0": "D0E2F2",
    "f4d5d5": "D5E5F4", "e8a29c": "9CC4E8", "e1a1a1": "A1C3E1", "f7e5ec": "E5EDF7",
}

pattern = re.compile("#(" + "|".join(MAP.keys()) + r")\b", re.IGNORECASE)
EXTS = {".js", ".jsx", ".css", ".html", ".json", ".py", ".svg"}
ROOTS = ["/app/frontend/src", "/app/frontend/public", "/app/backend", "/app/training_production"]
SKIP_DIRS = {"node_modules", ".git", "build", "__pycache__", ".pytest_cache", "output"}

changed = 0
for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1] not in EXTS:
                continue
            p = os.path.join(dirpath, fn)
            try:
                s = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError):
                continue
            new, n = pattern.subn(lambda m: "#" + MAP[m.group(1).lower()], s)
            if n:
                open(p, "w", encoding="utf-8").write(new)
                changed += 1
                print(f"{n:4d}  {p}")
print("files changed:", changed)
