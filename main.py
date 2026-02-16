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

    # ==========================================
    # 🌟 新增：產生 NotebookLM 專用的 Markdown 檔案
    # ==========================================
    md_content = "# 📊 最新財經與總經分析報告總覽\n\n"
    md_content += "這是一份自動彙整的日本主要研究機構報告清單，請協助我掌握近期的宏觀經濟與金融市場趨勢。\n\n"
    
    for report in unique_reports:
        md_content += f"### {report['Name']}\n"
        md_content += f"- **發布機構**: {report['Source']}\n"
        md_content += f"- **發布日期**: {report['Date']}\n"
        md_content += f"- **報告連結**: {report['Link']}\n\n"
        
    with open('data/reports_for_notebooklm.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
        
    print(f"✅ 成功產出 NotebookLM 專用檔至 data/reports_for_notebooklm.md")
    print(f"{'='*60}")
    # ==========================================

# 這是整個程式的啟動點，必須放在最外層、最下面
if __name__ == "__main__":
    main()
