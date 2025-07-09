#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_dictionaries.py
────────────────────────────────────────────────────────────────────
• Mozc 未収録なら「表記＝読み」のエントリも許可  
• skip_identical パラメータで排他条件を制御  
• SudachiPy（full 辞書）で品詞ごとに読みを取得し精度向上  
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

# ────────────────────────────────
# 0. パス定義
# ────────────────────────────────
MOZC_DIR = "./mozc"
DIC_DIR = "./dic"

place_file = f"{DIC_DIR}/place.txt"
names_file = f"{DIC_DIR}/names.txt"
wiki_file = f"{DIC_DIR}/wiki.txt"
neologd_file = f"{DIC_DIR}/neologd.txt"

place_out = "./filtered_place.txt"
names_out = "./filtered_names.txt"
wiki_out = "./filtered_wiki.txt"
neologd_out = "./filtered_neologd.txt"

place_ng = "./filtered_place_not_same.txt"
names_ng = "./filtered_names_not_same.txt"
wiki_ng = "./filtered_wiki_not_same.txt"
neologd_ng = "./filtered_neologd_not_same.txt"

suffix_file = f"{MOZC_DIR}/suffix.txt"

# ────────────────────────────────
# 1. Mozc 標準辞書読み込み
# ────────────────────────────────
first_strings_set: Set[str] = set()
last_strings_set: Set[str] = set()

print("Loading Mozc core dictionaries ...")
for p in sorted(glob.glob(f"{MOZC_DIR}/dictionary0[0-9].txt")):
    with open(p, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                first_strings_set.add(parts[0])
                last_strings_set.add(parts[-1])

suffix_set: Set[str] = (
    {ln.strip() for ln in open(suffix_file, encoding="utf-8")}
    if os.path.exists(suffix_file)
    else set()
)
print(f"suffix.txt: {len(suffix_set)} 行\n")

# ────────────────────────────────
# 2. ユーティリティ
# ────────────────────────────────
kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")
# SudachiPy (full dictionary)
sudachi_tokenizer = dictionary.Dictionary(dict_type="full").create()

KATA2HIRA = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
    "ァィゥェォッャュョー",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "ぁぃぅぇぉっゃゅょー",
)

def katakana_to_hiragana(text: str) -> str:
    """カタカナ→ひらがな + 中点除去"""
    return text.translate(KATA2HIRA).replace("・", "")

def reading_with_sudachi(text: str) -> str:
    """SudachiPy で品詞ごとに読みを取り、ひらがな化して結合"""
    return "".join(
        katakana_to_hiragana(tok.reading_form() if tok.reading_form() not in ("", "*") else tok.surface())
        for tok in sudachi_tokenizer.tokenize(text)
    )

kana_re = re.compile(r"[ぁ-んァ-ヶー]")
symbol_re = re.compile(r"[^\wぁ-んァ-ン一-龥]")

# ────────────────────────────────
# 3. フィルタ関数
# ────────────────────────────────
def filter_file(
    src: str,
    dst: str,
    ng_dst: str,
    *,
    clean_last: bool = False,
    remove_exclamation: bool = False,
    extra_filter: bool = False,
    require_filter: bool = False,
    skip_long: bool = False,
    skip_identical: bool = True,
) -> None:
    if not os.path.exists(src):
        print(f"[SKIP] {src} not found")
        return

    kept: List[str] = []
    flagged: List[str] = []

    for line in open(src, encoding="utf-8"):
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 5:
            continue

        word = parts[0]
        reading_raw = parts[-1].replace("(", "").replace(")", "") if clean_last else parts[-1]

        if skip_long and len(word) > 16:
            continue
        if symbol_re.search(reading_raw) and not symbol_re.search(word):
            continue
        if word.startswith("ん"):
            continue
        if remove_exclamation:
            reading_raw = reading_raw.replace("!", "")
        if extra_filter and any(ch in reading_raw for ch in "・！？"):
            continue

        word_clean = word.replace("・", "")
        reading_hira = katakana_to_hiragana(reading_raw)
        word_reading = reading_with_sudachi(word_clean)

        # Mozc に既にある identical はスキップ
        if skip_identical and word_reading == reading_hira and word_clean in first_strings_set:
            continue
        # require_filter で identical は除外
        if require_filter and word_reading == reading_hira:
            continue

        # かな集合差で不一致チェック
        if require_filter:
            if set(kana_re.findall(reading_hira)) - set(kana_re.findall(word_reading)):
                flagged.append(line.rstrip("\n"))
                continue
            if reading_raw in last_strings_set:
                continue

        kept.append(line.rstrip("\n"))

    if kept:
        with open(dst, "w", encoding="utf-8") as f:
            f.write("\n".join(kept) + "\n")
    if flagged:
        with open(ng_dst, "w", encoding="utf-8") as f:
            f.write("\n".join(flagged) + "\n")

    print(f"{os.path.basename(src):<15} → {len(kept):>6} kept / {len(flagged):>6} flagged")

# ────────────────────────────────
# 4. wiki と neologd の比較
# ────────────────────────────────
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
    wiki_d = load_dict(wiki_p)
    neo_d = load_dict(neo_p)
    common = wiki_d.keys() & neo_d.keys()
    only_wiki = wiki_d.keys() - neo_d.keys()
    only_neo = neo_d.keys() - wiki_d.keys()
    write_subset("wiki_neologd_common.txt", wiki_d, common)
    write_subset("only_wiki.txt", wiki_d, only_wiki)
    write_subset("only_neologd.txt", neo_d, only_neo)
    print(f"common: {len(common)}, wiki only: {len(only_wiki)}, neologd only: {len(only_neo)}")

# ────────────────────────────────
# 5. メイン
# ────────────────────────────────
def main():
    # place / names
    filter_file(place_file, place_out, place_ng, clean_last=True)
    filter_file(names_file, names_out, names_ng)

    # wiki / neologd — identical も収集
    filter_file(
        wiki_file,
        wiki_out,
        wiki_ng,
        remove_exclamation=True,
        extra_filter=True,
        require_filter=True,
        skip_long=True,
        skip_identical=False,
    )
    filter_file(
        neologd_file,
        neologd_out,
        neologd_ng,
        remove_exclamation=True,
        extra_filter=True,
        require_filter=True,
        skip_long=True,
        skip_identical=False,
    )

    compare_dicts(wiki_out, neologd_out)
    print("All done.")

if __name__ == "__main__":
    main()
