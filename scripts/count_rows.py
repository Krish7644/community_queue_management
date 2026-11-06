import re
from pathlib import Path

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

from test_parser import parse_mysql_values

table_blocks = re.findall(r"CREATE TABLE `(\w+)` \((.*?)\) ENGINE=", text, re.DOTALL)
for tname, body in table_blocks:
    pattern = rf"INSERT INTO `{tname}` VALUES (.*?);\n"
    m = re.search(pattern, text, re.DOTALL)
    if m:
        rows = parse_mysql_values(m.group(1))
        print(f"Table {tname}: {len(rows)} rows")
    else:
        print(f"Table {tname}: 0 rows (empty)")

