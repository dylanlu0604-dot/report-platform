from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, unquote
import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from scrapers.utils import is_within_30_days # 假設這是你原本的 utils

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲 (Playwright 動態渲染版)
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    seen_urls = set()
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    try:
        with sync_playwright() as p:
            # 啟動無頭瀏覽器
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print("  🌐 啟動 Playwright 載入動態網頁...")
            # 前往目標網頁，等待網路閒置 (確保 JS 載入且 API 回傳完畢)
            page.goto(target_url, wait_until="networkidle", timeout=30000)
            
            # 給予額外時間確保畫面上的報告列表已經渲染
            try:
                page.wait_for_selector('a', timeout=10000)
                time.sleep(3) 
            except PlaywrightTimeoutError:
                print("  ⚠️ 等待特定元素超時，嘗試直接解析當前頁面...")
            
            # 獲取渲染後的完整 HTML
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"  📄 渲染後頁面大小: {len(html_content):,} 字元")
            
            browser.close()

        # ==========================================
        # 策略 1: 廣域 PDF 搜尋 (沿用你原本的邏輯)
        # ==========================================
        print("  [策略 1] 廣域 PDF 搜尋...")
        
        pdf_urls_raw = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE)
        pdf_urls_raw.extend(re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE))
        pdf_urls_raw.extend(re.findall(r'(https?://[^\s<>"\']+\.pdf)', html_content, re.IGNORECASE))
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower():
                pdf_urls_raw.append(href)
        
        for elem in soup.find_all(attrs={'data-url': True}):
            url = elem.get('data-url', '')
            if '.pdf' in url.lower():
                pdf_urls_raw.append(url)
                
        for elem in soup.find_all(attrs={'data-href': True}):
            url = elem.get('data-href', '')
            if '.pdf' in url.lower():
                pdf_urls_raw.append(url)
        
        # 去重和清理
        pdf_urls = []
        for url in set(pdf_urls_raw):
            url = url.strip().strip('"').strip("'")
            if url and '.pdf' in url.lower():
                full_url = urljoin(base_url, url)
                if full_url not in seen_urls:
                    pdf_urls.append(full_url)
                    seen_urls.add(full_url)
        
        print(f"    找到 {len(pdf_urls)} 個 PDF URL")
        
        for pdf_url in pdf_urls:
            title, date_text = extract_info_from_url(pdf_url)
            
            if not title or not date_text:
                link = soup.find('a', href=lambda x: x and pdf_url in urljoin(base_url, x))
                if link:
                    if not title:
                        title = extract_title_from_link(link)
                    if not date_text:
                        date_text = extract_date_from_link(link)
            
            if not title or len(title) < 5:
                filename = unquote(pdf_url.split('/')[-1].replace('.pdf', '').replace('.PDF', ''))
                title = filename
            
            if not date_text:
                continue
            if not is_within_30_days(date_text):
                continue
                
            title = clean_title(title, date_text)
            
            reports.append({
                "Source": "CTBC",
                "Date": date_text,
                "Name": title,
                "Link": pdf_url
            })
            
        # ==========================================
        # 策略 2: 如果沒找到,搜尋所有可能的報告連結
        # ==========================================
        if len(reports) == 0:
            print("  [策略 2] 搜尋報告連結...")
            # (此處沿用你原本策略 2 與策略 3 的程式碼，直接複製貼上即可)
            # ...
            
    except Exception as e:
        print(f"  ❌ CTBC 爬取失敗: {e}")
        import traceback
        traceback.print_exc()

    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports

# 底下保留你原本寫好的 extract_info_from_url, extract_title_from_link, extract_date_from_link 等 def
# ...
