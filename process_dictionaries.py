#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter multiple dictionary sources, excluding entries already in Mozc,
while keeping new words / proper nouns.

✓ NEologd / Wikipedia: use features[7] (reading) instead of parts[-1]
✓ Neologd: keep only POS "名詞,固有名詞"
"""

import os
import glob
import re
import string
from kanjiconv import SudachiDictType
from kanjiconv import KanjiConv

# ────────── パス設定 ──────────
mozc_dir = "./mozc"
place_file = "./dic/place.txt"
names_file = "./dic/names.txt"
wiki_file = "./dic/wiki.txt"
neologd_file = "./dic/neologd.txt"

place_output_file = "./filtered_place.txt"
names_output_file = "./filtered_names.txt"
wiki_output_file = "./filtered_wiki.txt"
neologd_output_file = "./filtered_neologd.txt"

place_output_file_not_same = "./filtered_place_not_same.txt"
names_output_file_not_same = "./filtered_names_not_same.txt"
wiki_output_file_not_same = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same = "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(mozc_dir, "suffix.txt")

# ────────── Mozc 辞書読み込み ──────────
dictionary_files = sorted(glob.glob(os.path.join(mozc_dir, "dictionary0[0-9].txt")))

first_strings_set = set()
last_strings_set = set()  # Mozc に既にある読み

kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")

def clean_last_string(text: str) -> str:
    """Surrounding parentheses only are removed."""
    return text.replace("(", "").replace(")", "")

print("Processing Mozc dictionary files ...")
for file in dictionary_files:
    with open(file, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                first_strings_set.add(parts[0])
                last_strings_set.add(parts[-1])

# ────────── suffix.txt ──────────
suffix_set = set()
if os.path.exists(suffix_file):
    with open(suffix_file, encoding="utf-8") as f:
        for line in f:
            suf = line.strip()
            if suf:
                suffix_set.add(suf)
print(f"Loaded {len(suffix_set)} suffixes.")

# ────────── 文字ユーティリティ ──────────
def to_hiragana(text: str) -> str:
    return kanji_conv.to_hiragana(text)

def extract_kana(text: str):
    return set(re.findall(r'[ぁ-んァ-ヶー]', text))

def katakana_to_hiragana(text: str) -> str:
    text = text.replace("・", "")
    return text.translate(str.maketrans(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィゥェォッャュョー",
        "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉっゃゅょー"
    ))

# ────────── Mecab 形式行パーサ ──────────
def parse_mecab_line(line: str):
    """
    Return (surface, reading, pos_head) for a MeCab-format dictionary line.
    reading = features[7] (or surface if '*')
    pos_head = first two POS fields, e.g. '名詞,固有名詞'
    """
    surface, feat_str = line.split("\t", 1)
    feats = feat_str.split(",")
    reading = feats[7] if len(feats) > 7 and feats[7] != "*" else surface
    pos_head = ",".join(feats[:2]) if len(feats) >= 2 else ""
    return surface, reading, pos_head

# ────────── メインフィルタ関数 ──────────
def filter_file(
    input_file: str, output_file: str, not_same_output_file: str,
    *, clean_last=False, remove_exclamation=False,
    extra_filter=False, require_filter=False, skip_long_entries=False,
    line_parser=None, proper_only=False
):
    filtered = []
    not_same = []

    print(f"Processing {input_file} ...")
    with open(input_file, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # ---- 行パース ----
            if line_parser:
                surface, reading, pos_head = line_parser(line)
                if proper_only and pos_head != "名詞,固有名詞":
                    continue
                first_str, last_str = surface, reading
            else:
                parts = line.split("\t")
                if len(parts) < 5:
                    continue
                first_str = parts[0]
                last_str = clean_last_string(parts[-1]) if clean_last else parts[-1]

            # ---- 基本フィルタ ----
            if skip_long_entries and len(first_str) > 32:  # 長い固有名詞も残すなら上限上げ
                continue

            symbol_pattern = re.compile(r'[^\wぁ-んァ-ン一-龥・]')
            if symbol_pattern.search(last_str) and not symbol_pattern.search(first_str):
                continue

            if first_str.startswith("ん"):
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            if extra_filter and ("！" in last_str or "？" in last_str):
                continue

            first_str_clean = first_str.replace("・", "").strip()
            last_str_hira = katakana_to_hiragana(last_str).strip()

            kana_set_first = extract_kana(to_hiragana(first_str_clean))
            kana_set_last = extract_kana(last_str_hira)

            # ---- Mozc 重複排除 & 読み比較 ----
            if require_filter:
                if first_str_clean == last_str_hira:
                    continue
                if kana_set_last - kana_set_first:
                    not_same.append(line)
                    continue
                if last_str in last_strings_set:
                    continue
                filtered.append(line)
            else:
                if last_str in last_strings_set:
                    continue
                filtered.append(line)

    with open(output_file, "w", encoding="utf-8") as wf:
        wf.write("\n".join(filtered) + ("\n" if filtered else ""))

    if not_same:
        with open(not_same_output_file, "w", encoding="utf-8") as wf:
            wf.write("\n".join(not_same) + "\n")

    print(f"  ✔ filtered → {output_file}  ({len(filtered)} lines)")
    if not_same:
        print(f"  ⚠ suspect  → {not_same_output_file} ({len(not_same)} lines)")

# ────────── 個別ソースの実行 ──────────
if os.path.exists(place_file):
    filter_file(place_file, place_output_file, place_output_file_not_same,
                clean_last=True)
else:
    print(f"Skip: {place_file} not found")

if os.path.exists(names_file):
    filter_file(names_file, names_output_file, names_output_file_not_same)
else:
    print(f"Skip: {names_file} not found")

if os.path.exists(wiki_file):
    filter_file(wiki_file, wiki_output_file, wiki_output_file_not_same,
                remove_exclamation=True, extra_filter=True, require_filter=True,
                skip_long_entries=True, line_parser=parse_mecab_line)
else:
    print(f"Skip: {wiki_file} not found")

if os.path.exists(neologd_file):
    filter_file(neologd_file, neologd_output_file, neologd_output_file_not_same,
                remove_exclamation=True, extra_filter=True, require_filter=True,
                skip_long_entries=True, line_parser=parse_mecab_line,
                proper_only=True)  # 名詞,固有名詞 のみ
else:
    print(f"Skip: {neologd_file} not found")

# ────────── Wiki vs NEologd 比較 ──────────
common_output = "wiki_neologd_common.txt"
only_wiki_output = "only_wiki.txt"
only_neologd_output = "only_neologd.txt"

def load_dict(fp: str):
    d = {}
    with open(fp, encoding="utf-8") as f:
        for ln in f:
            parts = ln.rstrip("\n").split("\t")
            if len(parts) >= 2:
                d[(parts[0], parts[-1])] = ln.rstrip("\n")
    return d

def dump(out_fp: str, data: dict, keys):
    with open(out_fp, "w", encoding="utf-8") as f:
        for k in sorted(keys):
            f.write(data[k] + "\n")

if os.path.exists(wiki_output_file) and os.path.exists(neologd_output_file):
    print("Comparing wiki vs neologd ...")
    wiki_d = load_dict(wiki_output_file)
    neo_d = load_dict(neologd_output_file)
    common = wiki_d.keys() & neo_d.keys()
    wiki_only = wiki_d.keys() - neo_d.keys()
    neo_only = neo_d.keys() - wiki_d.keys()
    dump(common_output, wiki_d, common)
    dump(only_wiki_output, wiki_d, wiki_only)
    dump(only_neologd_output, neo_d, neo_only)
    print("  ✔ comparison done")
else:
    print("Comparison skipped (filtered files missing)")

print("Script finished.")
