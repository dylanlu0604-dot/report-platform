import re
import time
from urllib.parse import urljoin, unquote
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 假設這是你原本專案中的 utils，請確認路徑正確
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲 (Playwright 動態渲染 + CTBC API 支援版)
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    seen_urls = set()
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            print("  🌐 啟動 Playwright 載入動態網頁...")
            
            # 👉 修改 1：將 networkidle 改為 domcontentloaded，並將超時時間拉長到 60 秒以適應 GitHub Actions
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            except PlaywrightTimeoutError:
                print("  ⚠️ 網頁基本結構載入超時，但可能已部分渲染，繼續嘗試擷取...")

            # 👉 修改 2：拉長手動等待時間。因為我們放棄了 networkidle，所以多給 JS 一點時間生出報告列表
            print("  ⏳ 等待動態內容渲染...")
            time.sleep(8) 
            
            # 獲取渲染後的完整 HTML
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            print(f"  📄 渲染後頁面大小: {len(html_content):,} 字元")
            
            browser.close()

        # ==========================================
        # 策略 1: 廣域 PDF 搜尋 (加入 CTBC 專屬 API 格式)
        # ==========================================
        print("  [策略 1] 廣域 PDF 搜尋...")
        
        pdf_urls_raw = re.findall(r'["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE)
        pdf_urls_raw.extend(re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html_content, re.IGNORECASE))
        pdf_urls_raw.extend(re.findall(r'(https?://[^\s<>"\']+\.pdf)', html_content, re.IGNORECASE))
        
        # 擷取 CTBC 專屬的報告 API 連結
        pdf_urls_raw.extend(re.findall(r'(/IB/api/adapters/IB_Adapter/resource/report/[^"\']+)', html_content, re.IGNORECASE))
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '.pdf' in href.lower() or '/resource/report/' in href.lower():
                pdf_urls_raw.append(href)
        
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
        
        for target_url in target_urls:
            title, date_text = extract_info_from_url(target_url)
            
            # 如果 URL 沒資訊，嘗試找對應的 HTML 標籤
            if not title or not date_text:
                link = soup.find('a', href=lambda x: x and target_url in urljoin(base_url, x))
                
                # 如果用精準 href 找不到，試著找包含這段 report_id 的任何 UI 容器
                if not link:
                    report_id = target_url.split('/')[-1]
                    link = soup.find(lambda tag: tag.name in ['a', 'div', 'li', 'td'] and report_id in str(tag))

                if link:
                    if not title:
                        title = extract_title_from_link(link)
                    if not date_text:
                        date_text = extract_date_from_link(link)
            
            # 如果還是沒標題，用檔名
            if not title or len(title) < 5:
                filename = unquote(target_url.split('/')[-1].replace('.pdf', '').replace('.PDF', ''))
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
                "Link": target_url
            })
            
        # ==========================================
        # 策略 2: 如果沒找到,搜尋所有可能的報告連結
        # ==========================================
        if len(reports) == 0:
            print("  [策略 2] 搜尋報告連結...")
            keywords = [
                '報告', '評論', '分析', '市場', '展望', '觀點',
                'report', 'analysis', 'market', 'comment', 'review',
                '月報', '週報', '日報', '專題', '研究'
            ]
            
            report_links = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                if any(exclude in href.lower() for exclude in ['javascript:', 'mailto:', '#']):
                    continue
                
                if any(kw in link_text or kw in href for kw in keywords):
                    full_url = urljoin(base_url, href)
                    if 'ctbcbank.com' in full_url and full_url not in seen_urls:
                        report_links.append((full_url, link_text))
                        seen_urls.add(full_url)
            
            print(f"    找到 {len(report_links)} 個可能的報告連結")
            # 由於策略 1 已經涵蓋了 API，策略 2 僅作備用，這裡省略後續進階爬取以保持輕量

    except Exception as e:
        print(f"  ❌ CTBC 爬取失敗: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports


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
        
        # 如果去蕪存菁後，標題只剩下流水號 (如 -C-30-0)，強制設為 None，讓程式去抓 HTML 裡的中文標題
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
