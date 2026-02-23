import re
import time
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲 (增強版)
    
    改進:
    1. 增加重試機制處理網路錯誤
    2. 降級策略: Playwright失敗時使用requests
    3. 更好的錯誤處理
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    # 嘗試使用 Playwright (最多重試 3 次)
    html_content = None
    for attempt in range(3):
        try:
            html_content = scrape_with_playwright(target_url, attempt + 1)
            if html_content:
                break
        except Exception as e:
            print(f"  ⚠️ Playwright 嘗試 {attempt + 1}/3 失敗: {type(e).__name__}")
            if attempt < 2:
                time.sleep(5)  # 等待 5 秒後重試
    
    # 如果 Playwright 完全失敗,降級使用 requests
    if not html_content:
        print("  🔄 Playwright 失敗,降級使用 requests...")
        try:
            import requests
            resp = requests.get(target_url, headers=HEADERS, timeout=30)
            html_content = resp.text
            print(f"  ✓ requests 成功獲取頁面 ({len(html_content):,} 字元)")
        except Exception as e:
            print(f"  ❌ requests 也失敗: {e}")
            return reports
    
    # 解析 HTML
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        seen_urls = set()
        
        # 策略 1: 廣域 PDF 搜尋
        print("  [策略 1] 廣域 PDF 搜尋...")
        
        pdf_urls_raw = []
        
        # 方法 A: 正則搜尋
        pdf_urls_raw.extend(re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE))
        pdf_urls_raw.extend(re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE))
        pdf_urls_raw.extend(re.findall(r'(https?://[^\s<>"\']+\.pdf)', html_content, re.IGNORECASE))
        
        # CTBC 專屬的 API 格式
        pdf_urls_raw.extend(re.findall(r'(/IB/api/adapters/IB_Adapter/resource/report/[^"\']+)', html_content, re.IGNORECASE))
        
        # 方法 B: BeautifulSoup
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower() or '/resource/report/' in href.lower():
                pdf_urls_raw.append(href)
        
        # 方法 C: data 屬性
        for elem in soup.find_all(attrs={'data-url': True}):
            url = elem.get('data-url', '')
            if '.pdf' in url.lower() or '/resource/report/' in url.lower():
                pdf_urls_raw.append(url)
        
        for elem in soup.find_all(attrs={'data-href': True}):
            url = elem.get('data-href', '')
            if '.pdf' in url.lower() or '/resource/report/' in url.lower():
                pdf_urls_raw.append(url)
        
        # 去重和清理
        target_urls = []
        for url in set(pdf_urls_raw):
            url = url.strip().strip('"').strip("'")
            if url and ('.pdf' in url.lower() or '/resource/report/' in url.lower()):
                full_url = urljoin(base_url, url)
                if full_url not in seen_urls:
                    target_urls.append(full_url)
                    seen_urls.add(full_url)
        
        print(f"    找到 {len(target_urls)} 個目標 URL")
        
        # 處理每個 URL
        for target_url_item in target_urls:
            title, date_text = extract_info_from_url(target_url_item)
            
            # 如果 URL 沒資訊,嘗試從 HTML 提取
            if not title or not date_text:
                link = soup.find('a', href=lambda x: x and target_url_item in urljoin(base_url, x))
                
                if not link:
                    report_id = target_url_item.split('/')[-1]
                    link = soup.find(lambda tag: tag.name in ['a', 'div', 'li', 'td'] and report_id in str(tag))
                
                if link:
                    if not title:
                        title = extract_title_from_link(link)
                    if not date_text:
                        date_text = extract_date_from_link(link)
            
            # 如果還是沒標題,用檔名
            if not title or len(title) < 5:
                filename = unquote(target_url_item.split('/')[-1].replace('.pdf', '').replace('.PDF', ''))
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
                "Link": target_url_item
            })
        
        # 策略 2: 報告連結搜尋
        if len(reports) == 0:
            print("  [策略 2] 搜尋報告連結...")
            
            keywords = [
                '報告', '評論', '分析', '市場', '展望', '觀點',
                'report', 'analysis', 'market', 'comment', 'review'
            ]
            
            report_count = 0
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                
                if any(exclude in href.lower() for exclude in ['javascript:', 'mailto:', '#']):
                    continue
                
                if any(kw in text or kw in href for kw in keywords):
                    report_count += 1
            
            print(f"    找到 {report_count} 個可能的報告連結")
    
    except Exception as e:
        print(f"  ❌ HTML 解析失敗: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports


def scrape_with_playwright(url, attempt):
    """
    使用 Playwright 抓取頁面
    
    Args:
        url: 目標 URL
        attempt: 當前是第幾次嘗試
    
    Returns:
        HTML 內容或 None
    """
    print(f"  🌐 Playwright 嘗試 {attempt}/3...")
    
    try:
        with sync_playwright() as p:
            # 配置瀏覽器
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-dev-shm-usage',  # 避免共享記憶體問題
                    '--no-sandbox',             # GitHub Actions 需要
                    '--disable-setuid-sandbox'
                ]
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = context.new_page()
            
            # 設置較短的超時,失敗就快速重試
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                print(f"    ✓ 頁面載入成功")
            except PlaywrightTimeoutError:
                print(f"    ⚠️ 載入超時,但繼續嘗試...")
            except PlaywrightError as e:
                if "ERR_NETWORK_CHANGED" in str(e):
                    print(f"    ⚠️ 網路切換錯誤,將重試...")
                    browser.close()
                    return None
                raise
            
            # 等待動態內容
            print(f"    ⏳ 等待動態內容 (5秒)...")
            time.sleep(5)
            
            # 獲取內容
            html_content = page.content()
            print(f"    ✓ 獲取頁面內容 ({len(html_content):,} 字元)")
            
            browser.close()
            return html_content
            
    except Exception as e:
        print(f"    ✗ 失敗: {type(e).__name__}")
        return None


def extract_info_from_url(url):
    """從 URL 提取標題和日期"""
    title = None
    date_text = None
    
    url_decoded = unquote(url)
    filename = url_decoded.split('/')[-1].replace('.pdf', '').replace('.PDF', '')
    
    date_patterns = [
        r'20\d{2}年\d{1,2}月\d{1,2}日',
        r'20\d{2}[_-]\d{1,2}[_-]\d{1,2}',
        r'20\d{2}\d{2}\d{2}',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, filename)
        if match:
            date_text = match.group(0)
            if len(date_text) == 8 and date_text.isdigit():
                date_text = f"{date_text[:4]}/{date_text[4:6]}/{date_text[6:8]}"
            break
    
    if date_text:
        title = re.sub(r'20\d{2}[年_\-/]\d{1,2}[月_\-/]\d{1,2}[日]?', '', filename)
        title = re.sub(r'20\d{2}\d{2}\d{2}', '', title)
        
        # 如果只剩流水號,設為 None
        if re.match(r'^[-_A-Za-z0-9]+$', title.strip()):
            title = None
    else:
        title = filename
    
    return title, date_text


def extract_title_from_link(link):
    """從連結元素提取標題"""
    title = link.get_text(strip=True)
    
    if not title or len(title) < 5:
        title = link.get('title', '')
    
    if not title or len(title) < 5:
        parent = link.find_parent(['li', 'div', 'td'])
        if parent:
            title = re.sub(r'\s+', ' ', parent.get_text(strip=True))
    
    return title


def extract_date_from_link(link):
    """從連結周圍提取日期"""
    parent = link.find_parent(['li', 'div', 'tr', 'td', 'article'])
    if parent:
        search_text = parent.get_text()
    else:
        search_text = link.get_text()
    
    return extract_date_from_text(search_text)


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
    title = re.sub(r'20\d{2}[年/.\-_]\d{1,2}[月/.\-_]\d{1,2}[日]?', '', title)
    title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\(PDF\)', '', title, flags=re.IGNORECASE)
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
