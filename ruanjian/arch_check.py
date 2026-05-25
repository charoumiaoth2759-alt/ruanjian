# arch_check.py
# 架构解耦自动验收工具（UI / commands / core / solver）

import os
import re
from pathlib import Path

ROOT = Path(".")

RULES = [
    # ❌ UI 不允许直接写 core / solver
    (r"ui/.*\.py", r"import\s+.*core", "UI 层禁止直接 import core"),
    (r"ui/.*\.py", r"import\s+.*solver", "UI 层禁止直接 import solver"),

    # ❌ solver 不允许碰 UI
    (r"solver/.*\.py", r"import\s+.*view", "Solver 禁止 import view"),
    (r"solver/.*\.py", r"Qt", "Solver 禁止依赖 Qt"),

    # ❌ core 纯净
    (r"core/.*\.py", r"Qt", "Core 层禁止 Qt"),
    (r"core/.*\.py", r"signal|emit", "Core 层禁止 Qt signal"),

    # ❌ commands 不能直接操作 UI
    (r"commands/.*\.py", r"import\s+.*view", "Commands 禁止 import view"),

    # ❌ UI 不能直接创建 Space（强规则）
    (r"ui/.*\.py", r"Space\(", "UI 层禁止直接创建 Space"),
    # ❌ UI 不能直接写 project.root_space（须经 CommandDispatcher）
    (r"ui/.*\.py", r'setattr\s*\(\s*[^,]+,\s*["\']root_space["\']', "UI 禁止 setattr(project, \"root_space\", ...)"),
    (r"ui/.*\.py", r"\.root_space\s*=", "UI 禁止对 .root_space 直接赋值"),
]

VIOLATIONS = []


def scan_file(path, pattern, msg):
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except:
        return

    if re.search(pattern, text):
        VIOLATIONS.append(f"[FAIL] {path} → {msg}")


def main():
    print("[arch_check] Architecture Check Start...\n")

    for file in ROOT.rglob("*.py"):
        rel = str(file.as_posix())

        for file_rule, pattern, msg in RULES:
            if re.match(file_rule, rel):
                scan_file(file, pattern, msg)

    if not VIOLATIONS:
        print("[arch_check] PASS: no violations")
        return

    print("[arch_check] FAIL: violations found\n")
    for v in VIOLATIONS:
        print(v)

    print("[arch_check] fix violations before continuing.\n")


if __name__ == "__main__":
    main()