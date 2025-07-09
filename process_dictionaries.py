#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_dictionaries.py
────────────────────────────────────────────────────────────────────
  • Mozc 未収録なら identical を許可
  • skip_identical パラメータ化
  • SudachiPy(full) で読み取得
  • min_fields で列数の柔軟化（UT 辞書 3 列対応）
────────────────────────────────────────────────────────────────────
要件:
    pip install kanjiconv sudachipy sudachidict_full
"""

import glob
import os
import re
from typing import Dict, List, Set, Tuple

from kanjiconv import KanjiConv, SudachiDictType
from sudachipy import dictionary

# ─────────────── パス設定 ───────────────
MOZC_DIR = "./mozc"
DIC_DIR = "./dic"

place_file, names_file   = f"{DIC_DIR}/place.txt", f"{DIC_DIR}/names.txt"
wiki_file,  neologd_file = f"{DIC_DIR}/wiki.txt",  f"{DIC_DIR}/neologd.txt"

place_out,  names_out    = "./filtered_place.txt", "./filtered_names.txt"
wiki_out,   neologd_out  = "./filtered_wiki.txt",  "./filtered_neologd.txt"

place_ng, names_ng       = "./filtered_place_not_same.txt", "./filtered_names_not_same.txt"
wiki_ng,  neologd_ng     = "./filtered_wiki_not_same.txt",  "./filtered_neologd_not_same.txt"

suffix_file = f"{MOZC_DIR}/suffix.txt"

# ─────────────── Mozc 標準辞書読み込み ───────────────
first_strings_set: Set[str] = set()
last_strings_set:  Set[str] = set()

for p in sorted(glob.glob(f"{MOZC_DIR}/dictionary0[0-9].txt")):
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ps = ln.rstrip("\n").split("\t")
            if len(ps) >= 2:
                first_strings_set.add(ps[0])
                last_strings_set.add(ps[-1])

suffix_set: Set[str] = set()
if os.path.exists(suffix_file):
    with open(suffix_file, encoding="utf-8") as f:
        suffix_set = {ln.strip() for ln in f if ln.strip()}

print(f"Mozc core: {len(first_strings_set)} words, suffix: {len(suffix_set)} lines")

# ─────────────── ユーティリティ ───────────────
kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")
sudachi_tokenizer = dictionary.Dictionary(dict_type="full").create()

KATA2HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
    "ァィゥェォッャュョー",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "ぁぃぅぇぉっゃゅょー",
)

def kata_to_hira(t: str) -> str:
    return t.translate(KATA2HIRA).replace("・", "")

def reading_with_sudachi(t: str) -> str:
    return "".join(
        kata_to_hira(tok.reading_form() if tok.reading_form() not in ("", "*") else tok.surface())
        for tok in sudachi_tokenizer.tokenize(t)
    )

kana_re    = re.compile(r"[ぁ-んァ-ヶー]")
symbol_re  = re.compile(r"[^\wぁ-んァ-ン一-龥]")

# ─────────────── フィルタ関数 ───────────────
def filter_file(
    src: str, dst: str, ng_dst: str,
    *, clean_last=False, remove_excl=False, extra_filter=False,
    require_filter=False, skip_long=False, skip_identical=True,
    min_fields: int = 2,
) -> None:
    if not os.path.exists(src):
        print(f"[SKIP] {src}")
        return

    kept: List[str] = []
    flagged: List[str] = []

    for ln in open(src, encoding="utf-8"):
        ps = ln.rstrip("\n").split("\t")
        if len(ps) < min_fields:
            continue

        word = ps[0]
        reading_raw = ps[-1].replace("(", "").replace(")", "") if clean_last else ps[-1]

        if skip_long and len(word) > 16:
            continue
        if symbol_re.search(reading_raw) and not symbol_re.search(word):
            continue
        if word.startswith("ん"):
            continue
        if remove_excl:
            reading_raw = reading_raw.replace("!", "")
        if extra_filter and any(c in reading_raw for c in "・！？"):
            continue

        word_clean   = word.replace("・", "")
        reading_hira = kata_to_hira(reading_raw)
        word_reading = reading_with_sudachi(word_clean)

        if skip_identical and word_reading == reading_hira and word_clean in first_strings_set:
            continue
        if require_filter and word_reading == reading_hira:
            continue

        if require_filter:
            if set(kana_re.findall(reading_hira)) - set(kana_re.findall(word_reading)):
                flagged.append(ln.rstrip("\n"))
                continue
            if reading_raw in last_strings_set:
                continue

        kept.append(ln.rstrip("\n"))

    if kept:
        with open(dst, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
    if flagged:
        with open(ng_dst, "w", encoding="utf-8") as f:
            f.write("\n".join(flagged) + "\n")

    print(f"{os.path.basename(src):<15} → {len(kept):>6} kept / {len(flagged):>6} flagged")

# ─────────────── 比較ユーティリティ ───────────────
def load_dict(path: str) -> Dict[Tuple[str, str], str]:
    d: Dict[Tuple[str, str], str] = {}
    with open(path, encoding="utf-8") as f:
        for ln in f:
            ps = ln.rstrip("\n").split("\t")
            if len(ps) >= 2:
                d[(ps[0], ps[-1])] = ln.rstrip("\n")
    return d

def write_subset(path: str, data: Dict[Tuple[str, str], str], keys: Set[Tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for k in sorted(keys):
            f.write(f"{data[k]}\n")

def compare_dicts(wiki_p: str, neo_p: str):
    if not (os.path.exists(wiki_p) and os.path.exists(neo_p)):
        return
    wiki_d, neo_d = load_dict(wiki_p), load_dict(neo_p)
    common, only_wiki, only_neo = wiki_d.keys() & neo_d.keys(), wiki_d.keys() - neo_d.keys(), neo_d.keys() - wiki_d.keys()
    write_subset("wiki_neologd_common.txt", wiki_d, common)
    write_subset("only_wiki.txt", wiki_d, only_wiki)
    write_subset("only_neologd.txt", neo_d, only_neo)
    print(f"[compare] common={len(common)} wiki_only={len(only_wiki)} neo_only={len(only_neo)}")

# ─────────────── メイン ───────────────
def main():
    # place / names
    filter_file(place_file, place_out, place_ng, clean_last=True, min_fields=3)
    filter_file(names_file, names_out, names_ng, min_fields=3)

    # wiki / neologd — identical も収集
    filter_file(
        wiki_file, wiki_out, wiki_ng,
        remove_excl=True, extra_filter=True,
        require_filter=True, skip_long=True,
        skip_identical=False, min_fields=3,
    )
    filter_file(
        neologd_file, neologd_out, neologd_ng,
        remove_excl=True, extra_filter=True,
        require_filter=True, skip_long=True,
        skip_identical=False, min_fields=3,
    )

    compare_dicts(wiki_out, neologd_out)
    print("All done.")

if __name__ == "__main__":
    main()
