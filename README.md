# Парсер товаров в Excel для импорта в WordPress

Скрипт собирает карточки товаров с другого магазина и сохраняет в `.xlsx`, который удобно маппить в WP All Import / WooCommerce Import.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Быстрый запуск

```bash
python parser.py \
  --start-url "https://example.com/catalog" \
  --product-link-selector ".product-card a::attr(href)" \
  --title-selector "h1.product-title" \
  --price-selector ".price" \
  --description-selector ".description" \
  --image-selector ".gallery img::attr(src)" \
  --category-selector ".breadcrumbs a" \
  --sku-selector ".sku" \
  --output products.xlsx
```

## Что будет в Excel

- `post_title`
- `sku`
- `regular_price`
- `post_content`
- `images`
- `tax:product_cat`
- `meta:source_url`

## Как подобрать селекторы

1. Открой страницу в браузере.
2. Через DevTools (`F12`) найди элемент (название, цена и т.д.).
3. Скопируй CSS-селектор.
4. Для атрибутов используй формат: `селектор::attr(имя_атрибута)`.

Примеры:
- Ссылка товара: `.product-card a::attr(href)`
- Картинки: `.product-gallery img::attr(src)`

## Важно

- Используй задержку `--delay`, чтобы не перегружать сайт.
- Проверь legal/ToS магазина-источника перед парсингом.
