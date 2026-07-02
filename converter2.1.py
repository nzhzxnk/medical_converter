import json
import re
import csv
import os
from datetime import datetime, timedelta

# ==========================================
# 基準日の設定
# ==========================================
BASE_YEAR = 2026
REFERENCE_DATE = datetime(2026, 2, 27)  # 受診日
EVENT_DATE = datetime(2026, 2, 10)      # 手術日（第1病日）
PATIENT_BIRTH_YEAR = 1988               # 38歳基準の生年

# ==========================================
# 前処理関数
# ==========================================
def normalize_text(text):
    if not text:
        return ""
    # 全角記号・スペースを半角にし、無駄な空白を削除
    text = text.replace("＋", "+").replace("ー", "-").replace("−", "-").replace(" ", " ")
    text = re.sub(r'\s+', '', text)
    return text

# ==========================================
# メインの抽出・変換処理
# ==========================================
def process_text_ordered(text):
    text = normalize_text(text)
    
    # 計算の基準となる年を記憶しておくための場所
    state = {
        "last_year": BASE_YEAR
    }
    
    ordered_results = []

    # 【重要】カルテから見つけ出したい時間表現の「ルール」をすべてリストアップ
    patterns = [
        r"20\d{2}年(?:\d+月)?(?:\d+日)?",                   # 例: 2025年, 2026年2月10日
        r"X[+-]?\d*年(?:\d+月)?(?:\d+日)?",                 # 例: X年, X+1年, X-1年9月
        r"(?:同年|翌年)(?:\d+月)?(?:\d+日)?",               # 例: 同年, 翌年3月
        r"(?<!\d)\d+歳(?:時)?",                             # 例: 38歳, 49歳時
        r"(?:第)?\d+病日",                                  # 例: 第2病日, 11病日 (第がなくてもOKに修正)
        r"(?<!\d)\d+年\d+(?:カ月|ヶ月|か月)(?:前|後)",      # 例: 1年2か月前
        r"(?<!\d)\d+(?:日|週間|カ月|ヶ月|か月|年)(?:前|後)",# 例: 3週間前, 1年前, 4日後
    ]
    
    # すべてのルールを合体させて、左から右へ一気に探せるようにする
    combined_pattern = "|".join(f"({p})" for p in patterns)

    # 見つかった表現を、それぞれどう西暦に直すかの変換ロジック
    def replacer(match):
        original = match.group(0)
        result = original  # 初期値（計算できないものはそのまま）

        # 1. 既に西暦のもの（そのまま抽出）
        if re.match(r"^20\d{2}年", original):
            state["last_year"] = int(original[:4]) # 同年のための記憶を更新
            result = original

        # 2. X年 / X+1年
        elif original.startswith("X"):
            m = re.match(r"X([+-]\d+)?年(?:(\d+)月)?(?:(\d+)日)?", original)
            if m:
                offset_str = m.group(1)
                offset = int(offset_str) if offset_str is not None else 0
                calc_year = BASE_YEAR + offset
                state["last_year"] = calc_year # 同年のための記憶を更新
                
                month, day = m.group(2), m.group(3)
                result = f"{calc_year}年"
                if month: result += f"{month}月"
                if day: result += f"{day}日"

        # 3. 同年 / 翌年
        elif original.startswith("同年") or original.startswith("翌年"):
            m = re.match(r"(同年|翌年)(?:(\d+)月)?(?:(\d+)日)?", original)
            if m:
                is_next = "翌" in m.group(1)
                calc_year = state["last_year"] + (1 if is_next else 0)
                
                month, day = m.group(2), m.group(3)
                result = f"{calc_year}年"
                if month: result += f"{month}月"
                if day: result += f"{day}日"

        # 4. 年齢（〇歳時）
        elif "歳" in original:
            m = re.search(r"(\d+)歳", original)
            if m:
                age = int(m.group(1))
                calc_year = PATIENT_BIRTH_YEAR + age
                result = f"{calc_year}年"
                state["last_year"] = calc_year

        # 5. 病日（第〇病日 / 〇病日）
        elif "病日" in original:
            m = re.search(r"(\d+)病日", original)
            if m:
                days = int(m.group(1))
                calc_date = EVENT_DATE + timedelta(days=days - 1)
                result = calc_date.strftime("%Y年%m月%d日")

        # 6. 1年2か月前 などの複合
        elif "年" in original and ("前" in original or "後" in original) and "月" in original:
            m = re.search(r"(\d+)年(\d+)(?:カ月|ヶ月|か月)(前|後)", original)
            if m:
                y = int(m.group(1))
                m_num = int(m.group(2))
                direction = m.group(3)
                sign = -1 if direction == "前" else 1
                
                # 簡易計算 (1年=365日, 1ヶ月=30日)
                total_days = (y * 365 + m_num * 30) * sign
                calc_date = REFERENCE_DATE + timedelta(days=total_days)
                result = calc_date.strftime("%Y年%m月")

        # 7. 単純な 〇週間前、〇年前 など
        elif "前" in original or "後" in original:
            m = re.search(r"(\d+)(日|週間|カ月|ヶ月|か月|年)(前|後)", original)
            if m:
                num = int(m.group(1))
                unit = m.group(2)
                direction = m.group(3)
                sign = -1 if direction == "前" else 1
                
                if unit == "日":
                    calc_date = REFERENCE_DATE + timedelta(days=num * sign)
                    result = calc_date.strftime("%Y年%m月%d日")
                elif unit == "週間":
                    calc_date = REFERENCE_DATE + timedelta(weeks=num * sign)
                    result = calc_date.strftime("%Y年%m月%d日")
                elif unit in ["カ月", "ヶ月", "か月"]:
                    calc_date = REFERENCE_DATE + timedelta(days=num * 30 * sign)
                    result = calc_date.strftime("%Y年%m月")
                elif unit == "年":
                    calc_year = BASE_YEAR + (num * sign)
                    result = f"{calc_year}年"

        # 見つけた結果をリストに記録
        ordered_results.append((original, result))
        return result

    # カルテ文章を左から右へ一気に処理
    converted_text = re.sub(combined_pattern, replacer, text)

    # 抽出結果の重複をなくす
    unique_results = []
    seen = set()
    for orig, conv in ordered_results:
        if orig not in seen:
            unique_results.append((orig, conv))
            seen.add(orig)

    return unique_results, text, converted_text

# ==========================================
# ファイル入出力
# ==========================================
def main():
    output_dir = "test_result2.1"
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open('test_case.json', 'r', encoding='utf-8') as f:
            cases = json.load(f)
    except FileNotFoundError:
        print("エラー: test_case.json が見つかりません。")
        return

    for case in cases:
        case_id = case.get('id', 'unknown')
        ordered_results, original_text, converted_text = process_text_ordered(case.get('text', ''))
        
        filename = os.path.join(output_dir, f"result2.1_{case_id}.csv")
        
        # Excelの文字化けを防ぐため utf-8-sig を使用
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['抽出された時間表現', '修正した時間表現'])
            for orig, conv in ordered_results:
                writer.writerow([orig, conv])
                
        print(f"{case_id} の処理完了。抽出数: {len(ordered_results)}件")

if __name__ == "__main__":
    main()