#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filter Mozc-style dictionaries and compare results.
「見出し語＝読み」で既存辞書にある語のみを除外するよう修正済み。
読みが既存辞書に存在する場合も除外するよう、元のロジックに修正。
【最終修正】比較ロジックを全面的に刷新し、データの正規化処理を導入。
【デバッグ機能追加】どの単語がどのルールで除外されたかを出力する機能を追加。
"""

import os
import glob
import re
import string
from kanjiconv import SudachiDictType, KanjiConv

# ───────── 設定 ──────────
# 各ファイルのパスはご自身の環境に合わせて適宜修正してください
mozc_dir = "./mozc"
place_file    = "./dic/place.txt"
names_file    = "./dic/names.txt"
wiki_file     = "./dic/wiki.txt"
neologd_file  = "./dic/neologd.txt"

place_output_file    = "./filtered_place.txt"
names_output_file    = "./filtered_names.txt"
wiki_output_file     = "./filtered_wiki.txt"
neologd_output_file  = "./filtered_neologd.txt"

place_output_file_not_same    = "./filtered_place_not_same.txt"
names_output_file_not_same    = "./filtered_names_not_same.txt"
wiki_output_file_not_same     = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same  = "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(mozc_dir, "suffix.txt")

# ───────── 個別の除外リスト ──────────
# ファイルごとに除外したい単語を (見出し語, 読み) のタプルで指定
specific_exclusions = {
    neologd_file: [
        ("明倫養賢堂", "ようけんどう"),
    ]
}


# ───────── 既存 Mozc 辞書の語を収集 ──────────
dictionary_files = sorted(glob.glob(os.path.join(mozc_dir, "dictionary0[0-9].txt")))
first_strings_set, last_strings_set = set(), set()

# kanjiconvの初期化
try:
    kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")
except Exception as e:
    print(f"Error initializing KanjiConv: {e}")
    print("Please ensure you have SudachiDict-full installed (`pip install SudachiDict-full`).")
    def to_hiragana_fallback(text: str) -> str:
        print("Warning: kanjiconv not available. Kanji-to-hiragana conversion will be partial.")
        return katakana_to_hiragana(text)
    to_hiragana = to_hiragana_fallback
else:
    def to_hiragana(text: str) -> str:
        return kanji_conv.to_hiragana(text)

def clean_last_string(text: str) -> str:
    """Remove parentheses only (内容は残す)."""
    return text.replace("(", "").replace(")", "")

print("Processing Mozc dictionary files...")
for file in dictionary_files:
    try:
        with open(file, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    first_strings_set.add(parts[0])
                    last_strings_set.add(parts[-1])
    except FileNotFoundError:
        print(f"Warning: Mozc dictionary file not found, skipping: {file}")


# ───────── suffix.txt ──────────
suffix_set = set()
if os.path.exists(suffix_file):
    with open(suffix_file, encoding="utf-8") as f:
        suffix_set.update({line.strip() for line in f if line.strip()})
print(f"Loaded {len(suffix_set)} suffixes.")

# ───────── ユーティリティ ──────────
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
    
    print("-" * 20)
    print(f"Processing {input_file}...")
    print("-" * 20)

    with open(input_file, encoding="utf-8") as f:
        for i, line in enumerate(f):
            original_line = line.strip()
            parts = original_line.split("\t")
            
            # ルール1: 列数が不足
            if len(parts) < 5:
                # print(f"[Line {i+1} EXCLUDED] Invalid format (less than 5 columns): {original_line}")
                continue

            first_str = parts[0]
            last_str  = clean_last_string(parts[-1]) if clean_last else parts[-1]

            # ★★★ 新しい除外ルール ★★★
            # 個別の除外リストに一致するかチェック
            is_specifically_excluded = False
            if input_file in specific_exclusions:
                for excluded_entry, excluded_reading in specific_exclusions[input_file]:
                    if first_str == excluded_entry and last_str == excluded_reading:
                        print(f"[Line {i+1} EXCLUDED] Specific exclusion rule: {first_str} -> {last_str}")
                        is_specifically_excluded = True
                        break
            if is_specifically_excluded:
                continue
            # ★★★★★★★★★★★★★★★★★

            # ルール2: 長すぎる見出し語
            if skip_long_entries and len(first_str) > 16:
                print(f"[Line {i+1} EXCLUDED] Entry too long (>16): {first_str}")
                continue

            # ルール3: 読み仮名にのみ記号
            if re.search(r'[^\wぁ-んァ-ン一-龥]', last_str) and not re.search(r'[^\wぁ-んァ-ン一-龥]', first_str):
                print(f"[Line {i+1} EXCLUDED] Symbol in reading only: {first_str} -> {last_str}")
                continue
            
            # ルール4: 「ん」で始まる
            if first_str.startswith("ん"):
                print(f"[Line {i+1} EXCLUDED] Starts with 'ん': {first_str}")
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            first_str_cleaned = first_str.replace("・", "").strip()
            last_str_hira     = katakana_to_hiragana(last_str).strip()

            # ルール5: 読みに特定の記号
            if extra_filter and any(c in last_str for c in "・！？"):
                print(f"[Line {i+1} EXCLUDED] Invalid char in reading: {first_str} -> {last_str}")
                continue

            kana_set_first = extract_kana(to_hiragana(first_str_cleaned))
            kana_set_last  = extract_kana(last_str_hira)

            if require_filter:
                # ルール6: 見出し語と読みが同一で、かつ既存辞書にある
                if first_str_cleaned == last_str_hira:
                    if first_str in first_strings_set:
                        print(f"[Line {i+1} EXCLUDED] Already in Mozc (entry==reading): {first_str}")
                        continue
                
                # ルール7: 読みが不適切
                if kana_set_last - kana_set_first:
                    print(f"[Line {i+1} EXCLUDED] Possibly incorrect reading: {first_str} -> {last_str}")
                    not_same_lines.append(original_line)
                    continue

                # ルール8: 「読み」が既存辞書に存在する
                if last_str in last_strings_set:
                    print(f"[Line {i+1} EXCLUDED] Reading already in Mozc: {first_str} -> {last_str}")
                    continue

            filtered_lines.append(original_line)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(filtered_lines) + "\n")

    if not_same_lines:
        with open(not_same_output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(not_same_lines) + "\n")

    print(f"\nFiltered output saved to {output_file}")
    if not_same_lines:
        print(f"Potentially incorrect readings saved to {not_same_output_file}")

# ───────── 個別フィルタ実行 ──────────
# (この部分は変更ありません)
if os.path.exists(place_file):
    filter_file(place_file, place_output_file, place_output_file_not_same, clean_last=True)
if os.path.exists(names_file):
    filter_file(names_file, names_output_file, names_output_file_not_same)
if os.path.exists(wiki_file):
    filter_file(
        wiki_file, wiki_output_file, wiki_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True
    )
if os.path.exists(neologd_file):
    filter_file(
        neologd_file, neologd_output_file, neologd_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True
    )

# ───────── Wiki vs NEologd 比較 (全面的に刷新) ──────────
def load_data_for_comparison(path: str) -> dict[tuple[str, str], str]:
    """
    フィルタリング済みファイルを読み込み、比較用のキーを持つ辞書を返す。
    キーは (見出し語, 読み) のタプル。
    キーの各要素は、比較前に空白を除去し正規化することで、比較の正確性を担保する。
    """
    data = {}
    if not os.path.exists(path):
        print(f"Comparison source file not found: {path}")
        return data
        
    with open(path, encoding="utf-8") as f:
        for line in f:
            original_line = line.rstrip("\n")
            parts = original_line.split("\t")
            
            if len(parts) < 2:
                continue

            # 見出し語と読みを抽出して、前後の空白を完全に除去する（正規化）
            entry_word = parts[0].strip()
            reading = parts[-1].strip()
            
            # 読みから括弧を除去（正規化）
            reading = reading.replace("(", "").replace(")", "")

            # 正規化されたキーを作成
            key = (entry_word, reading)
            data[key] = original_line
            
    return data

def write_data(path: str, data: dict, keys: set[tuple[str, str]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        # 結果をソートして書き込む
        for k in sorted(list(keys)):
            f.write(f"{data[k]}\n")

if all(os.path.exists(p) for p in (wiki_output_file, neologd_output_file)):
    print("\n" + "="*20 + " Starting Comparison " + "="*20)
    
    # 新しい、堅牢な読み込み関数を使用
    wiki_data    = load_data_for_comparison(wiki_output_file)
    neologd_data = load_data_for_comparison(neologd_output_file)

    wiki_keys    = set(wiki_data.keys())
    neologd_keys = set(neologd_data.keys())

    # 正確なキーで集合演算を実行
    common_keys       = wiki_keys & neologd_keys
    only_wiki_keys    = wiki_keys - neologd_keys
    only_neologd_keys = neologd_keys - wiki_keys

    # 結果を書き出し
    write_data("wiki_neologd_common.txt", wiki_data, common_keys)
    write_data("only_wiki.txt",           wiki_data, only_wiki_keys)
    write_data("only_neologd.txt",        neologd_data, only_neologd_keys)

    print("Comparison files generated successfully.")
    print(f" - Common words: {len(common_keys)}")
    print(f" - Words only in Wiki: {len(only_wiki_keys)}")
    print(f" - Words only in NEologd: {len(only_neologd_keys)}")
else:
    print("Skipping comparison (wiki / neologd output missing).")

print("\nScript finished.")
