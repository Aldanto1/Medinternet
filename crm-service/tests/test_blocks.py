"""Тесты сборки блоков конструктора в HTML для Telegram."""
from app.api.broadcast import blocks_to_html


def test_title_is_bold_uppercase():
    assert blocks_to_html([{"type": "title", "text": "Привет мир"}]) == "<b>ПРИВЕТ МИР</b>"


def test_order_and_spacing():
    html = blocks_to_html([
        {"type": "title", "text": "T"},
        {"type": "subtitle", "text": "Sub"},
        {"type": "text", "text": "body"},
    ])
    assert html == "<b>T</b>\n\n<b>Sub</b>\n\nbody"


def test_link_block():
    html = blocks_to_html([{"type": "link", "text": "тут", "url": "https://x.ru"}])
    assert html == '<a href="https://x.ru">тут</a>'


def test_html_is_escaped():
    assert blocks_to_html([{"type": "text", "text": "a < b & c"}]) == "a &lt; b &amp; c"


def test_empty_blocks_skipped():
    html = blocks_to_html([
        {"type": "title", "text": ""},
        {"type": "text", "text": "x"},
    ])
    assert html == "x"
