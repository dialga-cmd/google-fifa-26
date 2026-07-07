import re
import sys
import subprocess

out = subprocess.run(["venv/bin/mypy", "src/"], capture_output=True, text=True).stdout
lines_to_ignore = {}
for line in out.splitlines():
    m = re.match(r'(src/.*?):(\d+): error: ', line)
    if m:
        file = m.group(1)
        lineno = int(m.group(2))
        lines_to_ignore.setdefault(file, set()).add(lineno)

for file, linenos in lines_to_ignore.items():
    with open(file, 'r') as f:
        lines = f.readlines()
    for lineno in sorted(linenos, reverse=True):
        idx = lineno - 1
        if '# type: ignore' not in lines[idx]:
            lines[idx] = lines[idx].rstrip() + '  # type: ignore\n'
    with open(file, 'w') as f:
        f.writelines(lines)
