# HTML data parser

CLI-парсер для поиска данных в HTML файлах.

## Что умеет
- Ищет по умолчанию:
  - `mm/yy` (например `09/27`)
  - `mm/yyyy` (например `09/2027`)
  - `dd.mm.yy`, `dd/mm/yy`, `dd-mm-yy`
  - `dd.mm.yyyy`, `dd/mm/yyyy`, `dd-mm-yyyy`
- Режимы анализа:
  - `raw` — по исходному HTML
  - `text` — по видимому тексту (режим по умолчанию, меньше ложных совпадений)
  - `message` — по сообщениям (одно сообщение → потом следующее)
- Сохраняет:
  - `matches.csv`
  - `unique_values.txt`
  - TXT файл формата `xxxxxxxxxxxxxxxx|xx/xx|xxx` (только из подписанных полей `number:`, `mm/yy:`, `cvc:`)

## Главное изменение
Если не указать путь к папке и имя TXT файла аргументами, скрипт **спросит их у вас в консоли**.

## Запуск

```bash
# Интерактивный запуск: скрипт спросит путь к HTML и имя/путь TXT файла
python3 html_data_parser.py

# Явно указать папку
python3 html_data_parser.py --input-dir ./my_html_folder

# Указать и папку, и имя TXT файла (без вопросов)
python3 html_data_parser.py --input-dir ./my_html_folder --combo-file final.txt
```

## Для вашего кейса (чат по сообщениям)

```bash
python3 html_data_parser.py \
  --input-dir ./my_html_folder \
  --by-message \
  --only-text \
  --out-dir ./result \
  --combo-file cards.txt
```

Формат строк в TXT (берутся только поля `number:`, `mm/yy:`, `cvc:`):

```text
4111111111111111|10/27|123
```

## Если хотите отключить вопросы

```bash
python3 html_data_parser.py --no-prompt --input-dir ./my_html_folder
```


Повторяющиеся строки в `cards_mm_yy_cvc.txt` и дубли одинаковых записей в `matches.csv` автоматически удаляются.

Комбинации `card|mm/yy|cvc` собираются последовательно по меткам `number -> mm/yy -> cvc` и не смешиваются с другими случайными `mm/yy` или `cvc` из файла.

Если нужно старое поведение с большим количеством совпадений, добавьте `--include-raw` (поиск и в исходном HTML, и в text).

Также копия combo-файла всегда сохраняется в `--out-dir/cards_mm_yy_cvc.txt`.
Также файл всегда дублируется в фиксированную папку `./parsed_output/cards_mm_yy_cvc.txt` (даже если `--out-dir` другой).
