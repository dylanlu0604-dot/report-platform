import json
import os
import importlib
import pkgutil
import scrapers  # 引入整個 scrapers 資料夾

def main():
    print(f"\n{'='*60}")
    print("開始執行獨立模組化爬蟲 (自動偵測模式)...")
    print(f"{'='*60}\n")
    
    all_reports = []
    
    # 🌟 魔法在這裡：自動掃描 scrapers 資料夾下的所有 .py 檔案
    for _, module_name, _ in pkgutil.iter_modules(scrapers.__path__):
        
        # 排除 utils.py (因為它只是工具箱，不是爬蟲)
        if module_name == "utils":
            continue
            
        try:
            # 動態載入模組 (等同於 import scrapers.xxx)
            module = importlib.import_module(f"scrapers.{module_name}")
            
            # 確保這個檔案裡面有寫 scrape() 這個函數，才叫它工作
            if hasattr(module, "scrape"):
                results = module.scrape()
                if results:
                    all_reports.extend(results)
            else:
                print(f"⚠️ 略過 {module_name}.py (找不到 scrape 函數)")
                
        except Exception as e:
            print(f"❌ 載入或執行 {module_name} 失敗: {e}")

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
