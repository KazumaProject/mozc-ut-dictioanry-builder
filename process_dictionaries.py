#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_dictionaries.py
────────────────────────────────────────────────────────────────────────────
・Mozc に未収録なら「表記＝読み」のエントリも許可  
・排他条件 skip_identical をパラメータ化  
・SudachiPy で品詞ごとに読みを取得して精度向上  
────────────────────────────────────────────────────────────────────────────
必要ライブラリ
    pip install kanjiconv sudachipy sudachidict_full
"""

import os
import glob
import re
from typing import List, Set, Tuple, Dict

from kanjiconv import KanjiConv, SudachiDictType
from sudachipy import dictionary, config


# ─────────────────────────
#  0. パス定義
# ─────────────────────────
MOZC_DIR = "./mozc"
DIC_DIR = "./dic"

place_file     = os.path.join(DIC_DIR, "place.txt")
names_file     = os.path.join(DIC_DIR, "names.txt")
wiki_file      = os.path.join(DIC_DIR, "wiki.txt")
neologd_file   = os.path.join(DIC_DIR, "neologd.txt")

place_output_file           = "./filtered_place.txt"
names_output_file           = "./filtered_names.txt"
wiki_output_file            = "./filtered_wiki.txt"
neologd_output_file         = "./filtered_neologd.txt"

place_output_file_not_same  = "./filtered_place_not_same.txt"
names_output_file_not_same  = "./filtered_names_not_same.txt"
wiki_output_file_not_same   = "./filtered_wiki_not_same.txt"
neologd_output_file_not_same= "./filtered_neologd_not_same.txt"

suffix_file = os.path.join(MOZC_DIR, "suffix.txt")


# ─────────────────────────
#  1. Mozc 標準辞書を読み込み
# ─────────────────────────
dictionary_files = sorted(glob.glob(os.path.join(MOZC_DIR, "dictionary0[0-9].txt")))

first_strings_set: Set[str] = set()
last_strings_set:  Set[str] = set()

print("Loading Mozc core dictionaries...")
for file in dictionary_files:
    with open(file, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                first_strings_set.add(parts[0])
                last_strings_set.add(parts[-1])

# suffix
suffix_set: Set[str] = set()
if os.path.exists(suffix_file):
    with open(suffix_file, encoding="utf-8") as f:
        for line in f:
            suffix = line.strip()
            if suffix:
                suffix_set.add(suffix)
print(f"→ suffix.txt: {len(suffix_set)} 行\n")


# ─────────────────────────
#  2. ユーティリティ
# ─────────────────────────
# KanjiConv (fallback) と SudachiPy の併用で読み仮名を生成
kanji_conv = KanjiConv(sudachi_dict_type=SudachiDictType.FULL.value, separator="")
sudachi_tokenizer = dictionary.Dictionary(config.Config.from_json("""{}""")).create()

KATA2HIRA_TABLE = str.maketrans(
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
    "ァィゥェォッャュョー",
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "ぁぃぅぇぉっゃゅょー"
)

def katakana_to_hiragana(text: str) -> str:
    return text.translate(KATA2HIRA_TABLE).replace("・", "")

def reading_with_sudachi(text: str) -> str:
    """品詞ごとに SudachiPy で読みを取得し、ひらがなに整形"""
    tokens = sudachi_tokenizer.tokenize(text)
    readings: List[str] = []
    for t in tokens:
        r = t.reading_form()
        if r == "*" or not r:              # 読みが取れない場合は表層形
            r = t.surface()
        readings.append(katakana_to_hiragana(r))
    return "".join(readings)

def extract_kana_set(text: str) -> Set[str]:
    """文字列中の仮名を集合で取得"""
    return set(re.findall(r"[ぁ-んァ-ヶー]", text))

symbol_pattern = re.compile(r"[^\wぁ-んァ-ン一-龥]")


# ─────────────────────────
#  3. フィルタ処理
# ─────────────────────────
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
    skip_identical: bool = True,
) -> None:
    """
    Mozc 拡張辞書をフィルタリングして精度を高める
    """
    filtered_lines: List[str]   = []
    not_same_lines: List[str]   = []

    if not os.path.exists(input_file):
        print(f"[SKIP] {input_file} が見つかりません")
        return

    print(f"— {os.path.basename(input_file)} を処理中 —")

    with open(input_file, encoding="utf-8") as f:
        for raw in f:
            parts = raw.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue

            first_str = parts[0]
            last_str  = parts[-1].replace("(", "").replace(")", "") if clean_last else parts[-1]

            if skip_long_entries and len(first_str) > 16:
                continue

            # 読み⇔表記で記号の有無が異なるものを除外
            if symbol_pattern.search(last_str) and not symbol_pattern.search(first_str):
                continue

            # 先頭が「ん」は極めて稀 → 除外
            if first_str.startswith("ん"):
                continue

            if remove_exclamation:
                last_str = last_str.replace("!", "")

            # 表記を正規化
            first_str_clean = first_str.replace("・", "")

            # 読みをひらがなに整形
            last_str_hira   = katakana_to_hiragana(last_str)

            # wiki / neologd 用の追加フィルタ
            if extra_filter and any(ch in last_str for ch in "・！？"):
                continue

            # Sudachi で表記の読みを取得
            first_reading_hira = reading_with_sudachi(first_str_clean)

            # identical 判定
            if skip_identical and first_reading_hira == last_str_hira:
                # Mozc 本体に既に入っていればスキップ
                if first_str_clean in first_strings_set:
                    continue     # Mozc 重複
            # require_filter 時は読みが完全一致していたらスキップ
            elif require_filter and first_reading_hira == last_str_hira:
                continue

            # 読みの不整合チェック
            kana_set_first = extract_kana_set(first_reading_hira)
            kana_set_last  = extract_kana_set(last_str_hira)

            if require_filter:
                if kana_set_last - kana_set_first:
                    not_same_lines.append(raw.rstrip("\n"))
                    continue
                else:
                    # Mozc 未登録の読みだけ保持
                    if last_str not in last_strings_set:
                        filtered_lines.append(raw.rstrip("\n"))
            else:
                filtered_lines.append(raw.rstrip("\n"))

    # 出力
    if filtered_lines:
        with open(output_file, "w", encoding="utf-8") as wf:
            wf.write("\n".join(filtered_lines) + "\n")
    if not_same_lines:
        with open(not_same_output_file, "w", encoding="utf-8") as wf:
            wf.write("\n".join(not_same_lines) + "\n")

    print(f"  ✓ {len(filtered_lines):>6} 行 → {output_file}")
    if not_same_lines:
        print(f"  ⚠ {len(not_same_lines):>6} 行 → {not_same_output_file}")
    print("")


# ─────────────────────────
#  4. 実行
# ─────────────────────────
def main() -> None:
    # place / names
    filter_file(
        place_file, place_output_file, place_output_file_not_same,
        clean_last=True
    )
    filter_file(
        names_file, names_output_file, names_output_file_not_same
    )

    # wiki / neologd – identical を許可して未知語も収集
    filter_file(
        wiki_file,  wiki_output_file,  wiki_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True,
        skip_identical=False,
    )
    filter_file(
        neologd_file, neologd_output_file, neologd_output_file_not_same,
        remove_exclamation=True, extra_filter=True,
        require_filter=True, skip_long_entries=True,
        skip_identical=False,
    )

    # ─── wiki と neologd の比較 ───
    if os.path.exists(wiki_output_file) and os.path.exists(neologd_output_file):
        compare_filtered_dicts(
            wiki_output_file, neologd_output_file,
            "wiki_neologd_common.txt", "only_wiki.txt", "only_neologd.txt"
        )

    print("All done.")


# ─────────────────────────
#  5. 比較ユーティリティ
# ─────────────────────────
def load_dict(path: str) -> Dict[Tuple[str, str], str]:
    d: Dict[Tuple[str, str], str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2:
                d[(p[0], p[-1])] = line.rstrip("\n")
    return d

def write_subset(path: str, data: Dict[Tuple[str, str], str], keys: Set[Tuple[str, str]]):
    with open(path, "w", encoding="utf-8") as f:
        for k in sorted(keys):
            f.write(f"{data[k]}\n")

def compare_filtered_dicts(wiki_path: str, neo_path: str,
                           common_out: str, only_wiki_out: str, only_neo_out: str):
    print("Comparing wiki vs neologd ...")
    wiki_d = load_dict(wiki_path)
    neo_d  = load_dict(neo_path)

    common_keys = wiki_d.keys() & neo_d.keys()
    only_wiki   = wiki_d.keys() - neo_d.keys()
    only_neo    = neo_d.keys() - wiki_d.keys()

    write_subset(common_out, wiki_d, common_keys)
    write_subset(only_wiki_out, wiki_d, only_wiki)
    write_subset(only_neo_out,  neo_d,  only_neo)

    print(f"  共通: {len(common_keys):>6} 行 → {common_out}")
    print(f"  wikiのみ: {len(only_wiki):>6} 行 → {only_wiki_out}")
    print(f"  neologdのみ: {len(only_neo):>6} 行 → {only_neo_out}\n")


if __name__ == "__main__":
    main()
