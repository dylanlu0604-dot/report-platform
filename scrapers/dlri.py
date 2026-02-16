import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from scrapers.utils import is_within_30_days, fetch_real_pdf_link

def scrape():
    print("🔍 正在爬取 DLRI (第一生命) - 🎭 Playwright 真人模擬模式...")
    reports = []
    
    # 動態載入 Playwright
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ❌ 尚未安裝 Playwright，請確認 requirements.txt")
        return reports

    # 啟動真實的瀏覽器引擎
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 偽裝成一般的 Windows Chrome 瀏覽器
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 前往報告總覽頁面
            page.goto("https://www.dlri.co.jp/report_index.html", wait_until="networkidle", timeout=20000)
            
            # 🌟 關鍵：等待網頁上的 JavaScript 執行，直到報告的 <a> 連結出現為止
            page.wait_for_selector(".list a", timeout=15000)
            
            # 抓取渲染完成後的完整 HTML
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 以下恢復我們熟悉的 Beautifulsoup 解析邏輯
            links = soup.find_all('a', href=re.compile(r'/report/'))
            seen_hrefs = set()
            
            for tag in links:
                href = tag.get('href')
                title = tag.get_text(strip=True)
                
                # 排除太短或重複的雜訊
                if len(title) < 5 or href in seen_hrefs: continue
                if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ"]): continue
                
                # 找日期
                date_text = None
                parent = tag.find_parent()
                if parent:
                    match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', parent.get_text())
                    if match: date_text = match.group(0)
                    
                # 嚴格把關：沒日期或超過30天就踢掉
                if not date_text or not is_within_30_days(date_text): continue
                
                seen_hrefs.add(href)
                link = urljoin("https://www.dlri.co.jp", href)
                
                # 若內頁也被 CloudFront 擋，就直接給網頁連結
                final_pdf = fetch_real_pdf_link(link)
                
                reports.append({
                    "Source": "DLRI", 
                    "Date": date_text, 
                    "Name": title, 
                    "Link": final_pdf
                })
                
        except Exception as e:
            print(f"  ❌ Playwright 執行失敗: {e}")
        finally:
            browser.close()
            
    print(f"  ✅ DLRI 找到 {len(reports)} 筆報告")
    return reports
