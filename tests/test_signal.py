from aurora import Signal


def test_get_set_update():
    s = Signal(1)
    assert s() == 1 and s.value == 1
    s.set(2)
    s.update(lambda v: v * 10)
    assert s() == 20


def test_subscribers_only_on_change():
    s = Signal("a")
    seen: list[str] = []
    unsubscribe = s.subscribe(seen.append)
    s.set("a")  # mismo valor: no notifica
    s.set("b")
    unsubscribe()
    s.set("c")
    assert seen == ["b"]
