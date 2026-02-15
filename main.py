import json
import os
from scrapers import nli, jri, mizuho, dir_report, sony_fg

def main():
    print(f"\n{'='*60}")
    print("開始執行獨立模組化爬蟲...")
    print(f"{'='*60}\n")
    
    all_reports = []
    
    # 未來如果要新增網站，只要把模組加進這個 List 即可！
    scrapers = [nli, jri, mizuho, dir_report, sony_fg]
    
    for scraper in scrapers:
        try:
            results = scraper.scrape()
            all_reports.extend(results)
        except Exception as e:
            print(f"❌ 執行失敗: {e}")

    if not all_reports:
        print("\n❌ 未抓到任何資料")
        return

    # 去除重複報告（基於 Link）
    seen_links = set()
    unique_reports = []
    for report in all_reports:
        if report["Link"] not in seen_links:
            seen_links.add(report["Link"])
            unique_reports.append(report)
            
    print(f"\n{'='*60}")
    print(f"總共找到 {len(unique_reports)} 筆報告（已去重）")
    
    # 建立 data 資料夾並儲存為 JSON
    os.makedirs('data', exist_ok=True)
    with open('data/reports.json', 'w', encoding='utf-8') as f:
        json.dump(unique_reports, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 成功將 {len(unique_reports)} 筆資料儲存至 data/reports.json")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
