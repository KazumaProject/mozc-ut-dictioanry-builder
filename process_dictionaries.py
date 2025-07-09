#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_dictionaries.py
────────────────────────────────────────────────────────────────────────────
・Mozc に未収録なら identical 読みを許可
・skip_identical をパラメータ化
・SudachiPy で読みを取得して精度向上
────────────────────────────────────────────────────────────────────────────
"""

import os, glob, re
from typing import List, Set, Tuple, Dict

from kanjiconv import KanjiConv, SudachiDictType
from sudachipy import dictionary


# ───────── パス ─────────
MOZC_DIR = "./mozc"
DIC_DIR  = "./dic"

place_file   = f"{DIC_DIR}/place.txt"
names_file   = f"{DIC_DIR}/names.txt"
wiki_file    = f"{DIC_DIR}/wiki.txt"
neologd_file = f"{DIC_DIR}/neologd.txt"

place_output_file            = "./filtered_place.txt"
names_output_file            = "./filtered_names.txt"
wiki_output_file             = "./filtered_wiki.txt"
neologd_output_file          = "./filtered_neologd.txt"

place_output_file_not_same   = "./filtered_place_not_same.txt"
names_output_file_not_same   = "./filtered_names_not_same.txt"
wiki_output_file_not_same    = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same = "./filtered_neologd_not_same.txt"

suffix_file = f"{MOZC_DIR}/suffix.txt"


# ───────── Mozc 標準辞書読み込み ─────────
first_strings_set: Set[str] = set()
last_strings_set:  Set[str] = set()

for path in sorted(glob.glob(f"{MOZC_DIR}/dictionary0[0-9].txt")):
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ps = ln.rstrip("\n").split("\t")
            if len(ps) >= 2:
                first_strings_set.add(ps[0])
                last_strings_set.add(ps[-1])

suffix_set = {ln.strip() for ln in open(suffix_file, encoding="utf-8")} if os.path.exists(suffix_file) else set()


# ───────── ユーティリティ ─────────
kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")
sudachi_tokenizer = dictionary.Dictionary().create()

KATA2HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
    "ァィゥェォッャュョー",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "ぁぃぅぇぉっゃゅょー"
)

def katakana_to_hiragana(t: str) -> str:
    return t.translate(KATA2HIRA).replace("・", "")

def reading_with_sudachi(t: str) -> str:
    return "".join(
        katakana_to_hiragana(tok.reading_form() if tok.reading_form() not in ("", "*") else tok.surface())
        for tok in sudachi_tokenizer.tokenize(t)
    )

kana_re = re.compile(r"[ぁ-んァ-ヶー]")
symbol_re = re.compile(r"[^\wぁ-んァ-ン一-龥]")


# ───────── フィルタ ─────────
def filter_file(
    input_path: str, out_path: str, nosame_path: str,
    *, clean_last=False, remove_exclamation=False, extra_filter=False,
    require_filter=False, skip_long_entries=False, skip_identical=True
):
    if not os.path.exists(input_path):
        print(f"[SKIP] {input_path}")
        return

    filt, nosame = [], []
    for ln in open(input_path, encoding="utf-8"):
        ps = ln.rstrip("\n").split("\t")
        if len(ps) < 5:
            continue

        word = ps[0]
        reading_raw = ps[-1].replace("(", "").replace(")", "") if clean_last else ps[-1]

        if skip_long_entries and len(word) > 16:
            continue
        if symbol_re.search(reading_raw) and not symbol_re.search(word):
            continue
        if word.startswith("ん"):
            continue
        if remove_exclamation:
            reading_raw = reading_raw.replace("!", "")
        if extra_filter and any(c in reading_raw for c in "・！？"):
            continue

        word_clean = word.replace("・", "")
        reading_hira = katakana_to_hiragana(reading_raw)
        word_reading = reading_with_sudachi(word_clean)

        if skip_identical and word_reading == reading_hira and word_clean in first_strings_set:
            continue
        if require_filter:
            first_k = set(kana_re.findall(word_reading))
            last_k  = set(kana_re.findall(reading_hira))
            if last_k - first_k:
                nosame.append(ln.rstrip("\n"))
                continue
            if reading_raw in last_strings_set:
                continue

        filt.append(ln.rstrip("\n"))

    if filt:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(filt) + "\n")
    if nosame:
        with open(nosame_path, "w", encoding="utf-8") as f:
            f.write("\n".join(nosame) + "\n")
    print(f"{os.path.basename(input_path):<15} → {len(filt):>6} kept / {len(nosame):>6} flagged")


# ───────── 実行 ─────────
def main():
    filter_file(place_file, place_output_file, place_output_file_not_same, clean_last=True)
    filter_file(names_file, names_output_file, names_output_file_not_same)

    filter_file(
        wiki_file, wiki_output_file, wiki_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True,
        skip_identical=False
    )
    filter_file(
        neologd_file, neologd_output_file, neologd_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True,
        skip_identical=False
    )

if __name__ == "__main__":
    main()
