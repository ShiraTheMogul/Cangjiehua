# 倉頡化 Cangjiehua
Tools for integrating the Cangjie Input Method 倉頡輸入法 into Anki and Pleco.

# Items
- Cangjie Input Pleco Dictionary + generator for it
- Tool for filling Anki decks with Cangjie combinations; it's a little finicky at times but gets the job done.
- Cangjie Input lists taken from [ikwbb/cangjie-practice-tool](https://github.com/ikwbb/cangjie-practice-tool) - something I must recommend to any new users!

I also recommend viewing [my Anki deck](https://ankiweb.net/shared/info/2113549423) for learning Cangjie with Literary Chinese, derived from [@ikwbb](https://github.com/ikwbb)'s work!

# Dependencies 
Both of the current tools require Python 3.7+ and `pypinyin`. 

```bash
pip install pypinyin
```

## Pleco Cangjie Dictionary Generator

# Pipeline

`cangjie_to_pleco_pqb.py` builds a native Pleco `.pqb` dictionary where:

- Each Han character is an entry, appended to the main entry (In other words, it will be in-line with your usual Mandarin entries. 
- The definitions list said dictionary gives features Chinese and Latin versions of inputs. 
- Cangjie 3 and Cangjie 5 are supported; merged if identical, separated if not.

Line breaks use Pleco’s internal newline marker (U+EAB1), so formatting is preserved in-app.

Example output:
```
Cangjie3:
日 月 金
a b c

Cangjie5:
日 月
a b
```

Or:
```
Cangjie
日 月 金:
a b c
```

# Usage
```bash
python cangjie_to_pleco_pqb.py --cj3 cangjie3.txt --cj5 cangjie5.txt --out Cangjie_Input.pqb
```

Optional metadata:
```
--dict-name - The Title
--menu-name - How it shows in the menu
--short-name - How it shows in short order
--icon - How it shows in definition lists 
```

Technically, you can use this for all sorts of Pleco dictionary nonsense, but here I'm using it for Cangjie...

## Anki Deck Cangjie Filler

This fills an Anki `.txt` export and fills one or more columns with Cangjie inputs, built by comparing a `{Hanzi}` field with the `cangjie3.txt` and `cangjie5.txt` files. It works with Latin and Chinese characters, uses 1-based column matching, and supports UTF-8 BOM. 

Only Han characters are processed for safety, supporting up to Extension J.

# Usage:
```bash
python fill_anki_cangjie.py --in-txt deck.txt --out-txt deck_out.txt --source-col 4 --cj3-col 6 --cj3-table cangjie3.txt --output prompts
```

If you want Cangjie5...
```
--cj5-col 7 \
--cj5-table cangjie5.txt
```
Use these. 

Then for output modes...
```
--output prompts (default):
日月金 / 竹戈

--output codes:
abc / hi
```

## Unihan Cangjie Pinger
Input a `.txt` or `.csv` list of characters and get their Cangjie codes according to the Unihan database. It includes features such as choosing a column, the `k` part of Unihan data, and can skip empty cells (after 3, it stops automatically). 

It will produce a local SQLite cache of the Unihan database of around 12 KB. 

# Usage

For example...
```bash
python append_unihan_cangjie_csv.py --in-csv zi.csv --out-csv zi_with_cangjie.csv --source-col Hanzi --out-col kCangjie --verbose
```

# About this Repository
I created these tools for self-study of Cangjie, having noticed that it is very undersupported in the main Chinese learning app I use (Pleco). I decided that what I did was decent enough to release. I am currently learning Literary Chinese and found that it was a bit awkward using Pinyin to write it; not only are the common characters often buried in a fleet of common Mandarin ones, it's also not phonetically neutral! Japanese, Korean, and Vietnamese used this language. 

Cangjie itself is only really used in Hong Kong nowadays, and is considered quite difficult to learn. It encourages recognition of characters and has you write them based on structure; this way, you do not need to learn the phonology of any character to write it. This makes it ideal for Cantonese and other Chinese topolects, though many are moving to their own rime inputs; e.g. Cantonese's Jyutping input, Shanghainese's [Yahwe-Rime-Zaonhe](https://github.com/wugniu/rime-yahwe_zaonhe), etc. Regardless, it is still used and useful, and I personally think it is incredibly handy for Literary Chinese in particular given its unspoken nature. Thus came this repository.

# Acknowledgements
ChatGPT was used to assist with the development of this code and its debugging. 

## Licence
As a supporter of the [Free Software Movement](https://www.fsf.org/about/) and its values, this is published under a [GNU General Public Licence v3.0](https://www.gnu.org/licenses/gpl-3.0.en.html). Contributions are encouraged. 
