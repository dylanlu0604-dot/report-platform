import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所)...")
    base_url = "https://www.dlri.co.jp"
    target_url = "https://www.dlri.co.jp/report/"
    reports = []
    
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        links = soup.find_all('a', href=True)
        seen_hrefs = set()
        
        for tag in links:
            href = tag['href']
            title = tag.get_text(strip=True)
            
            # 1. 基本排除：字數太短或已經處理過的連結
            if len(title) < 5: continue
            if href in seen_hrefs: continue
            
            # 2. 限定必須是報告詳細頁面 (包含 /report/ 且結尾通常是 .html 或 .pdf)
            # 排除掉分類首頁 (例如以 / 結尾的導覽列)
            if "/report/" not in href: continue
            if href.endswith('/') or href.endswith('index.html'): continue
            
            # 排除非報告連結的雜訊文字
            if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ", "検索"]): continue
            
            # 3. 嚴格找日期：擴大範圍尋找附近的文字
            date_text = None
            parent = tag.find_parent()
            if parent:
                txt = parent.get_text()
                prev = parent.find_previous_sibling()
                if prev: 
                    txt += " " + prev.get_text()
                
                # 匹配精確格式：2026年02月16日 或 2026.02.16 或 2026/02/16
                match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}日?', txt)
                if match: 
                    date_text = match.group(0)

            # 4. 如果沒找到日期，直接判定不是報告，踢除！
            if not date_text: continue
            
            # 5. 超過 30 天就跳過
            if not is_within_30_days(date_text): continue

            # 加入清單並進入內部尋找 PDF 連結
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
