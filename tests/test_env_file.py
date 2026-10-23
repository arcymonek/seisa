"""Editing the API keys in the .env file (backend/env_file.py). Expected values come from what python-dotenv, the reader
pydantic-settings uses, returns for the written file - not from the writer's own code."""
from __future__ import annotations

import json
import os
import stat

import pytest
from dotenv import dotenv_values

import backend.config as cfg
from backend import env_file
from backend.config import Settings, settings
from backend.env_file import EnvFileError


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A private .env path, no key in the process environment, every setting at its default (the developer's own .env,
    which `settings` read at import, must not decide what a test sees) and every setting restored after the test."""
    monkeypatch.setattr(cfg, "ENV_FILE", tmp_path / ".env")
    for field, info in Settings.model_fields.items():
        monkeypatch.delenv(field.upper(), raising=False)
        monkeypatch.setattr(settings, field, info.default)
    return tmp_path / ".env"


def values(path):
    return dict(dotenv_values(path))


def test_editable_fields_are_the_fields_of_settings():
    assert tuple(Settings.model_fields) == env_file.EDITABLE
    assert set(env_file.SECRET_FIELDS) == {f for f in Settings.model_fields if f.endswith("_api_key")}
    assert "openrouter_model" not in env_file.SECRET_FIELDS


def test_set_a_key_creates_a_private_file_and_updates_the_running_settings(env):
    env_file.write({"otx_api_key": "abc123"})
    assert values(env)["OTX_API_KEY"] == "abc123"
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert settings.otx_api_key == "abc123"


def test_a_new_file_starts_from_env_example(env):
    env.with_name(".env.example").write_text("# comment\nOTX_API_KEY=\nGREYNOISE_API_KEY=\n")
    env_file.write({"otx_api_key": "k1"})
    text = env.read_text()
    assert text.startswith("# comment\nOTX_API_KEY=k1\n")
    assert values(env) == {"OTX_API_KEY": "k1", "GREYNOISE_API_KEY": ""}


def test_overwrite_keeps_comments_and_unknown_lines(env):
    env.write_text("# my notes\nOTX_API_KEY=old\nSOMETHING_ELSE=keep me\n")
    env_file.write({"otx_api_key": "new"})
    assert env.read_text() == "# my notes\nOTX_API_KEY=new\nSOMETHING_ELSE=keep me\n"


def test_duplicates_and_export_lines_become_one_line(env):
    env.write_text("export OTX_API_KEY=a\nX=1\nOTX_API_KEY=b\n  OTX_API_KEY = c\n")
    env_file.write({"otx_api_key": "d"})
    assert env.read_text() == "OTX_API_KEY=d\nX=1\n"
    assert values(env)["OTX_API_KEY"] == "d"


def test_a_key_that_only_starts_with_the_same_letters_is_not_touched(env):
    env.write_text("OTX_API_KEY_OLD=keep\n")
    env_file.write({"otx_api_key": "k"})
    assert values(env) == {"OTX_API_KEY_OLD": "keep", "OTX_API_KEY": "k"}


def test_crlf_file_and_missing_final_newline(env):
    env.write_bytes(b"A=1\r\nOTX_API_KEY=x\r\nB=2")
    env_file.write({"otx_api_key": "y"})
    assert env.read_bytes() == b"A=1\nOTX_API_KEY=y\nB=2\n"


def test_remove_leaves_an_empty_line_and_resets_the_setting(env):
    env.write_text("OTX_API_KEY=abc\nOTHER=1\n")
    env_file.write({"otx_api_key": "abc"})
    env_file.write({"otx_api_key": None})
    assert env.read_text() == "OTX_API_KEY=\nOTHER=1\n"
    assert settings.otx_api_key == ""


def test_removing_the_model_restores_the_default(env):
    env_file.write({"openrouter_model": "vendor/model:free"})
    assert settings.openrouter_model == "vendor/model:free"
    env_file.write({"openrouter_model": None})
    assert settings.openrouter_model == Settings.model_fields["openrouter_model"].default


@pytest.mark.parametrize("bad", ["a\nB=1", "a b", " a", "a${HOME}", "a#b", 'a"b', "a'b", "a\\b", "", "x" * 513, "żółć"])
def test_values_that_could_change_the_file_are_refused_without_echoing_them(env, bad):
    with pytest.raises(EnvFileError) as err:
        env_file.write({"otx_api_key": bad})
    assert bad not in err.value.message or bad == ""
    assert not env.exists()


def test_real_looking_values_pass(env):
    value = "sk-or-v1-AbC123_xyz.~+/=:-"
    env_file.write({"openrouter_api_key": value})
    assert values(env)["OPENROUTER_API_KEY"] == value


def test_unknown_field_is_refused(env):
    with pytest.raises(EnvFileError):
        env_file.write({"not_a_setting": "abc"})
    assert not env.exists()


def test_a_field_set_by_the_environment_is_refused(env, monkeypatch):
    monkeypatch.setenv("OTX_API_KEY", "from-shell")
    with pytest.raises(EnvFileError) as err:
        env_file.write({"otx_api_key": "abc"})
    assert "OTX_API_KEY" in err.value.message
    assert not env.exists()


def test_one_bad_change_changes_nothing(env):
    env.write_text("OTX_API_KEY=old\n")
    with pytest.raises(EnvFileError):
        env_file.write({"otx_api_key": "new", "greynoise_api_key": "bad value"})
    assert env.read_text() == "OTX_API_KEY=old\n"


def test_a_symbolic_link_is_not_replaced(env, tmp_path):
    target = tmp_path / "elsewhere"
    target.write_text("OTX_API_KEY=old\n")
    env.symlink_to(target)
    with pytest.raises(EnvFileError):
        env_file.write({"otx_api_key": "new"})
    assert env.is_symlink()
    assert target.read_text() == "OTX_API_KEY=old\n"


def test_no_temporary_file_is_left_behind(env):
    env_file.write({"otx_api_key": "a"})
    assert [p.name for p in env.parent.iterdir()] == [".env"]


def test_status_never_contains_a_secret_value(env, monkeypatch):
    env_file.write({"otx_api_key": "TOPSECRET123", "openrouter_model": "vendor/model"})
    rows = {r["field"]: r for r in env_file.keys_status()}
    assert "TOPSECRET123" not in json.dumps(rows)
    assert rows["otx_api_key"]["set"] is True and rows["otx_api_key"]["secret"] is True
    assert rows["greynoise_api_key"]["set"] is False
    assert rows["openrouter_model"]["value"] == "vendor/model"
    assert "value" not in rows["otx_api_key"]
    monkeypatch.setenv("GREYNOISE_API_KEY", "x")
    assert {r["field"]: r for r in env_file.keys_status()}["greynoise_api_key"]["from_env"] is True


def test_changing_a_key_forgets_the_stored_quota_of_that_service(env):
    from backend.storage import load_api_usage, save_api_usage

    save_api_usage({"live": {"otx": {"rows": [1]}, "urlscan": {"rows": [2]}}, "headers": {"x": 1}})
    env_file.write({"otx_api_key": "k"})
    usage = load_api_usage()
    assert "otx" not in usage["live"] and "urlscan" in usage["live"] and usage["headers"] == {"x": 1}


def test_the_test_run_does_not_point_at_the_real_env_file(env):
    assert cfg.ENV_FILE != cfg.BASE_DIR / ".env"
    assert os.fspath(cfg.ENV_FILE).startswith(os.fspath(env.parent))


def test_an_empty_change_does_not_touch_the_file(env):
    env_file.write({})
    assert not env.exists()
