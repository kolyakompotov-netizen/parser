from bs4 import BeautifulSoup

from parser import _extract_many, _extract_one, _parse_selector


HTML = """
<html>
  <body>
    <h1 class='title'> Test Product </h1>
    <span class='price'> 19 990 ₽ </span>
    <div class='desc'> Great <b>item</b> for home </div>
    <img class='photo' src='/img/a.jpg' />
    <img class='photo' src='/img/b.jpg' />
    <a class='product-link' href='/p/1'>Item</a>
  </body>
</html>
"""


def test_parse_selector_attr():
    css, attr = _parse_selector("a.link::attr(href)")
    assert css == "a.link"
    assert attr == "href"


def test_extract_text_and_attr():
    soup = BeautifulSoup(HTML, "lxml")
    assert _extract_one(soup, "h1.title") == "Test Product"
    assert _extract_many(soup, "img.photo::attr(src)") == ["/img/a.jpg", "/img/b.jpg"]
