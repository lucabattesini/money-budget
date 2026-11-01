"""The commit-message rule from AGENTS.md (`MB-NNNN type: subject`)."""

import pytest

from scripts.check_commit_msg import is_valid, main


@pytest.mark.parametrize(
    "subject",
    [
        "MB-0007 feat: add whatsapp category filter",
        "MB-0006 chore: add ruff",
        "MB-0001 test: x",
        "Merge pull request #35 from lucabattesini/MB-0005-x",
        'Revert "MB-0005 fix: something"',
    ],
)
def test_accepts_valid_messages(subject):
    assert is_valid(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "add whatsapp filter",
        "fix: missing code",
        "MB-7 feat: code is not zero padded",
        "MB-0007: no type",
        "MB-0007 feature: unknown type",
        "MB-0007 feat:no space",
        "MB-0007 feat: ",
        "mb-0007 feat: lowercase code",
    ],
)
def test_rejects_invalid_messages(subject):
    assert not is_valid(subject)


def test_only_the_subject_line_of_a_message_file_is_checked(tmp_path):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("MB-0007 fix: ok\n\nbody without a code is fine\n")

    assert main(["check_commit_msg.py", str(message)]) == 0


def test_a_bad_message_file_fails_and_explains(tmp_path, capsys):
    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("did some stuff\n")

    assert main(["check_commit_msg.py", str(message)]) == 1
    assert "did some stuff" in capsys.readouterr().out
