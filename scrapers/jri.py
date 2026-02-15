import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    print("🔍 正在爬取 JRI (Year List)...")
    base_url = "https://www.jri.co.jp"
    target_url = "https://www.jri.co.jp/report/year/"
    reports = []
    
    try:
        resp = requests.get(target_url, headers=HEADERS)
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        
        for tag in links:
            href = tag['href']
            title = tag.get_text(strip=True)
            
            if len(title) < 5 or "Column" in title or "column" in href.lower() or "一覧" in title or "List" in title or "#" in href or href.endswith('/'): continue
            if ("/report/" in href or "page.jsp?id=" in href) and title in ["経済分析・政策提言", "マクロ経済分析", "リサーチ・レポート"]: continue

            date_text = "未知日期"
            parent = tag.find_parent()
            if parent:
                txt = parent.get_text() + " " + (parent.find_previous_sibling().get_text() if parent.find_previous_sibling() else "")
                match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', txt)
                if match: date_text = match.group(0)
            
            if not is_within_30_days(date_text): continue

            link = urljoin(base_url, href)
            final_pdf = fetch_real_pdf_link(link)
            reports.append({"Source": "JRI", "Date": date_text, "Name": title, "Link": final_pdf})
                
    except Exception as e:
        print(f"  ❌ JRI 失敗: {e}")
    
    print(f"  ✅ JRI 找到 {len(reports)} 筆報告")
    return reports
