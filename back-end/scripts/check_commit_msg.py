"""Check that a commit message follows AGENTS.md: `MB-0007 feat: short subject`.

Used by the pre-commit `commit-msg` hook (argument: path to the message file)
and by CI (`--stdin`, one subject per line).
"""

import re
import sys

PATTERN = re.compile(r"^MB-\d{4} (feat|fix|chore|docs|refactor|test): \S")
# Git writes these itself (merges, reverts, fixup commits); they are not typed by hand
IGNORED = ("Merge ", "Revert ", "fixup! ", "squash! ")


def is_valid(subject: str) -> bool:
    return subject.startswith(IGNORED) or bool(PATTERN.match(subject))


def main(argv: list[str]) -> int:
    if argv[1:] == ["--stdin"]:
        subjects = [line for line in sys.stdin.read().splitlines() if line.strip()]
    else:
        with open(argv[1], encoding="utf-8") as f:
            subjects = [f.readline().rstrip("\n")]

    bad = [s for s in subjects if not is_valid(s)]
    for subject in bad:
        print(f"Bad commit message: {subject!r}")
    if bad:
        print("Expected: MB-NNNN <feat|fix|chore|docs|refactor|test>: subject  (see AGENTS.md)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
