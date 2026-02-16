import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    print("🔍 正在爬取 DLRI (第一生命經濟研究所) - 🚀 雙引擎突破模式...")
    reports = []
    seen_urls = set()
    found_paths = []

    # ==========================================
    # 引擎 1：改良版 MarsFlag API 攔截 (偽裝通行證)
    # ==========================================
    api_url = "https://finder.api.mf.marsflag.com/api/v1/finder_service/documents/d3eff4d6/search"
    api_headers = HEADERS.copy()
    api_headers.update({
        'Accept': 'application/json',
        'Origin': 'https://www.dlri.co.jp',
        'Referer': 'https://www.dlri.co.jp/'
    })
    
    # MarsFlag API 通常需要特定的查詢參數，我們把常見的都帶上
    queries = ["経済", "市場", "金融", "日本"]
    for q in queries:
        try:
            resp = requests.get(api_url, params={'match': q, 'q': q}, headers=api_headers, timeout=5)
            # 清理跳脫字元後，直接暴力抓出所有報告網址的後半段
            text = resp.text.replace('\\/', '/')
            paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', text)
            found_paths.extend(paths)
        except:
            pass

    # ==========================================
    # 引擎 2：首頁 HTML 暴力掃描 (備用方案)
    # ==========================================
    try:
        # 就算 API 擋住我們，首頁通常也會掛上最新報告的連結
        top_resp = requests.get("https://www.dlri.co.jp/", headers=HEADERS, timeout=5)
        paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', top_resp.text)
        found_paths.extend(paths)
    except:
        pass

    # ==========================================
    # 總結處理：造訪每個找到的報告內頁提取資料
    # ==========================================
    # 剔除重複的連結
    unique_paths = set(found_paths)
    print(f"  [偵探回報] 總共搜集到 {len(unique_paths)} 個潛在報告連結，開始逐一檢驗內頁...")
    
    for path in unique_paths:
        url = urljoin("https://www.dlri.co.jp", path)
        if url in seen_urls: continue
        seen_urls.add(url)
        
        try:
            # 直接進去報告的專屬頁面
            detail_resp = requests.get(url, headers=HEADERS, timeout=5)
            detail_resp.encoding = 'utf-8'
            soup = BeautifulSoup(detail_resp.text, 'html.parser')
            
            # 1. 從 <title> 抓最乾淨的標題
            title_tag = soup.find('title')
            if not title_tag: continue
            title = title_tag.get_text(strip=True).split('|')[0].strip()
            
            # 排除非報告的網頁
            if len(title) < 5 or any(kw in title for kw in ["一覧", "List", "執筆者", "分野別"]): 
                continue
            
            # 2. 直接在整份原始碼裡面找日期 (最無腦但也最有效)
            date_text = None
            date_match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', detail_resp.text)
            if date_match:
                date_text = date_match.group(0)
                
            # 如果這篇報告沒有日期，或是超過 30 天，就立刻放棄
            if not date_text or not is_within_30_days(date_text):
                continue
                
            # 3. 找 PDF 下載連結
            pdf_tag = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
            if not pdf_tag:
                pdf_tag = soup.find('a', string=re.compile(r'PDF', re.IGNORECASE))
                
            final_pdf = urljoin(url, pdf_tag['href']) if (pdf_tag and pdf_tag.get('href')) else url
                
            reports.append({
                "Source": "DLRI", 
                "Date": date_text, 
                "Name": title, 
                "Link": final_pdf
            })
            time.sleep(0.3) # 禮貌性延遲，保護對方伺服器
        except:
            pass

    print(f"  ✅ DLRI 最終成功收錄 {len(reports)} 筆報告")
    return reports
