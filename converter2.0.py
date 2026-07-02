import json
import re
import csv
import os
from datetime import datetime, timedelta

# ==========================================
# 基準日の設定
# ==========================================
BASE_YEAR = 2026
REFERENCE_DATE = datetime(2026, 2, 27) # 受診日
EVENT_DATE = datetime(2026, 2, 10)     # 入院・手術日
# ==========================================

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31, 29 if year%4==0 and not year%100==0 or year%400==0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime(year, month, day)

def calculate_converted_string(match_str):
    converted = match_str

    def calc_xy(m):
        m_diff = m.group(1)
        d_diff = m.group(2)
        add_m = int(re.sub(r'[\s+]', '', m_diff)) if m_diff else 0
        add_d = int(re.sub(r'[\s+]', '', d_diff)) if d_diff else 0
        target = add_months(REFERENCE_DATE, add_m)
        target += timedelta(days=add_d)
        return target.strftime("%Y年%m月%d日")
    
    converted = re.sub(r'X([+-]\s*[0-9]+)?月Y\s*([+-]\s*[0-9]+)?日', calc_xy, converted)
    converted = re.sub(r'([0-9]+)日(?:ほど)?前', lambda m: (REFERENCE_DATE - timedelta(days=int(m.group(1)))).strftime("%Y年%m月%d日"), converted)
    converted = re.sub(r'([0-9]+)ヶ月(?:ほど)?前', lambda m: add_months(REFERENCE_DATE, -int(m.group(1))).strftime("%Y年%m月"), converted)

    def calc_post_op(m):
        num = int(m.group(1))
        unit = m.group(2)
        if unit == "年":
            return add_months(EVENT_DATE, num * 12).strftime("%Y年")
        elif unit == "ヶ月":
            return add_months(EVENT_DATE, num).strftime("%Y年%m月")
        elif unit == "日":
            return (EVENT_DATE + timedelta(days=num)).strftime("%Y年%m月%d日")
        return m.group(0)
    
    converted = re.sub(r'術後\s*([0-9]+)\s*(年|ヶ月|日)(?:目)?', calc_post_op, converted)
    converted = re.sub(r'第([0-9]+)病日', lambda m: (EVENT_DATE + timedelta(days=int(m.group(1))-1)).strftime("%Y年%m月%d日"), converted)
    converted = re.sub(r'[Dd]ay\s*([0-9]+)', lambda m: (EVENT_DATE + timedelta(days=int(m.group(1))-1)).strftime("%Y年%m月%d日"), converted)

    converted = re.sub(r'昭和([0-9]+)年', lambda m: str(1925 + int(m.group(1))) + "年", converted)
    converted = re.sub(r'平成([0-9]+)年', lambda m: str(1988 + int(m.group(1))) + "年", converted)
    converted = re.sub(r'令和([0-9]+)年', lambda m: str(2018 + int(m.group(1))) + "年", converted)
    converted = re.sub(r'[RＲ]([0-9]+)年', lambda m: str(2018 + int(m.group(1))) + "年", converted)
    converted = re.sub(r'[HＨ]([0-9]+)年', lambda m: str(1988 + int(m.group(1))) + "年", converted)
    converted = re.sub(r'X-([0-9]+)年', lambda m: str(BASE_YEAR - int(m.group(1))) + "年", converted)
    converted = re.sub(r'X\+([0-9]+)年', lambda m: str(BASE_YEAR + int(m.group(1))) + "年", converted)
    converted = re.sub(r'X年', str(BASE_YEAR) + "年", converted)

    return converted

def process_text_ordered(raw_text):
    text = raw_text.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    text = re.sub(r'[かカヵ]月', 'ヶ月', text)

    pattern_str = r'(昭和[0-9]+年|平成[0-9]+年|令和[0-9]+年|[RHS][0-9]+年|[0-9]{4}年(?:[0-9]+月(?:[0-9]+日)?)?|[0-9]{2,4}年度?|X[-+]?[0-9]*年(?:[A-Za-z0-9+-]+月(?:[A-Za-z0-9+-]+日)?)?|X(?:[+-]\s*[0-9]+)?月Y\s*(?:[+-]\s*[0-9]+)?日|[0-9]+(?:年|ヶ月|週|日)(?:ほど)?前(?:より)?|第[0-9]+病日|[Dd]ay\s*[0-9]+|術後[0-9]+(?:年|ヶ月|日)(?:目)?|[0-9]+歳(?:代|時)?|[0-9]+代(?:前半|後半)?)'
    
    # 文章の先頭から順番に見つけ出す
    matches = list(re.finditer(pattern_str, text))
    
    ordered_results = []
    for m in matches:
        original_expr = m.group(0)
        converted_expr = calculate_converted_string(original_expr)
        ordered_results.append((original_expr, converted_expr))

    # 文章全体の変換（意図しない書き換えを防ぐため、文字数が長いものから順に処理する）
    unique_matches = list(set([m.group(0) for m in matches]))
    unique_matches.sort(key=len, reverse=True)
    
    converted_text = text
    for match in unique_matches:
        replacement = calculate_converted_string(match)
        converted_text = converted_text.replace(match, replacement)

    return ordered_results, text, converted_text

def main():
    # 症例ごとのファイルをまとめるフォルダを作成
    output_dir = "training_result2.0"
    os.makedirs(output_dir, exist_ok=True)

    with open('training_case.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    for case in cases:
        case_id = case['id']
        ordered_results, original_text, converted_text = process_text_ordered(case['text'])
        
        # 症例IDごとにファイル名をつける
        filename = os.path.join(output_dir, f"result2.0_{case_id}.csv")
        
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            
            # 1. 時間表現を出現順に書き込む
            writer.writerow(['抽出された時間表現', '修正した時間表現'])
            for orig, conv in ordered_results:
                writer.writerow([orig, conv])
            
            # 2. 確認しやすいよう、少し間を空けて元の文章と変換後の文章も記録しておく
            # writer.writerow([])
            # writer.writerow(['【元のテキスト】'])
            # writer.writerow([case['text']])
            # writer.writerow([])
            # writer.writerow(['【変換後のテキスト】'])
            # writer.writerow([converted_text])
            
    print(f"処理が完了しました！ '{output_dir}' フォルダの中に、症例ごとのCSVファイルが作成されています。")

if __name__ == "__main__":
    main()
