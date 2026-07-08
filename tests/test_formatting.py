from lexibot.handlers import highlight_word


def test_highlights_word_case_insensitively():
    assert highlight_word("Apple is an apple.", "apple") == (
        "<b>Apple</b> is an <b>apple</b>."
    )


def test_does_not_highlight_inside_another_word():
    assert highlight_word("A cat is in a category.", "cat") == (
        "A <b>cat</b> is in a category."
    )


def test_escapes_html_around_highlight():
    assert highlight_word("Use <run> & run.", "run") == (
        "Use &lt;<b>run</b>&gt; &amp; <b>run</b>."
    )
