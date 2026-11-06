import re
from pathlib import Path

dump_path = Path(r"C:\Users\littl\Downloads\community_scanner_dev.sql")
text = dump_path.read_text(encoding="utf-8", errors="ignore")

def parse_mysql_values(values_str):
    """
    Parse a string like '(1, \'abc\', NULL), (2, \'def\', 0)' into list of lists of Python values.
    """
    rows = []
    i = 0
    n = len(values_str)
    
    while i < n:
        # find start of row '('
        while i < n and values_str[i] != '(':
            i += 1
        if i >= n:
            break
        i += 1 # skip '('
        
        row = []
        current = []
        in_string = False
        escape = False
        
        while i < n:
            char = values_str[i]
            if in_string:
                if escape:
                    if char == 'n': current.append('\n')
                    elif char == 'r': current.append('\r')
                    elif char == 't': current.append('\t')
                    elif char == '\\': current.append('\\')
                    elif char == "'": current.append("'")
                    elif char == '"': current.append('"')
                    elif char == '0': current.append('\0')
                    else: current.append(char)
                    escape = False
                elif char == '\\':
                    escape = True
                elif char == "'":
                    # Check for '' escaped quote in SQL
                    if i + 1 < n and values_str[i+1] == "'":
                        current.append("'")
                        i += 1
                    else:
                        in_string = False
                else:
                    current.append(char)
            else:
                if char == "'":
                    in_string = True
                elif char == ',':
                    val = "".join(current).strip()
                    row.append(val)
                    current = []
                elif char == ')':
                    val = "".join(current).strip()
                    row.append(val)
                    current = []
                    i += 1
                    break
                else:
                    current.append(char)
            i += 1
            
        # Convert row values: NULL -> None, numbers -> int/float, strings -> str
        clean_row = []
        for v in row:
            if v == 'NULL':
                clean_row.append(None)
            else:
                clean_row.append(v)
        rows.append(clean_row)
        
    return rows

# Test on admins and gates
admin_m = re.search(r"INSERT INTO `admins` VALUES (.*?);\n", text, re.DOTALL)
if admin_m:
    rows = parse_mysql_values(admin_m.group(1))
    print(f"Parsed {len(rows)} admins:", rows)

gates_m = re.search(r"INSERT INTO `gates` VALUES (.*?);\n", text, re.DOTALL)
if gates_m:
    rows = parse_mysql_values(gates_m.group(1))
    print(f"Parsed {len(rows)} gates:", rows)

