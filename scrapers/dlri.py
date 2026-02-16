import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    DLRI 爬蟲 - 三引擎增強版
    
    策略說明:
    1. MarsFlag API (如果可用)
    2. 首頁連結掃描
    3. 已知報告列表頁面 (備援)
    4. RSS/Sitemap (如果有)
    """
    print("🔍 正在爬取 DLRI (第一生命經濟研究所) - 🚀 三引擎增強模式...")
    reports = []
    seen_urls = set()
    found_paths = []
    
    # 統計資訊
    stats = {
        'api_paths': 0,
        'homepage_paths': 0,
        'list_page_paths': 0,
        'valid_reports': 0,
        'no_date': 0,
        'old_date': 0,
        'errors': 0
    }

    # ==========================================
    # 引擎 1：MarsFlag API (可能需要認證或有速率限制)
    # ==========================================
    print("  [引擎 1] 嘗試 MarsFlag API...")
    api_url = "https://finder.api.mf.marsflag.com/api/v1/finder_service/documents/d3eff4d6/search"
    api_headers = HEADERS.copy()
    api_headers.update({
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
        'Origin': 'https://www.dlri.co.jp',
        'Referer': 'https://www.dlri.co.jp/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site'
    })
    
    # 嘗試多種查詢策略
    queries = [
        {"match": "経済", "q": "経済"},
        {"match": "市場", "q": "市場"},
        {"match": "金融", "q": "金融"},
        {"match": "レポート", "q": "レポート"},
        {"q": ""},  # 空查詢有時能返回最新項目
    ]
    
    for query_params in queries:
        try:
            resp = requests.get(api_url, params=query_params, headers=api_headers, timeout=8)
            if resp.status_code == 200:
                # 清理 JSON 跳脫字元
                text = resp.text.replace('\\/', '/')
                
                # 模式 1: /report/xxx.html
                paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', text)
                found_paths.extend(paths)
                stats['api_paths'] += len(paths)
                
                # 如果找到結果就不需要繼續查詢
                if paths:
                    break
        except Exception as e:
            stats['errors'] += 1
            # API 失敗不要中斷整個流程
            pass
    
    if stats['api_paths'] > 0:
        print(f"    ✓ API 找到 {stats['api_paths']} 個路徑")
    else:
        print(f"    ✗ API 無結果或無法訪問")

    # ==========================================
    # 引擎 2：首頁連結掃描
    # ==========================================
    print("  [引擎 2] 掃描首頁連結...")
    try:
        top_resp = requests.get("https://www.dlri.co.jp/", headers=HEADERS, timeout=8)
        if top_resp.status_code == 200:
            # 模式 1: 標準報告連結
            paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', top_resp.text)
            found_paths.extend(paths)
            stats['homepage_paths'] = len(paths)
            
            # 模式 2: 有時連結可能包含在 JavaScript 變數中
            js_paths = re.findall(r'["\'](/report/[^"\']+\.html)["\']', top_resp.text)
            found_paths.extend(js_paths)
            stats['homepage_paths'] += len(js_paths)
            
            print(f"    ✓ 首頁找到 {stats['homepage_paths']} 個路徑")
        else:
            print(f"    ✗ 首頁訪問失敗 (HTTP {top_resp.status_code})")
    except Exception as e:
        print(f"    ✗ 首頁訪問異常")
        stats['errors'] += 1

    # ==========================================
    # 引擎 3：已知報告列表頁面 (備援)
    # ==========================================
    print("  [引擎 3] 嘗試報告列表頁...")
    list_pages = [
        "https://www.dlri.co.jp/report_index.html",
        "https://www.dlri.co.jp/report.html",
        "https://www.dlri.co.jp/report/index.html",
    ]
    
    for list_url in list_pages:
        try:
            resp = requests.get(list_url, headers=HEADERS, timeout=8)
            if resp.status_code == 200:
                paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', resp.text)
                if paths:
                    found_paths.extend(paths)
                    stats['list_page_paths'] += len(paths)
                    print(f"    ✓ {list_url} 找到 {len(paths)} 個路徑")
                    break  # 找到一個有效頁面就夠了
        except:
            continue
    
    if stats['list_page_paths'] == 0:
        print(f"    ✗ 無法訪問任何列表頁")

    # ==========================================
    # 資料處理：訪問每個報告頁面並提取資訊
    # ==========================================
    unique_paths = list(set(found_paths))
    print(f"\n  📊 總共收集到 {len(unique_paths)} 個不重複的報告連結")
    
    if len(unique_paths) == 0:
        print(f"  ⚠️  未找到任何報告連結,可能原因:")
        print(f"      1. 網站結構已改變")
        print(f"      2. API 需要認證或有 CORS 限制")
        print(f"      3. 最近真的沒有新報告")
        print(f"  ✅ DLRI 最終成功收錄 {len(reports)} 筆報告")
        return reports
    
    print(f"  🔍 開始逐一檢驗報告內頁...")
    
    for idx, path in enumerate(unique_paths, 1):
        url = urljoin("https://www.dlri.co.jp", path)
        
        # 避免重複處理
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        # 顯示進度 (每 10 個顯示一次)
        if idx % 10 == 0:
            print(f"    處理中... {idx}/{len(unique_paths)}")
        
        try:
            detail_resp = requests.get(url, headers=HEADERS, timeout=8)
            detail_resp.encoding = 'utf-8'
            soup = BeautifulSoup(detail_resp.text, 'html.parser')
            
            # 1. 提取標題
            title = None
            
            # 策略 A: <title> 標籤
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
                # 清理標題 (移除網站名稱)
                title = title.split('|')[0].split('｜')[0].strip()
            
            # 策略 B: <h1> 標籤 (通常是文章標題)
            if not title or len(title) < 5:
                h1_tag = soup.find('h1')
                if h1_tag:
                    title = h1_tag.get_text(strip=True)
            
            # 策略 C: meta title
            if not title or len(title) < 5:
                meta_title = soup.find('meta', property='og:title')
                if meta_title and meta_title.get('content'):
                    title = meta_title['content'].strip()
            
            # 無效標題就跳過
            if not title or len(title) < 5:
                continue
            
            # 排除明顯的導航頁面
            if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ", "検索"]):
                continue
            
            # 2. 提取日期 (多種策略)
            date_text = None
            
            # 策略 A: 在整個頁面的原始碼中找 (最粗暴但有效)
            date_patterns = [
                r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}[日]?',  # 2026.02.16, 2026年2月16日
                r'20\d{2}[-]\d{1,2}[-]\d{1,2}',             # 2026-02-16
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, detail_resp.text)
                if match:
                    date_text = match.group(0)
                    break
            
            # 策略 B: 檢查 meta 標籤
            if not date_text:
                meta_date = soup.find('meta', property='article:published_time')
                if meta_date and meta_date.get('content'):
                    date_text = meta_date['content'][:10]  # 通常是 YYYY-MM-DD 格式
            
            # 沒有日期就跳過
            if not date_text:
                stats['no_date'] += 1
                continue
            
            # 檢查是否在 30 天內
            if not is_within_30_days(date_text):
                stats['old_date'] += 1
                continue
            
            # 3. 找 PDF 下載連結
            pdf_link = url  # 預設值
            
            # 策略 A: 找 <a> 標籤中包含 .pdf 的連結
            pdf_tag = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
            
            # 策略 B: 找文字包含 "PDF" 的連結
            if not pdf_tag:
                pdf_tag = soup.find('a', string=re.compile(r'PDF|ダウンロード|download', re.IGNORECASE))
            
            # 策略 C: 找 class 或 id 包含 pdf 的元素
            if not pdf_tag:
                pdf_tag = soup.find('a', class_=re.compile(r'pdf', re.IGNORECASE))
            
            if pdf_tag and pdf_tag.get('href'):
                pdf_link = urljoin(url, pdf_tag['href'])
            
            # 4. 加入結果
            reports.append({
                "Source": "DLRI",
                "Date": date_text,
                "Name": title,
                "Link": pdf_link
            })
            stats['valid_reports'] += 1
            
            # 禮貌性延遲
            time.sleep(0.2)
            
        except Exception as e:
            stats['errors'] += 1
            # 單個頁面失敗不影響其他頁面
            continue
    
    # 輸出統計資訊
    print(f"\n  📊 統計資訊:")
    print(f"    - API 路徑: {stats['api_paths']}")
    print(f"    - 首頁路徑: {stats['homepage_paths']}")
    print(f"    - 列表頁路徑: {stats['list_page_paths']}")
    print(f"    - 有效報告: {stats['valid_reports']}")
    print(f"    - 無日期: {stats['no_date']}")
    print(f"    - 舊日期: {stats['old_date']}")
    print(f"    - 錯誤數: {stats['errors']}")
    print(f"  ✅ DLRI 最終成功收錄 {len(reports)} 筆報告")
    
    return reports


# 獨立的測試函數
def test_scraper():
    """測試函數,用於診斷問題"""
    print("🧪 DLRI 爬蟲測試模式")
    print("=" * 60)
    
    # 測試 1: 檢查網站是否可訪問
    print("\n[測試 1] 網站連通性測試")
    try:
        resp = requests.get("https://www.dlri.co.jp/", headers=HEADERS, timeout=5)
        print(f"✓ 首頁狀態碼: {resp.status_code}")
        print(f"✓ 內容長度: {len(resp.text)} 字元")
    except Exception as e:
        print(f"✗ 首頁訪問失敗: {e}")
        return
    
    # 測試 2: 檢查是否能找到報告連結
    print("\n[測試 2] 連結發現測試")
    paths = re.findall(r'/report/[a-zA-Z0-9_/-]+\.html', resp.text)
    print(f"首頁找到 {len(set(paths))} 個不重複的報告連結")
    
    if paths:
        print("樣本連結:")
        for p in list(set(paths))[:5]:
            print(f"  - https://www.dlri.co.jp{p}")
    
    # 測試 3: 測試一個報告頁面
    if paths:
        print("\n[測試 3] 單一報告頁面測試")
        test_path = paths[0]
        test_url = f"https://www.dlri.co.jp{test_path}"
        
        try:
            resp = requests.get(test_url, headers=HEADERS, timeout=5)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 標題
            title_tag = soup.find('title')
            print(f"標題: {title_tag.get_text(strip=True) if title_tag else 'N/A'}")
            
            # 日期
            date_match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}', resp.text)
            print(f"日期: {date_match.group(0) if date_match else 'N/A'}")
            
            # PDF
            pdf_tag = soup.find('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
            print(f"PDF: {pdf_tag['href'] if pdf_tag else 'N/A'}")
            
        except Exception as e:
            print(f"✗ 報告頁面訪問失敗: {e}")


if __name__ == "__main__":
    # 執行測試
    test_scraper()
    
    print("\n" + "=" * 60)
    print("正式執行爬蟲")
    print("=" * 60)
    
    # 執行爬蟲
    results = scrape()
    
    # 顯示結果
    if results:
        print(f"\n📄 找到 {len(results)} 筆報告:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['Date']}] {r['Name']}")
            print(f"   🔗 {r['Link']}")
