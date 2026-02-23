import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, unquote
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲 (超級靈活版)
    
    策略:
    1. 直接找 PDF 連結 (任何位置)
    2. 找所有可能是報告的連結
    3. 搜尋頁面中的 data 屬性和 JSON
    4. 檢查是否有 API 載入
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    seen_urls = set()
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    try:
        # 獲取頁面
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        print(f"  📄 頁面大小: {len(resp.text):,} 字元")
        
        # ==========================================
        # 策略 1: 超級寬鬆的 PDF 搜尋
        # ==========================================
        print("  [策略 1] 廣域 PDF 搜尋...")
        
        # 方法 A: 正則搜尋所有 PDF URL (包括 JavaScript 中的)
        pdf_urls_raw = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', resp.text, re.IGNORECASE)
        pdf_urls_raw.extend(re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', resp.text, re.IGNORECASE))
        pdf_urls_raw.extend(re.findall(r'(https?://[^\s<>"\']+\.pdf)', resp.text, re.IGNORECASE))
        
        # 方法 B: BeautifulSoup 找所有 <a> 標籤
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower():
                pdf_urls_raw.append(href)
        
        # 方法 C: 檢查 data 屬性
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
            # 清理 URL
            url = url.strip().strip('"').strip("'")
            if url and '.pdf' in url.lower():
                full_url = urljoin(base_url, url)
                if full_url not in seen_urls:
                    pdf_urls.append(full_url)
                    seen_urls.add(full_url)
        
        print(f"    找到 {len(pdf_urls)} 個 PDF URL")
        
        # 處理找到的 PDF
        for pdf_url in pdf_urls:
            # 嘗試從 URL 提取資訊
            title, date_text = extract_info_from_url(pdf_url)
            
            # 如果 URL 沒資訊,嘗試找對應的 <a> 標籤
            if not title or not date_text:
                link = soup.find('a', href=lambda x: x and pdf_url in urljoin(base_url, x))
                if link:
                    if not title:
                        title = extract_title_from_link(link)
                    if not date_text:
                        date_text = extract_date_from_link(link)
            
            # 如果還是沒標題,用檔名
            if not title or len(title) < 5:
                filename = unquote(pdf_url.split('/')[-1].replace('.pdf', '').replace('.PDF', ''))
                title = filename
            
            # 沒日期就跳過
            if not date_text:
                continue
            
            # 檢查 30 天內
            if not is_within_30_days(date_text):
                continue
            
            # 清理標題
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
            
            # 超級寬鬆的關鍵字
            keywords = [
                '報告', '評論', '分析', '市場', '展望', '觀點',
                'report', 'analysis', 'market', 'comment', 'review',
                '月報', '週報', '日報', '專題', '研究'
            ]
            
            report_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                # 排除明顯不相關的
                if any(exclude in href.lower() for exclude in ['javascript:', 'mailto:', '#']):
                    continue
                
                # 檢查是否包含關鍵字
                if any(kw in text or kw in href for kw in keywords):
                    full_url = urljoin(base_url, href)
                    if 'ctbcbank.com' in full_url and full_url not in seen_urls:
                        report_links.append((full_url, text))
                        seen_urls.add(full_url)
            
            print(f"    找到 {len(report_links)} 個可能的報告連結")
            
            # 訪問每個連結找 PDF
            for detail_url, preview_title in report_links[:30]:
                try:
                    detail_resp = requests.get(detail_url, headers=HEADERS, timeout=10)
                    detail_resp.encoding = 'utf-8'
                    detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                    
                    # 在詳情頁找 PDF
                    pdf_link = detail_soup.find('a', href=re.compile(r'\.pdf$', re.I))
                    
                    if not pdf_link:
                        # 嘗試找包含 PDF 的 JavaScript
                        pdf_urls_in_page = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', 
                                                       detail_resp.text, re.IGNORECASE)
                        if pdf_urls_in_page:
                            pdf_url = urljoin(detail_url, pdf_urls_in_page[0])
                        else:
                            continue
                    else:
                        pdf_url = urljoin(detail_url, pdf_link['href'])
                    
                    if pdf_url in seen_urls:
                        continue
                    seen_urls.add(pdf_url)
                    
                    # 標題
                    h1 = detail_soup.find('h1')
                    title = h1.get_text(strip=True) if h1 else preview_title
                    
                    # 日期
                    date_text = extract_date_from_text(detail_resp.text)
                    
                    if not date_text or not is_within_30_days(date_text):
                        continue
                    
                    title = clean_title(title, date_text)
                    
                    reports.append({
                        "Source": "CTBC",
                        "Date": date_text,
                        "Name": title,
                        "Link": pdf_url
                    })
                    
                    time.sleep(0.3)
                    
                except Exception:
                    continue
        
        # ==========================================
        # 策略 3: 檢查 JSON 或 data 屬性
        # ==========================================
        if len(reports) == 0:
            print("  [策略 3] 搜尋 JSON 資料...")
            
            # 在 script 標籤中找 JSON
            for script in soup.find_all('script'):
                if script.string:
                    # 尋找看起來像報告資料的 JSON
                    json_matches = re.findall(r'\{[^}]*(?:pdf|report|title|date)[^}]*\}', 
                                             script.string, re.IGNORECASE)
                    for json_str in json_matches:
                        try:
                            import json
                            data = json.loads(json_str)
                            # 嘗試提取 PDF URL
                            # 這裡可以根據實際 JSON 結構調整
                        except:
                            pass
        
    except Exception as e:
        print(f"  ❌ CTBC 爬取失敗: {e}")
        import traceback
        traceback.print_exc()
    
    # 如果完全沒找到,給出診斷建議
    if len(reports) == 0:
        print("\n  ⚠️  未找到任何報告,可能原因:")
        print("     1. 網站使用 JavaScript 動態載入 (需要 Selenium)")
        print("     2. 內容在 iframe 中")
        print("     3. 需要登入才能訪問")
        print("     4. 網站結構完全不同")
        print("\n  💡 建議:")
        print("     1. 手動訪問網站確認報告位置")
        print("     2. 使用瀏覽器開發者工具查看 Network 請求")
        print("     3. 運行診斷腳本: python diagnose_ctbc_live.py")
    
    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports


def extract_info_from_url(url):
    """從 URL 提取標題和日期"""
    title = None
    date_text = None
    
    # URL decode
    url_decoded = unquote(url)
    
    # 提取檔名
    filename = url_decoded.split('/')[-1].replace('.pdf', '').replace('.PDF', '')
    
    # 從檔名提取日期
    date_patterns = [
        r'20\d{2}年\d{1,2}月\d{1,2}日',
        r'20\d{2}[_-]\d{1,2}[_-]\d{1,2}',
        r'20\d{2}\d{2}\d{2}',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, filename)
        if match:
            date_text = match.group(0)
            # 標準化日期格式
            if len(date_text) == 8 and date_text.isdigit():
                date_text = f"{date_text[:4]}/{date_text[4:6]}/{date_text[6:8]}"
            break
    
    # 從檔名提取標題 (移除日期部分)
    if date_text:
        title = re.sub(r'20\d{2}[年_\-/]\d{1,2}[月_\-/]\d{1,2}[日]?', '', filename)
        title = re.sub(r'20\d{2}\d{2}\d{2}', '', title)
    else:
        title = filename
    
    return title, date_text


def extract_title_from_link(link):
    """從連結元素提取標題"""
    # 策略 1: 連結文字
    title = link.get_text(strip=True)
    
    # 策略 2: title 屬性
    if not title or len(title) < 5:
        title = link.get('title', '')
    
    # 策略 3: 父元素
    if not title or len(title) < 5:
        parent = link.find_parent(['li', 'div', 'td'])
        if parent:
            title = re.sub(r'\s+', ' ', parent.get_text(strip=True))
    
    return title


def extract_date_from_link(link):
    """從連結周圍提取日期"""
    date_text = None
    
    parent = link.find_parent(['li', 'div', 'tr', 'td', 'article'])
    if parent:
        search_text = parent.get_text()
    else:
        search_text = link.get_text()
    
    date_text = extract_date_from_text(search_text)
    return date_text


def extract_date_from_text(text):
    """從文字中提取日期"""
    date_patterns = [
        r'20\d{2}年\d{1,2}月\d{1,2}日',
        r'20\d{2}/\d{1,2}/\d{1,2}',
        r'20\d{2}\.\d{1,2}\.\d{1,2}',
        r'20\d{2}-\d{1,2}-\d{1,2}',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    
    return None


def clean_title(title, date_text):
    """清理標題"""
    # 移除日期
    title = re.sub(r'20\d{2}[年/.\-_]\d{1,2}[月/.\-_]\d{1,2}[日]?', '', title)
    
    # 移除 PDF 字樣
    title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\(PDF\)', '', title, flags=re.IGNORECASE)
    
    # 移除多餘空白和符號
    title = re.sub(r'[_\-]+', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    
    return title


if __name__ == "__main__":
    results = scrape()
    
    if results:
        print(f"\n📄 找到的報告:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['Date']}] {r['Name'][:60]}")
            print(f"   🔗 {r['Link']}")
