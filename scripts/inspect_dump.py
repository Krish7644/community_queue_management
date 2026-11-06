import re
from pathlib import Path

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

# Find table creations
tables = re.findall(r"CREATE TABLE `(\w+)`", text)
print(f"Total tables found: {len(tables)}")
print("Tables:", tables)

# Find inserts
for t in tables:
    pattern = rf"INSERT INTO `{t}` VALUES (.*?);\n"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        print(f"Table `{t}` has {len(matches)} INSERT statement(s)")

