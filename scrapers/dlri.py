import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所)...")
    base_url = "https://www.dlri.co.jp"
    
    # 🌟 破解法：避開 JavaScript 動態載入的首頁，直接去抓這 7 個靜態分類清單！
    target_urls = [
        "https://www.dlri.co.jp/summary/type/trends.html",
        "https://www.dlri.co.jp/summary/type/indicators.html",
        "https://www.dlri.co.jp/summary/type/forecast.html",
        "https://www.dlri.co.jp/summary/type/market.html",
        "https://www.dlri.co.jp/summary/type/life_design.html",
        "https://www.dlri.co.jp/summary/type/dlri_report.html",
        "https://www.dlri.co.jp/summary/type/businessenvironment.html"
    ]
    
    reports = []
    seen_hrefs = set()
    
    for target_url in target_urls:
        try:
            resp = requests.get(target_url, headers=HEADERS, timeout=15)
            soup = BeautifulSoup(resp.content, 'html.parser')
            links = soup.find_all('a', href=True)
            
            for tag in links:
                href = tag['href']
                title = tag.get_text(strip=True)
                
                # 1. 排除太短或已經抓過的連結
                if len(title) < 5 or href in seen_hrefs: continue
                
                # 2. 確認是報告 (必須包含 /report/ )
                if "/report/" not in href: continue
                if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ", "検索"]): continue
                if href.endswith('/') or href.endswith('index.html'): continue
                
                # 3. 找日期
                date_text = None
                parent = tag.find_parent()
                if parent:
                    txt = parent.get_text()
                    prev = parent.find_previous_sibling()
                    if prev: txt += " " + prev.get_text()
                    
                    match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', txt)
                    if match:
                        date_text = match.group(0)
                
                # 4. 嚴格過濾：沒日期、或超過 30 天，立刻踢除
                if not date_text: continue
                if not is_within_30_days(date_text): continue
                
                # 5. 加入清單
                seen_hrefs.add(href)
                link = urljoin(base_url, href)
                final_pdf = fetch_real_pdf_link(link)
                
                reports.append({
                    "Source": "DLRI", 
                    "Date": date_text, 
                    "Name": title, 
                    "Link": final_pdf
                })
                
        except Exception as e:
            print(f"  ❌ DLRI ({target_url}) 失敗: {e}")
            
    print(f"  ✅ DLRI 找到 {len(reports)} 筆報告")
    return reports
