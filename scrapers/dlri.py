import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所) - 🚀 API 攔截模式...")
    # 破解法：直接向 MarsFlag API 的底層資料庫要資料！
    api_url = "https://finder.api.mf.marsflag.com/api/v1/finder_service/documents/d3eff4d6/search"
    
    # 丟幾個泛用關鍵字給 API，保證能把最新報告都挖出來
    queries = ["", "経済", "日本", "市場"]
    reports = []
    seen_urls = set()
    
    for q in queries:
        try:
            resp = requests.get(api_url, params={'q': q, 'limit': 30}, headers=HEADERS, timeout=10)
            
            # API 傳回的 JSON 裡面的網址可能會被跳脫 (\/)，先還原它
            text = resp.text.replace('\\/', '/')
            
            # 利用正規表達式，暴力抓取所有符合報告格式的網址 (無視未知的 JSON 結構)
            urls = re.findall(r'https?://www\.dlri\.co\.jp/report/[a-zA-Z0-9_/-]+\.html', text)
            
            for url in urls:
                if url in seen_urls: continue
                seen_urls.add(url)
                
                # 有了網址後，直接訪問該報告的「靜態專屬內頁」抓取標題和日期
                try:
                    detail_resp = requests.get(url, headers=HEADERS, timeout=5)
                    detail_resp.encoding = 'utf-8'
                    soup = BeautifulSoup(detail_resp.text, 'html.parser')
                    
                    # 1. 抓標題 (去除 "| 第一生命..." 後綴)
                    title_tag = soup.find('title')
                    if not title_tag: continue
                    title = title_tag.get_text(strip=True).split('|')[0].strip()
                    if len(title) < 5 or "一覧" in title: continue
                    
                    # 2. 抓日期
                    date_text = None
                    date_match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', detail_resp.text)
                    if date_match:
                        date_text = date_match.group(0)
                        
                    # 嚴格守門員：沒找到日期或超過30天，直接踢除
                    if not date_text or not is_within_30_days(date_text):
                        continue
                        
                    # 3. 抓 PDF 連結 (直接在內頁找，省去一次額外請求時間)
                    pdf_tag = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
                    if not pdf_tag:
                        pdf_tag = soup.find('a', string=re.compile(r'PDF', re.IGNORECASE))
                        
                    if pdf_tag and pdf_tag.get('href'):
                        final_pdf = urljoin(url, pdf_tag['href'])
                    else:
                        final_pdf = url
                        
                    reports.append({
                        "Source": "DLRI", 
                        "Date": date_text, 
                        "Name": title, 
                        "Link": final_pdf
                    })
                    time.sleep(0.3) # 禮貌性延遲
                except:
                    pass
        except Exception as e:
            print(f"  ❌ API 查詢失敗: {e}")
            
    print(f"  ✅ DLRI 找到 {len(reports)} 筆報告")
    return reports
