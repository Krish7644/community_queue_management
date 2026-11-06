import re
from pathlib import Path

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

table_blocks = re.findall(r"CREATE TABLE `(\w+)` \((.*?)\) ENGINE=", text, re.DOTALL)
for tname, body in table_blocks:
    cols = []
    for line in body.strip().splitlines():
        line = line.strip()
        m = re.match(r"`(\w+)`\s+([^\s,]+)", line)
        if m:
            cols.append((m.group(1), m.group(2)))
    print(f"Table {tname}: {len(cols)} columns: {[c[0] for c in cols]}")

