import re

with open("agents/config.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == ")":
        continue
        continue
    new_lines.append(line)

with open("agents/config.py", "w") as f:
    f.writelines(new_lines)
