from __future__ import annotations

import pytest

from apparatus_core.skills import (
    BUILTIN_SKILLS, canonical_path, has_skill_index, is_legacy_pointer,
    legacy_pointer, SKILL_INDEX, valid_name, validate_skill,
)


def document(header="name: apparatus-welcome\ndescription: Start a work area.", body="Read the selected files."):
    return f"---\n{header}\n---\n\n{body}\n"


@pytest.mark.parametrize("crlf", [False, True])
def test_common_portable_metadata_and_single_readable_body(crlf):
    text = document("name: apparatus-welcome\ndescription: Start a work area.\n"
                    "license: MIT\ncompatibility: Requires file reading.\n"
                    "metadata: {author: Example, version: '1'}\nallowed-tools: Read")
    if crlf:
        text = text.replace("\n", "\r\n")
    assert validate_skill(text.encode(), "apparatus-welcome") == []


@pytest.mark.parametrize("text", [
    b"\xff", "Plain instructions", "---\nname: apparatus-welcome\n",
    "---\n- not a mapping\n---\nBody", document(body=""),
    document("name: apparatus-welcome\nname: apparatus-welcome\ndescription: Start."),
    document("name: apparatus-welcome\ndescription: Start.\nmetadata: {version: '1', version: '2'}"),
    document("name: apparatus-welcome\ndescription: Start.\nmetadata: &loop {cycle: *loop}"),
    document("name: apparatus-welcome\ndescription: Start.\nmetadata: {version: 1}"),
    document("name: apparatus-welcome\ndescription: Start.\nallowed-tools: [Read]"),
    document("name: apparatus-welcome\ndescription: Start.\ncompatibility: " + "x" * 501),
    document("name: apparatus-welcome\ndescription: " + "x" * 1025),
    document("name: apparatus-welcome\ndescription: ''"),
    document("name: other-name\ndescription: Start."),
    document("name: apparatus-welcome\ndescription: Start.\npermission: all"),
    document("name: apparatus-welcome\ndescription: Start.\ntrue: value"),
])
def test_malformed_or_nonportable_documents_are_rejected(text):
    assert validate_skill(text, "apparatus-welcome")


@pytest.mark.parametrize("name", ["", "A", "-start", "end-", "two--parts", "a/b", "naïve", "x" * 65])
def test_invalid_directory_names_cannot_construct_canonical_paths(name):
    assert not valid_name(name)
    with pytest.raises(ValueError):
        canonical_path(name)


def test_legacy_pointer_recognition_requires_complete_exact_bytes():
    for old, name in BUILTIN_SKILLS.items():
        pointer = legacy_pointer(old)
        assert canonical_path(name).encode() in pointer
        assert is_legacy_pointer(old, pointer)
        assert is_legacy_pointer(old, pointer.replace(b"\n", b"\r\n"))
        assert not is_legacy_pointer(old, pointer + b"Custom additions\n")
    assert not has_skill_index(b"<!-- Apparatus Skill index: v1 -->\nCustom body")
    assert has_skill_index(b"Custom canon\n" + SKILL_INDEX.encode())
