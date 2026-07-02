import json
import re
import csv
import os
from datetime import datetime, timedelta

# 年齢からの逆算機能の追加:

# 受診時の年齢を基準（現在は38歳に設定）とし、「〇歳時」という表現から逆算して「西暦〇年(当時〇歳)」に書き換えるようにしました。

# 不要なスペースや全角文字の正規化:

# カルテ特有の「全角の＋やー」「全角スペース」を半角に統一し、「X + 1 月」のような無駄な隙間を詰めてから検索する処理を追加しました。

# 単独の「X月」「Y日」等への対応:

# 「X月Y日」のセットだけでなく、「X月」「X+1月」「Y日」「X日」などが単独で記載されていても、受診日を基準に計算・変換できるようにしました。

# 「〇年前」「〇週前」の計算式の追加:

# 抽出はできていたものの計算ルールが抜けていた「年前」「週前」の計算式を補完し、「25年前」なども正常に西暦に変換されるように直しました。

# 「〇ヶ月後」などの相対表現について:

# 起点が受診日なのか治療開始日なのか文脈でしか判断できないため、プログラムによる誤変換（医療ミス）を防ぐ目的で、今回はあえて検索・変換の対象から外しています。

# ==========================================
# 基準日の設定
# ==========================================
BASE_YEAR = 2026
REFERENCE_DATE = datetime(2026, 2, 27)
EVENT_DATE = datetime(2026, 2, 10)
BASE_AGE = 38
# ==========================================

def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31, 29 if year%4==0 and not year%100==0 or year%400==0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime(year, month, day)

def calculate_converted_string(match_str):
    converted = match_str

    # 年齢の逆算（西暦のみを返すように修正）
    def calc_age(m):
        age = int(m.group(1))
        target_year = BASE_YEAR - (BASE_AGE - age)
        return f"{target_year}年"
    converted = re.sub(r'([0-9]+)\s*歳(?:代|時)?', calc_age, converted)

    def calc_xy(m):
        m_diff = m.group(1)
        d_diff = m.group(2)
        add_m = int(re.sub(r'[\s+]', '', m_diff)) if m_diff else 0
        add_d = int(re.sub(r'[\s+]', '', d_diff)) if d_diff else 0
        target = add_months(REFERENCE_DATE, add_m)
        target += timedelta(days=add_d)
        return target.strftime("%Y年%m月%d日")
    converted = re.sub(r'X\s*([+-]\s*[0-9]+)?\s*月\s*Y\s*([+-]\s*[0-9]+)?\s*日', calc_xy, converted)

    def calc_x_month(m):
        m_diff = m.group(1)
        add_m = int(re.sub(r'[\s+]', '', m_diff)) if m_diff else 0
        return add_months(REFERENCE_DATE, add_m).strftime("%Y年%m月")
    converted = re.sub(r'X\s*([+-]\s*[0-9]+)?\s*月(?!\s*Y)', calc_x_month, converted)

    def calc_xy_day(m):
        d_diff = m.group(1)
        add_d = int(re.sub(r'[\s+]', '', d_diff)) if d_diff else 0
        return (REFERENCE_DATE + timedelta(days=add_d)).strftime("%Y年%m月%d日")
    converted = re.sub(r'[XY]\s*([+-]\s*[0-9]+)?\s*日', calc_xy_day, converted)

    converted = re.sub(r'([0-9]+)\s*年(?:ほど)?前', lambda m: str(REFERENCE_DATE.year - int(m.group(1))) + "年", converted)
    converted = re.sub(r'([0-9]+)\s*ヶ月(?:ほど)?前', lambda m: add_months(REFERENCE_DATE, -int(m.group(1))).strftime("%Y年%m月"), converted)
    converted = re.sub(r'([0-9]+)\s*週(?:ほど)?前', lambda m: (REFERENCE_DATE - timedelta(days=int(m.group(1))*7)).strftime("%Y年%m月%d日"), converted)
    converted = re.sub(r'([0-9]+)\s*日(?:ほど)?前', lambda m: (REFERENCE_DATE - timedelta(days=int(m.group(1)))).strftime("%Y年%m月%d日"), converted)

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
    text = raw_text.translate(str.maketrans('０１２３４５６７８９＋−ー　', '0123456789+-- '))
    text = re.sub(r'[かカヵ]月', 'ヶ月', text)
    
    pattern_str = r'(昭和[0-9]+年|平成[0-9]+年|令和[0-9]+年|[RHS][0-9]+年|[0-9]{4}年(?:\s*[0-9]+\s*月(?:\s*[0-9]+\s*日)?)?|[0-9]{2,4}年度?|X\s*[-+]?\\s*[0-9]*\\s*年(?:\s*[A-Za-z0-9+-]+\s*月(?:\s*[A-Za-z0-9+-]+\s*日)?)?|X\s*(?:[+-]\s*[0-9]+)?\s*月\s*Y\s*(?:[+-]\s*[0-9]+)?\s*日|X\s*(?:[+-]\s*[0-9]+)?\s*月(?!\s*Y)|[XY]\s*(?:[+-]\s*[0-9]+)?\s*日|[0-9]+\s*(?:年|ヶ月|週|日)(?:ほど)?前(?:より)?|第[0-9]+病日|[Dd]ay\s*[0-9]+|術後\s*[0-9]+\s*(?:年|ヶ月|日)(?:目)?|[0-9]+\s*歳(?:代|時)?|[0-9]+\s*代(?:前半|後半)?)'
    
    matches = list(re.finditer(pattern_str, text))
    
    ordered_results = []
    for m in matches:
        original_expr = m.group(0)
        converted_expr = calculate_converted_string(original_expr)
        ordered_results.append((original_expr, converted_expr))

    unique_matches = list(set([m.group(0) for m in matches]))
    unique_matches.sort(key=len, reverse=True)
    
    converted_text = text
    for match in unique_matches:
        replacement = calculate_converted_string(match)
        converted_text = converted_text.replace(match, replacement)

    return ordered_results, text, converted_text

def main():
    output_dir = "training_result2.1"
    os.makedirs(output_dir, exist_ok=True)

    with open('training_case.json', 'r', encoding='utf-8') as f:
        cases = json.load(f)

    for case in cases:
        case_id = case['id']
        ordered_results, original_text, converted_text = process_text_ordered(case['text'])
        
        filename = os.path.join(output_dir, f"result2.1_{case_id}.csv")
        
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['抽出された時間表現', '修正した時間表現'])
            for orig, conv in ordered_results:
                writer.writerow([orig, conv])
            
            # writer.writerow([])
            # writer.writerow(['【元のテキスト】'])
            # writer.writerow([case['text']])
            # writer.writerow([])
            # writer.writerow(['【変換後のテキスト】'])
            # writer.writerow([converted_text])
            
    print(f"処理完了。{output_dir}フォルダを確認してください。")

if __name__ == "__main__":
    main()
