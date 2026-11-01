"""`rich_text` (tramos con estilo dentro de un párrafo) y `markdown`."""

import pytest

from aurora import DAYLIGHT, App, Signal, button, column, markdown, rich_text, span, text


def _pilot(view, size=(420, 300)):
    return App(view, size=size).pilot()


def test_spans_join_into_one_paragraph_and_inherit_the_paragraph_style():
    el = rich_text("Pulsa ", span("Guardar", weight=700), [".", None, ""], size=15, key="r")
    spec = el.to_spec(DAYLIGHT)
    assert spec["text"] == "Pulsa Guardar."
    assert [s[0] for s in spec["style"]["spans"]] == [6, 7, 1]
    assert spec["style"]["spans"][1][4] is None  # sin tamaño propio: hereda los 15 del párrafo


def test_span_styles_resolve_theme_tokens():
    spec = rich_text(span("x", color="$danger", code=True)).to_spec(DAYLIGHT)
    color, bg = spec["style"]["spans"][0][1:3]
    assert color == DAYLIGHT.resolve("$danger") and bg == DAYLIGHT.resolve("$surface_hover")


def test_rich_text_wraps_like_plain_text():
    words = "una frase bastante larga que no cabe en una sola línea " * 3
    view = lambda: column()[
        column(width=200)[
            text(words, key="plain"),
            rich_text(words[:20], span(words[20:60], weight=700), words[60:], key="rich"),
        ]
    ]
    pilot = _pilot(view)
    _, _, w, h = pilot.rect("rich")
    assert w <= 200
    assert h >= pilot.rect("plain")[3] * 0.8  # varias líneas, no una sola desbordada


def test_link_spans_receive_clicks_and_are_announced_as_links():
    clicks: list[str] = []
    view = lambda: column(padding=10)[
        rich_text(
            "Lee ",
            span("la guía", on_click=lambda: clicks.append("guía")),
            " o ",
            span("el código", on_click=lambda: clicks.append("código"), color="$text"),
            key="r",
        )
    ]
    pilot = _pilot(view)
    pilot.click("r#link-1-0")
    pilot.click("r#link-0-0")
    assert clicks == ["código", "guía"]
    links = [n for n in pilot.a11y_tree() if n["role"] == "link"]
    assert [n["label"] for n in links] == ["la guía", "el código"]
    pilot.a11y_action(links[0]["key"], "click")
    assert clicks[-1] == "guía"


def test_link_that_wraps_is_clickable_on_both_lines():
    clicks = Signal(0)
    bump = lambda: clicks.set(clicks() + 1)
    view = lambda: column()[
        column(width=120)[
            rich_text("Texto previo ", span("enlace muy largo que se parte", on_click=bump), key="r")
        ]
    ]
    pilot = _pilot(view)
    pilot.click("r#link-0-0")
    pilot.click("r#link-0-1")
    assert clicks() == 2


def test_links_join_the_tab_order_and_activate_with_enter():
    clicks: list[str] = []
    view = lambda: column(padding=10, gap=8)[
        button("Antes", lambda: clicks.append("antes"), key="b"),
        rich_text(
            "Lee ",
            span("la guía", on_click=lambda: clicks.append("guía")),
            " o ",
            span("el código", on_click=lambda: clicks.append("código")),
            key="r",
        ),
    ]
    pilot = _pilot(view)
    pilot.press("tab")
    assert pilot.focused == "b"
    pilot.press("tab")
    assert pilot.focused == "r#link-0-0"
    pilot.press("enter")
    assert clicks == ["guía"]
    # Tras la reconstrucción que provoca el clic, el foco sigue en el enlace.
    assert pilot.focused == "r#link-0-0"
    pilot.press("tab")
    assert pilot.focused == "r#link-1-0"
    pilot.press("enter")
    pilot.press("space")  # Espacio no activa un enlace (como en la web)
    assert clicks == ["guía", "código"]
    pilot.press("shift+tab")
    assert pilot.focused == "r#link-0-0"
    focused = [n for n in pilot.a11y_tree() if n["focused"]]
    assert [(n["role"], n["label"]) for n in focused] == [("link", "la guía")]
    assert "focus" in focused[0]["actions"]


def test_wrapped_link_is_one_tab_stop_and_its_bounds_cover_every_line():
    view = lambda: column()[
        column(width=120)[
            rich_text("Texto previo ", span("enlace muy largo que se parte", on_click=lambda: None), key="r")
        ]
    ]
    pilot = _pilot(view)
    pilot.press("tab")
    assert pilot.focused == "r#link-0-0"
    pilot.press("tab")  # el único enlace: el foco da la vuelta a él mismo
    assert pilot.focused == "r#link-0-0"
    # Al pulsar su segunda línea, el foco va al enlace entero.
    pilot.click("r#link-0-1")
    assert pilot.focused == "r#link-0-0"
    (link,) = [n for n in pilot.a11y_tree() if n["role"] == "link"]
    _, top, _, bottom = link["bounds"]
    _, y1, _, h1 = pilot.rect("r#link-0-1")
    assert top <= pilot.rect("r#link-0-0")[1] and bottom >= y1 + h1


def test_rich_text_without_links_has_no_link_handler():
    spec = rich_text("hola ", span("mundo", italic=True)).to_spec(DAYLIGHT)
    assert "link" not in spec["handlers"]


MD = r"""# Título

Párrafo con **negrita**, *cursiva*, `código` y [un enlace](https://example.com).
Sigue en la misma línea.

- uno
- dos
  1. dos.uno
- tres

> cita

```
bloque
  sangrado
```

---

Escape \*literal\* y [otro](local).
"""


def test_markdown_builds_headings_lists_and_code_blocks():
    pilot = _pilot(lambda: column()[markdown(MD, key="md")], size=(500, 700))
    tree = pilot.a11y_tree()
    headings = [n for n in tree if n["role"] == "heading"]
    assert [n["level"] for n in headings] == [1]
    assert sum(n["role"] == "listitem" for n in tree) == 4
    assert sum(n["role"] == "list" for n in tree) == 2
    names = [n.get("label") for n in tree if n["role"] == "link"]
    assert names == ["un enlace", "otro"]


def test_markdown_inline_formatting_and_escapes():
    col = markdown(r"Hola **fuerte _anidada_** y `a*b*c` con \*esto\* y ~~fuera~~.")
    para = col.children[0].to_spec(DAYLIGHT)
    assert para["text"] == "Hola fuerte anidada y a*b*c con *esto* y fuera."
    spans = para["style"]["spans"]
    # (longitud, color, fondo, peso, tamaño, familia, cursiva, subrayado, tachado, enlace)
    assert spans[1][0] == len("fuerte ") and spans[1][3] == 700
    assert spans[2][3] == 700 and spans[2][6] is True
    code = next(s for s in spans if s[5] is not None)
    assert code[0] == len("a*b*c")
    assert spans[-2][8] is True


def test_markdown_code_block_keeps_its_text_verbatim():
    col = markdown("```py\nx = 1\n  *y*\n```")
    block = col.children[0]
    assert block.children[0].to_spec(DAYLIGHT)["text"] == "x = 1\n  *y*"


def test_markdown_links_call_on_link_with_the_url():
    seen: list[str] = []
    view = lambda: column()[
        markdown("Ve a [la web](https://a.b/c) o [aquí](#x).", on_link=seen.append, key="md")
    ]
    pilot = _pilot(view)
    keys = [n["key"] for n in pilot.a11y_tree() if n["role"] == "link"]
    for k in keys:
        pilot.a11y_action(k, "click")
    assert seen == ["https://a.b/c", "#x"]


def test_markdown_links_are_reached_with_tab_and_followed_with_enter():
    seen: list[str] = []
    view = lambda: column()[
        markdown("# Enlaces\n\n- [uno](u1)\n- [dos](u2)\n\nY [tres](u3).", on_link=seen.append, key="md")
    ]
    pilot = _pilot(view)
    for _ in range(3):
        pilot.press("tab")
        pilot.press("enter")
    assert seen == ["u1", "u2", "u3"]


def test_markdown_default_links_only_open_web_urls(monkeypatch):
    import webbrowser

    opened: list[str] = []
    monkeypatch.setattr(webbrowser, "open", opened.append)
    view = lambda: column()[markdown("[web](https://a.b) [local](./x.md)", key="md")]
    pilot = _pilot(view)
    for k in [n["key"] for n in pilot.a11y_tree() if n["role"] == "link"]:
        pilot.a11y_action(k, "click")
    assert opened == ["https://a.b"]


@pytest.mark.parametrize("source", ["", "\n\n", "#", "- ", "```", "> ", "**", "[x](", "`"])
def test_markdown_tolerates_odd_input(source):
    pilot = _pilot(lambda: column()[markdown(source, key="md")])
    pilot.frame()
