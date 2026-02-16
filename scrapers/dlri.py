import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所)...")
    base_url = "https://www.dlri.co.jp"
    
    # 🌟 修正：這是 DLRI 真正的報告清單正確網址
    target_url = "https://www.dlri.co.jp/report_index.html"
    reports = []
    
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 抓取所有連結
        links = soup.find_all('a', href=True)
        seen_hrefs = set()
        
        for tag in links:
            href = tag['href']
            title = tag.get_text(strip=True)
            
            # 1. 排除太短或重複的連結
            if len(title) < 5 or href in seen_hrefs: continue
            
            # 2. 確保網址特徵是報告 (包含 /report/ 且以 .html 結尾)
            if "/report/" not in href or not href.endswith('.html'): continue
            if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ", "検索"]): continue
            
            # 3. 找日期 (DLRI 的日期格式通常為 2026.02.16)
            date_text = None
            parent = tag.find_parent()
            if parent:
                # 把標籤和它前後的文字合在一起找
                txt = parent.get_text()
                prev = parent.find_previous_sibling()
                if prev: txt += " " + prev.get_text()
                
                match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', txt)
                if match:
                    date_text = match.group(0)
            
            # 4. 找不到日期或超過30天就踢除
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
        print(f"  ❌ DLRI 失敗: {e}")
    
    print(f"  ✅ DLRI 找到 {len(reports)} 筆報告")
    return reports
