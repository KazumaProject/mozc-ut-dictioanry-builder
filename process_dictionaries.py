#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter Mozc-style dictionaries and compare results.
「見出し語＝読み」の新語（例: ちいかわ）を除外しないよう修正済み。
"""

import os
import glob
import re
import string
from kanjiconv import SudachiDictType, KanjiConv

# ───────── 設定 ──────────
mozc_dir = "./mozc"
place_file   = "./dic/place.txt"
names_file   = "./dic/names.txt"
wiki_file    = "./dic/wiki.txt"
neologd_file = "./dic/neologd.txt"

place_output_file   = "./filtered_place.txt"
names_output_file   = "./filtered_names.txt"
wiki_output_file    = "./filtered_wiki.txt"
neologd_output_file = "./filtered_neologd.txt"

place_output_file_not_same   = "./filtered_place_not_same.txt"
names_output_file_not_same   = "./filtered_names_not_same.txt"
wiki_output_file_not_same    = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same = "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(mozc_dir, "suffix.txt")

# ───────── 既存 Mozc 辞書の語を収集 ──────────
dictionary_files = sorted(glob.glob(os.path.join(mozc_dir, "dictionary0[0-9].txt")))
first_strings_set, last_strings_set = set(), set()

kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")

def clean_last_string(text: str) -> str:
    """Remove parentheses only (内容は残す)."""
    return text.replace("(", "").replace(")", "")

print("Processing Mozc dictionary files...")
for file in dictionary_files:
    with open(file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                first_strings_set.add(parts[0])
                last_strings_set.add(parts[-1])

# ───────── suffix.txt ──────────
suffix_set = set()
if os.path.exists(suffix_file):
    with open(suffix_file, encoding="utf-8") as f:
        suffix_set.update({line.strip() for line in f if line.strip()})
print(f"Loaded {len(suffix_set)} suffixes.")

# ───────── ユーティリティ ──────────
def to_hiragana(text: str) -> str:
    return kanji_conv.to_hiragana(text)

def extract_kana(text: str) -> set[str]:
    return set(re.findall(r'[ぁ-んァ-ヶー]', text))

def katakana_to_hiragana(text: str) -> str:
    text = text.replace("・", "")
    return text.translate(str.maketrans(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンァィゥェォッャュョー",
        "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんぁぃぅぇぉっゃゅょー"
    ))

# ───────── メイン処理 ──────────
def filter_file(
    input_file: str,
    output_file: str,
    not_same_output_file: str,
    *,
    clean_last: bool = False,
    remove_exclamation: bool = False,
    extra_filter: bool = False,
    require_filter: bool = False,
    skip_long_entries: bool = False,
) -> None:
    """フィルタリング本体"""
    filtered_lines, not_same_lines = [], []

    print(f"Processing {input_file}...")
    with open(input_file, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 5:
                continue

            first_str = parts[0]
            last_str  = clean_last_string(parts[-1]) if clean_last else parts[-1]

            if skip_long_entries and len(first_str) > 16:
                continue

            if re.search(r'[^\wぁ-んァ-ン一-龥]', last_str) and not re.search(r'[^\wぁ-んァ-ン一-龥]', first_str):
                continue
            if first_str.startswith("ん"):
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            first_str_cleaned = first_str.replace("・", "").strip()
            last_str_hira     = katakana_to_hiragana(last_str).strip()

            if extra_filter and any(c in last_str for c in "・！？"):
                continue

            kana_set_first = extract_kana(to_hiragana(first_str_cleaned))
            kana_set_last  = extract_kana(last_str_hira)

            if require_filter:
                # ───── 修正ポイント ─────
                if first_str_cleaned == last_str_hira:
                    # Mozc に既に同じ見出しがあれば重複として除外
                    if first_str in first_strings_set:
                        continue
                # ──────────────────────

                if kana_set_last - kana_set_first:
                    print(f"Possibly incorrect reading: {first_str} -> {last_str}")
                    not_same_lines.append(line.strip())
                    continue

                if last_str in last_strings_set:
                    continue  # 読みが Mozc 既存ならスキップ

            filtered_lines.append(line.strip())

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")

    if not_same_lines:
        with open(not_same_output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(not_same_lines) + "\n")

    print(f"Filtered output saved to {output_file}")
    if not_same_lines:
        print(f"Potentially incorrect readings saved to {not_same_output_file}")

# ───────── 個別フィルタ実行 ──────────
if os.path.exists(place_file):
    filter_file(place_file, place_output_file, place_output_file_not_same, clean_last=True)
else:
    print(f"Warning: Source file not found, skipping: {place_file}")

if os.path.exists(names_file):
    filter_file(names_file, names_output_file, names_output_file_not_same)
else:
    print(f"Warning: Source file not found, skipping: {names_file}")

if os.path.exists(wiki_file):
    filter_file(
        wiki_file, wiki_output_file, wiki_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True
    )
else:
    print(f"Warning: Source file not found, skipping: {wiki_file}")

if os.path.exists(neologd_file):
    filter_file(
        neologd_file, neologd_output_file, neologd_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True
    )
else:
    print(f"Warning: Source file not found, skipping: {neologd_file}")

# ───────── Wiki vs NEologd 比較 ──────────
def load_data(path: str) -> dict[tuple[str, str], str]:
    data = {}
    with open(path, encoding="utf-8") as f:
        for l in f:
            p = l.rstrip("\n").split("\t")
            if len(p) >= 2:
                data[(p[0], p[-1])] = l.rstrip("\n")
    return data

def write_data(path: str, data: dict, keys: set[tuple[str, str]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for k in sorted(keys):
            f.write(f"{data[k]}\n")

if all(os.path.exists(p) for p in (wiki_output_file, neologd_output_file)):
    print("Comparing filtered wiki and neologd files...")
    wiki_data     = load_data(wiki_output_file)
    neologd_data  = load_data(neologd_output_file)

    common_keys       = set(wiki_data) & set(neologd_data)
    only_wiki_keys    = set(wiki_data) - set(neologd_data)
    only_neologd_keys = set(neologd_data) - set(wiki_data)

    write_data("wiki_neologd_common.txt", wiki_data, common_keys)
    write_data("only_wiki.txt",          wiki_data, only_wiki_keys)
    write_data("only_neologd.txt",       neologd_data, only_neologd_keys)

    print("Comparison files generated.")
else:
    print("Skipping comparison (wiki / neologd output missing).")

print("Script finished.")
