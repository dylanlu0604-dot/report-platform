import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    DLRI 爬蟲 - 終極靈活版
    
    核心策略: 不假設任何特定的 URL 格式,而是:
    1. 掃描首頁找出所有可能是"報告列表"的連結
    2. 從這些列表頁找出所有報告
    3. 訪問每個報告頁面提取資訊
    """
    print("🔍 正在爬取 DLRI (第一生命經濟研究所) - 🎯 終極靈活模式...")
    reports = []
    seen_urls = set()
    
    base_url = "https://www.dlri.co.jp"
    
    # 統計
    stats = {
        'list_pages_found': 0,
        'report_candidates': 0,
        'valid_reports': 0,
        'no_date': 0,
        'old_date': 0
    }
    
    # ==========================================
    # 階段 1: 從首頁找出"報告列表頁"的連結
    # ==========================================
    print("  [階段 1] 從首頁尋找報告列表頁...")
    
    list_page_urls = []
    
    try:
        resp = requests.get(base_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 策略: 找所有內部連結,過濾出可能是報告列表的
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text(strip=True)
            
            # 轉換為絕對 URL
            if href.startswith('/'):
                full_url = urljoin(base_url, href)
            elif href.startswith('http'):
                full_url = href
            else:
                continue
            
            # 只處理 DLRI 網站的連結
            if 'dlri.co.jp' not in full_url:
                continue
            
            # 關鍵: 找可能包含報告列表的頁面
            # 日文關鍵字: レポート(report)、調査研究(research)、刊行物(publications)
            keywords = [
                'report', 'research', 'publication', 'column', 'article',
                'レポート', '報告', '調査', '研究', '刊行', 'コラム',
                'macro', 'market', 'economy', 'finance', 'outlook',
                'マクロ', '市場', '経済', '金融', '展望'
            ]
            
            # 檢查 URL 或連結文字是否包含這些關鍵字
            url_lower = full_url.lower()
            text_lower = text.lower()
            
            if any(kw in url_lower or kw in text_lower for kw in keywords):
                # 排除明顯不是列表的頁面
                if not any(exclude in text for exclude in ['English', 'プライバシー', 'サイトマップ']):
                    list_page_urls.append(full_url)
        
        # 去重
        list_page_urls = list(set(list_page_urls))
        stats['list_pages_found'] = len(list_page_urls)
        
        print(f"    ✓ 找到 {len(list_page_urls)} 個可能的報告列表頁")
        
        # 顯示前幾個供除錯
        if list_page_urls:
            print(f"    📋 樣本列表頁:")
            for url in list_page_urls[:5]:
                print(f"       • {url}")
                
    except Exception as e:
        print(f"    ✗ 首頁掃描失敗: {e}")
        # 即使首頁失敗,也嘗試一些已知的常見路徑
        list_page_urls = [
            f"{base_url}/report",
            f"{base_url}/research", 
            f"{base_url}/column",
            f"{base_url}/macro",
        ]
    
    # ==========================================
    # 階段 2: 從列表頁找出所有報告連結
    # ==========================================
    print(f"\n  [階段 2] 從列表頁提取報告連結...")
    
    report_urls = []
    
    for list_url in list_page_urls[:20]:  # 限制最多檢查 20 個列表頁
        try:
            resp = requests.get(list_url, headers=HEADERS, timeout=8)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 策略: 找所有看起來像"報告詳情頁"的連結
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                # 轉換為絕對 URL
                full_url = urljoin(list_url, href)
                
                # 只要 DLRI 的連結
                if 'dlri.co.jp' not in full_url:
                    continue
                
                # 關鍵: 過濾條件要非常寬鬆
                # 只排除明顯不是報告的連結
                exclude_patterns = [
                    r'mailto:', r'javascript:', r'#',
                    r'\.pdf$', r'\.zip$', r'\.xlsx?$',  # 這些是下載檔案,不是報告頁
                    r'/(english|privacy|sitemap|contact|about)/',
                ]
                
                if any(re.search(pattern, full_url, re.I) for pattern in exclude_patterns):
                    continue
                
                # 連結文字太短或是導航文字就跳過
                if len(text) < 5:
                    continue
                    
                nav_keywords = [
                    '一覧', 'List', 'トップ', 'ホーム', 'Home', 'TOP',
                    '次へ', '前へ', 'Next', 'Previous', 'もっと見る',
                    '戻る', 'Back', '検索', 'Search', 'お知らせ', 'News'
                ]
                
                if any(kw in text for kw in nav_keywords):
                    continue
                
                # 看起來是有效的報告連結
                report_urls.append((full_url, text))
                
            time.sleep(0.2)  # 禮貌性延遲
            
        except Exception as e:
            continue
    
    # 去重
    report_urls = list(set(report_urls))
    stats['report_candidates'] = len(report_urls)
    
    print(f"    ✓ 找到 {len(report_urls)} 個報告候選連結")
    
    if len(report_urls) == 0:
        print(f"\n  ⚠️  沒有找到任何報告連結!")
        print(f"  🔍 可能的原因:")
        print(f"     1. DLRI 網站完全改版了")
        print(f"     2. 報告內容需要登入才能看")
        print(f"     3. 使用 JavaScript 動態載入 (需要 Selenium)")
        print(f"\n  💡 建議:")
        print(f"     1. 手動訪問 https://www.dlri.co.jp/ 確認報告位置")
        print(f"     2. 檢查是否需要登入")
        print(f"     3. 查看網頁原始碼,搜尋 'report' 或 'レポート'")
        print(f"\n  ✅ DLRI 最終成功收錄 {len(reports)} 筆報告")
        return reports
    
    # 顯示樣本
    print(f"    📋 報告樣本:")
    for url, title in report_urls[:5]:
        print(f"       • {title[:50]}")
        print(f"         {url}")
    
    # ==========================================
    # 階段 3: 訪問每個報告頁面提取詳細資訊
    # ==========================================
    print(f"\n  [階段 3] 提取報告詳情 (0/{len(report_urls)})...", end='', flush=True)
    
    for idx, (url, title_preview) in enumerate(report_urls, 1):
        # 避免重複
        if url in seen_urls:
            continue
        seen_urls.add(url)
        
        # 進度顯示
        if idx % 5 == 0:
            print(f"\r  [階段 3] 提取報告詳情 ({idx}/{len(report_urls)})...", end='', flush=True)
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=8)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 提取標題 (優先順序: h1 > title > 預覽標題)
            title = None
            
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            
            if not title or len(title) < 5:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True).split('|')[0].split('｜')[0].strip()
            
            if not title or len(title) < 5:
                title = title_preview
            
            # 最終檢查
            if not title or len(title) < 5:
                continue
            
            # 提取日期 (在整個頁面中搜尋)
            date_text = None
            
            # 日期正則模式 (支援多種格式)
            date_patterns = [
                r'20\d{2}年\d{1,2}月\d{1,2}日',      # 2026年2月16日
                r'20\d{2}\.\d{1,2}\.\d{1,2}',        # 2026.2.16
                r'20\d{2}/\d{1,2}/\d{1,2}',          # 2026/2/16
                r'20\d{2}-\d{1,2}-\d{1,2}',          # 2026-02-16
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, resp.text)
                if match:
                    date_text = match.group(0)
                    break
            
            # 沒日期就跳過
            if not date_text:
                stats['no_date'] += 1
                continue
            
            # 檢查是否在 30 天內
            if not is_within_30_days(date_text):
                stats['old_date'] += 1
                continue
            
            # 尋找 PDF 連結
            pdf_link = url  # 預設
            
            # 多種策略尋找 PDF
            pdf_candidates = []
            
            # 策略 1: href 包含 .pdf
            for a in soup.find_all('a', href=re.compile(r'\.pdf$', re.I)):
                pdf_candidates.append(urljoin(url, a['href']))
            
            # 策略 2: 文字包含 PDF 或ダウンロード
            for a in soup.find_all('a', string=re.compile(r'PDF|ダウンロード|download', re.I)):
                if a.get('href'):
                    pdf_candidates.append(urljoin(url, a['href']))
            
            # 策略 3: class/id 包含 pdf
            for a in soup.find_all('a', attrs={'class': re.compile(r'pdf', re.I)}):
                if a.get('href'):
                    pdf_candidates.append(urljoin(url, a['href']))
            
            # 使用第一個找到的 PDF
            if pdf_candidates:
                pdf_link = pdf_candidates[0]
            
            # 加入結果
            reports.append({
                "Source": "DLRI",
                "Date": date_text,
                "Name": title,
                "Link": pdf_link
            })
            
            stats['valid_reports'] += 1
            
            time.sleep(0.15)  # 禮貌性延遲
            
        except Exception as e:
            continue
    
    print(f"\r  [階段 3] 提取報告詳情 ({len(report_urls)}/{len(report_urls)}) ✓")
    
    # ==========================================
    # 統計報告
    # ==========================================
    print(f"\n  📊 最終統計:")
    print(f"     列表頁數: {stats['list_pages_found']}")
    print(f"     報告候選: {stats['report_candidates']}")
    print(f"     有效報告: {stats['valid_reports']}")
    print(f"     無日期: {stats['no_date']}")
    print(f"     舊報告: {stats['old_date']}")
    print(f"  ✅ DLRI 最終成功收錄 {len(reports)} 筆報告")
    
    return reports


if __name__ == "__main__":
    results = scrape()
    
    if results:
        print(f"\n📄 找到的報告:")
        for i, r in enumerate(results, 1):
            print(f"\n{i}. [{r['Date']}] {r['Name'][:70]}")
            print(f"   🔗 {r['Link']}")
