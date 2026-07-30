from story.routes_version import (
    _decode_version_description,
    _decode_version_show_full_directory,
    _encode_version_description,
)


def test_legacy_version_defaults_to_full_directory() -> None:
    description = "[[format:script]]\n旧版本说明"

    assert _decode_version_description(description) == ("旧版本说明", "script")
    assert _decode_version_show_full_directory(description) is True


def test_progressive_directory_metadata_round_trips_without_leaking_into_description() -> None:
    encoded = _encode_version_description("发布说明", "novel", False)

    assert encoded.startswith("[[format:novel]]\n[[directory:progressive]]\n")
    assert _decode_version_description(encoded) == ("发布说明", "novel")
    assert _decode_version_show_full_directory(encoded) is False


def test_reencoding_replaces_existing_directory_marker() -> None:
    original = _encode_version_description("说明", "script", False)
    updated = _encode_version_description(original, "script", True)

    assert updated.count("[[directory:") == 1
    assert _decode_version_description(updated) == ("说明", "script")
    assert _decode_version_show_full_directory(updated) is True
