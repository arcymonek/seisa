"""backend/themes.py and the shipped themes in frontend/themes/.

Expected contrast values follow the WCAG 2.x definition (relative luminance, ratio (L1+0.05)/(L2+0.05)); the
thresholds are the AA limits from the standard, not numbers taken from the code.
"""
from __future__ import annotations

import json
import re
import struct

import pytest

from backend import themes as themes_mod
from backend.config import FRONTEND_DIR
from backend.themes import COLOR_KEYS, ThemeError, load_themes, public_list, render_css, validate_theme


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def good_theme(**over) -> dict:
    data = {
        "id": "demo", "name": {"en": "Demo", "pl": "Demo"}, "base": "light", "order": 50,
        "colors": dict.fromkeys(COLOR_KEYS, "#123456"),
    }
    data.update(over)
    return data


SHIPPED = {th["id"]: th for th in load_themes()}

# (foreground, background) pairs that carry text; every one needs 4.5:1 (WCAG AA, normal text)
TEXT_PAIRS = (
    [(fg, bg) for fg in ("text", "muted", "accent", "fail", "pass", "warn") for bg in ("bg", "bg-raised", "bg-inset")]
    + [("fail", "fail-bg"), ("pass", "pass-bg"), ("warn", "warn-bg"), ("on-accent", "accent"), ("on-warn", "warn"),
       ("text-strong", "hit-bg"), ("text", "tooltip-bg")]
)
# A shipped theme that cannot reach AA for some pair must be listed here with its reason; there are none today.
KNOWN_BELOW_AA: dict[str, set[tuple[str, str]]] = {}


def test_shipped_themes_are_light_dark_and_kohaku():
    assert set(SHIPPED) == {"light", "dark", "kohaku"}
    assert SHIPPED["light"]["base"] == "light" and SHIPPED["dark"]["base"] == "dark" and SHIPPED["kohaku"]["base"] == "light"
    assert [th["id"] for th in load_themes()] == ["light", "dark", "kohaku"]  # button order: light, dark, kohaku (System is added last)


@pytest.mark.parametrize("theme_id", ["light", "dark", "kohaku"])
def test_shipped_theme_contrast(theme_id):
    colors = SHIPPED[theme_id]["colors"]
    for fg, bg in TEXT_PAIRS:
        ratio = contrast(colors[fg], colors[bg])
        if (fg, bg) in KNOWN_BELOW_AA.get(theme_id, set()):
            assert ratio >= 3.5, (fg, bg, ratio)
        else:
            assert ratio >= 4.5, (theme_id, fg, bg, round(ratio, 2))


def test_light_theme_is_not_pure_white_or_black():
    colors = SHIPPED["light"]["colors"]
    assert "#ffffff" not in colors.values() and "#000000" not in colors.values()


def test_kohaku_has_a_red_and_white_stripe_and_the_others_have_none():
    assert SHIPPED["kohaku"]["stripe"] == {"top": "#e9e6e3", "bottom": SHIPPED["kohaku"]["colors"]["accent"]}
    assert "stripe" not in SHIPPED["light"] and "stripe" not in SHIPPED["dark"]


def test_status_red_is_darker_than_the_accent_red_in_kohaku():
    # both are red there; the error colour must stay visibly different from the accent (links, buttons, active tab)
    colors = SHIPPED["kohaku"]["colors"]
    assert _lum(colors["fail"]) < _lum(colors["accent"]) * 0.6, (colors["fail"], colors["accent"])


@pytest.mark.parametrize("theme_id", ["light", "dark", "kohaku"])
def test_info_banner_colour_is_not_the_error_colour(theme_id):
    colors = SHIPPED[theme_id]["colors"]
    assert colors["info"] != colors["fail"]
    css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.banner\.info\s*\{\s*border-color:\s*var\(--info\)", css)  # not var(--accent): that is red in kohaku


def test_info_colour_is_not_the_accent_where_the_accent_is_red():
    colors = SHIPPED["kohaku"]["colors"]
    assert colors["info"] not in (colors["accent"], colors["fail"])
    # the other two themes keep their blue accent for information, so their look did not change
    assert SHIPPED["light"]["colors"]["info"] == SHIPPED["light"]["colors"]["accent"]
    assert SHIPPED["dark"]["colors"]["info"] == SHIPPED["dark"]["colors"]["accent"]


def test_logo_of_light_themes_is_a_mask_painted_in_the_accent_colour():
    css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")
    block = re.search(r'h1 \.logo-img\[data-logo="light"\]\s*\{(.*?)\}', css, re.S).group(1)
    assert "background-color: var(--accent)" in block and "/logo-mask.png" in block
    mask = (FRONTEND_DIR / "logo-mask.png").read_bytes()
    assert mask[:8] == b"\x89PNG\r\n\x1a\n"
    width, height, depth, ctype = struct.unpack(">IIBB", mask[16:26])
    assert (width, height, depth, ctype) == (512, 512, 8, 4)  # grey + alpha: only the alpha channel shapes the logo
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert 'data-logo="light"' in html and "logo-light.png" not in html


def test_no_colour_literals_left_in_the_stylesheet():
    css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", css)
    assert literals == ["#fff"]  # the only one: screenshot canvas behind a transparent page capture (.us-shot img)


def test_every_variable_used_in_the_stylesheet_is_defined_by_themes_or_the_root():
    css = (FRONTEND_DIR / "css" / "style.css").read_text(encoding="utf-8")
    used = set(re.findall(r"var\(--([a-z-]+)\)", css))
    assert used <= set(COLOR_KEYS) | {"sans", "mono"}, used - set(COLOR_KEYS)


def test_valid_theme_round_trips_and_lowercases():
    data = good_theme(colors=dict.fromkeys(COLOR_KEYS, "#ABCDEF"))
    out = validate_theme(data, "demo")
    assert out["colors"]["bg"] == "#abcdef" and out["name"]["pl"] == "Demo"


def test_missing_language_falls_back_to_the_other_one():
    out = validate_theme(good_theme(name={"en": "Only English"}), "demo")
    assert out["name"] == {"en": "Only English", "pl": "Only English"}


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(id="Demo"),
    lambda d: d.update(id="other"),                       # differs from the file name "demo"
    lambda d: d.update(id="../x"),
    lambda d: d.update(base="sepia"),
    lambda d: d.update(order=-1),
    lambda d: d.update(order=True),
    lambda d: d.update(order="5"),
    lambda d: d.update(name={}),
    lambda d: d.update(name={"de": "Dunkel"}),
    lambda d: d.update(name={"en": "<b>x</b>"}),
    lambda d: d.update(name={"en": "x" * 41}),
    lambda d: d.update(extra=1),
    lambda d: d["colors"].pop("bg"),
    lambda d: d["colors"].update(sneaky="#123456"),
    lambda d: d["colors"].update(bg="#fff"),
    lambda d: d["colors"].update(bg="red"),
    lambda d: d["colors"].update(bg="#123456;}body{display:none"),
    lambda d: d["colors"].update(bg="url(https://attacker.example/x)"),
    lambda d: d["colors"].update(bg="#12345678"),
    lambda d: d["colors"].update(bg=123456),
    lambda d: d.update(colors=[]),
    lambda d: d.update(stripe="#ff0000"),                                          # must be an object
    lambda d: d.update(stripe={"top": "#ffffff"}),                                 # bottom missing
    lambda d: d.update(stripe={"top": "#ffffff", "bottom": "#ff0000", "mid": "#000000"}),
    lambda d: d.update(stripe={"top": "#fff", "bottom": "#ff0000"}),
    lambda d: d.update(stripe={"top": "red", "bottom": "#ff0000"}),
    lambda d: d.update(stripe={"top": "url(https://attacker.example/x)", "bottom": "#ff0000"}),
    lambda d: d.update(stripe={"top": "#ffffff;}body{display:none", "bottom": "#ff0000"}),
    lambda d: d.update(stripe={"top": 16777215, "bottom": "#ff0000"}),
])
def test_invalid_theme_is_rejected(mutate):
    data = good_theme()
    mutate(data)
    with pytest.raises(ThemeError):
        validate_theme(data, "demo")


def test_non_object_is_rejected():
    for bad in ([], "x", 3, None):
        with pytest.raises(ThemeError):
            validate_theme(bad, "demo")


def test_rendered_css_only_holds_whitelisted_pieces():
    css = render_css([validate_theme(good_theme(), "demo")])
    pattern = r'(:root\[data-theme="[a-z0-9-]+"\]\{color-scheme:(?:dark|light);--logo-dark-display:(?:inline|none);--logo-light-display:(?:inline|none);(?:--[a-z-]+:#[0-9a-f]{6};)+\}\n)+'
    assert re.fullmatch(pattern, css)
    assert css.count("--") == len(COLOR_KEYS) + 2  # + the two logo switches


def test_stripe_is_optional_lowercased_and_rendered_as_two_variables():
    plain = render_css([validate_theme(good_theme(), "demo")])
    assert "stripe" not in plain and "stripe" not in validate_theme(good_theme(), "demo")
    out = validate_theme(good_theme(stripe={"top": "#ABCDEF", "bottom": "#123456"}), "demo")
    assert out["stripe"] == {"top": "#abcdef", "bottom": "#123456"}
    css = render_css([out])
    assert "--stripe-top:#abcdef;--stripe-bottom:#123456;" in css
    assert css.count("--") == len(COLOR_KEYS) + 2 + 2  # colours + two logo switches + two stripe colours
    pattern = r'(:root\[data-theme="[a-z0-9-]+"\]\{color-scheme:(?:dark|light);--logo-dark-display:(?:inline|none);--logo-light-display:(?:inline|none);(?:--[a-z-]+:#[0-9a-f]{6};)+\}\n)+'
    assert re.fullmatch(pattern, css)  # still only whitelisted hex variables, so the strict pattern needs no change


def test_public_list_has_no_colours():
    listed = public_list([validate_theme(good_theme(), "demo")])
    assert listed == [{"id": "demo", "name": {"en": "Demo", "pl": "Demo"}, "base": "light", "order": 50}]


def test_loader_skips_bad_files_and_sorts(tmp_path, monkeypatch):
    monkeypatch.setattr(themes_mod, "THEMES_DIR", tmp_path)
    (tmp_path / "b.json").write_text(json.dumps(good_theme(id="b", order=30)))
    (tmp_path / "a.json").write_text(json.dumps(good_theme(id="a", order=30)))
    (tmp_path / "first.json").write_text(json.dumps(good_theme(id="first", order=1)))
    (tmp_path / "broken.json").write_text("{not json")
    (tmp_path / "wrongid.json").write_text(json.dumps(good_theme(id="zzz")))
    (tmp_path / "huge.json").write_text(" " * (themes_mod.MAX_FILE_BYTES + 1))
    (tmp_path / "notes.txt").write_text("ignored")
    assert [th["id"] for th in load_themes()] == ["first", "a", "b"]


def test_loader_ignores_symlinks(tmp_path, monkeypatch):
    target = tmp_path / "real.json"
    target.write_text(json.dumps(good_theme(id="real")))
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "real.json").symlink_to(target)
    monkeypatch.setattr(themes_mod, "THEMES_DIR", themes_dir)
    assert load_themes() == []


def test_missing_directory_gives_no_themes(tmp_path, monkeypatch):
    monkeypatch.setattr(themes_mod, "THEMES_DIR", tmp_path / "nope")
    assert load_themes() == []
