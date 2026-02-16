import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link
import time

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所)...")
    base_url = "https://www.dlri.co.jp"
    # 改為抓取首頁與報告總覽頁，這兩個地方最新報告最齊全
    target_urls = [
        "https://www.dlri.co.jp/",
        "https://www.dlri.co.jp/report_index.html"
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
                
                # 1. 基本排除
                if len(title) < 5 or href in seen_hrefs: continue
                
                # 2. 限定必須是報告的網址 (包含 /report/ 且通常以 .html 結尾)
                if "/report/" not in href or not href.endswith('.html'): continue
                if any(kw in href for kw in ["report_index", "category", "type"]): continue
                if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ"]): continue
                
                # 3. 找日期：先從外層容器 (li, dl, tr, div) 找找看
                date_text = None
                parent = tag.find_parent(['li', 'dl', 'tr', 'div'])
                if parent:
                    match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', parent.get_text())
                    if match:
                        date_text = match.group(0)
                
                link = urljoin(base_url, href)
                
                # 4. 終極必殺技：如果在外面找不到日期，直接點進去內頁找！
                if not date_text:
                    try:
                        detail_resp = requests.get(link, headers=HEADERS, timeout=5)
                        detail_match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', detail_resp.text)
                        if detail_match:
                            date_text = detail_match.group(0)
                        time.sleep(0.3) # 禮貌性暫停，不要把人家網站打掛
                    except:
                        pass
                
                # 5. 如果連內頁都找不到日期，那就真的不是報告
                if not date_text: continue
                
                # 6. 超過 30 天就跳過
                if not is_within_30_days(date_text): continue

                seen_hrefs.add(href)
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
