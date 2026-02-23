import re
import time
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲 (完全容錯版)
    
    策略:
    1. 先測試網路連通性
    2. 如果無法連接,優雅地返回空列表
    3. 不影響其他爬蟲的執行
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    # 快速網路測試 (5秒超時)
    if not test_connectivity(base_url):
        print("  ⚠️  無法連接到中國信託網站")
        print("  💡 可能原因:")
        print("     - GitHub Actions 環境網路限制")
        print("     - 網站封鎖 GitHub IP")
        print("     - 網站維護中")
        print("  ℹ️  跳過此爬蟲,繼續執行其他爬蟲...")
        return reports
    
    # 嘗試使用 Playwright
    html_content = None
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
        
        for attempt in range(2):  # 減少到 2 次重試節省時間
            try:
                html_content = scrape_with_playwright(target_url, attempt + 1)
                if html_content:
                    break
            except Exception as e:
                if attempt < 1:
                    time.sleep(3)
    except ImportError:
        print("  ⚠️  Playwright 未安裝,使用 requests...")
    
    # 降級使用 requests
    if not html_content:
        print("  🔄 使用 requests...")
        try:
            import requests
            resp = requests.get(target_url, headers=HEADERS, timeout=15)
            html_content = resp.text
            print(f"  ✓ 成功 ({len(html_content):,} 字元)")
        except Exception as e:
            print(f"  ❌ 連接失敗: {type(e).__name__}")
            print("  ℹ️  此爬蟲暫時無法使用")
            return reports
    
    # 解析 HTML
    try:
        reports = parse_html(html_content, base_url)
    except Exception as e:
        print(f"  ❌ 解析失敗: {e}")
    
    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports


def test_connectivity(base_url, timeout=5):
    """快速測試網站連通性"""
    try:
        import requests
        resp = requests.head(base_url, timeout=timeout, allow_redirects=True)
        return resp.status_code < 500
    except:
        return False


def scrape_with_playwright(url, attempt):
    """使用 Playwright 抓取 (簡化版)"""
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    
    print(f"  🌐 Playwright 嘗試 {attempt}/2...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--no-sandbox']
            )
            
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            
            page = context.new_page()
            
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)  # 縮短到 20 秒
            except PlaywrightTimeoutError:
                pass
            
            time.sleep(3)  # 縮短等待時間
            html_content = page.content()
            
            browser.close()
            return html_content
            
    except Exception:
        return None


def parse_html(html_content, base_url):
    """解析 HTML 提取報告"""
    reports = []
    soup = BeautifulSoup(html_content, 'html.parser')
    seen_urls = set()
    
    # 廣域搜尋 PDF
    pdf_urls_raw = []
    
    # 正則搜尋
    pdf_urls_raw.extend(re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE))
    pdf_urls_raw.extend(re.findall(r'(/IB/api/adapters/IB_Adapter/resource/report/[^"\']+)', html_content))
    
    # BeautifulSoup 搜尋
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if '.pdf' in href.lower() or '/resource/report/' in href.lower():
            pdf_urls_raw.append(href)
    
    # 清理 URL
    target_urls = []
    for url in set(pdf_urls_raw):
        url = url.strip().strip('"').strip("'")
        if url and ('.pdf' in url.lower() or '/resource/report/' in url.lower()):
            full_url = urljoin(base_url, url)
            if full_url not in seen_urls:
                target_urls.append(full_url)
                seen_urls.add(full_url)
    
    # 處理每個 URL
    for target_url in target_urls:
        title, date_text = extract_info_from_url(target_url)
        
        if not title or not date_text:
            link = soup.find('a', href=lambda x: x and target_url in urljoin(base_url, x))
            if link:
                if not title:
                    title = extract_title_from_link(link)
                if not date_text:
                    date_text = extract_date_from_link(link)
        
        if not title or len(title) < 5:
            filename = unquote(target_url.split('/')[-1].replace('.pdf', ''))
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
            "Link": target_url
        })
    
    return reports


def extract_info_from_url(url):
    """從 URL 提取標題和日期"""
    title = None
    date_text = None
    
    url_decoded = unquote(url)
    filename = url_decoded.split('/')[-1].replace('.pdf', '')
    
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
    parent = link.find_parent(['li', 'div', 'tr', 'td'])
    search_text = parent.get_text() if parent else link.get_text()
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
