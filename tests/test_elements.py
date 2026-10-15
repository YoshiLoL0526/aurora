import pytest

from aurora import MIDNIGHT, Theme, box, button, column, row, text


def test_children_with_brackets_and_flattening():
    tree = column()[
        text("a"),
        [text("b"), [text("c")]],
        None,
        False,
        "d",  # los strings sueltos se convierten en text()
    ]
    assert [c.content for c in tree.children] == ["a", "b", "c", "d"]


def test_conditional_children():
    show = False
    tree = row()[text("siempre"), show and text("nunca")]
    assert len(tree.children) == 1


def test_style_aliases():
    el = text("x", size=20, weight=700, family="Inter")
    assert el.style == {"font_size": 20, "font_weight": 700, "font_family": "Inter"}


def test_none_props_are_dropped():
    assert box(bg=None, padding=8).style == {"padding": 8}


def test_to_spec_resolves_tokens_and_lambdas():
    counter = 41
    spec = box(bg="$primary", radius="$md", shadow=(0, 4, 12, "$shadow"))[text(lambda: counter + 1)].to_spec(
        MIDNIGHT
    )
    assert spec["style"]["bg"] == MIDNIGHT.colors["primary"]
    assert spec["style"]["radius"] == MIDNIGHT.radius["md"]
    assert spec["style"]["shadow"] == (0, 4, 12, MIDNIGHT.colors["shadow"])
    assert spec["children"][0]["text"] == "42"


def test_unknown_token_raises():
    with pytest.raises(KeyError, match="token"):
        box(bg="$nope").to_spec(Theme())


def test_button_keeps_callback_and_key():
    def cb():
        return None

    spec = button("OK", cb, key="ok").to_spec(MIDNIGHT)
    assert spec["on_click"] is cb
    assert spec["key"] == "ok"
    assert spec["children"][0]["text"] == "OK"
