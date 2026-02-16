import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    """
    改進版 DLRI 爬蟲
    
    主要改進:
    1. 擴大日期搜尋範圍
    2. 更寬鬆的連結過濾條件
    3. 更多的日期格式支援
    4. 更好的錯誤處理和日誌
    """
    print("🔍 正在爬取 DLRI (第一生命經濟研究所)...")
    base_url = "https://www.dlri.co.jp"
    target_url = "https://www.dlri.co.jp/report_index.html"
    reports = []
    
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()  # 檢查 HTTP 錯誤
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 找所有連結
        links = soup.find_all('a', href=True)
        seen_hrefs = set()
        
        # 用於除錯
        total_links = len(links)
        report_candidates = 0
        date_found = 0
        within_30_days = 0
        
        for tag in links:
            href = tag['href']
            title = tag.get_text(strip=True)
            
            # 1. 基本過濾
            if len(title) < 5 or href in seen_hrefs:
                continue
            
            # 2. 必須包含 /report/ 且以 .html 結尾
            if "/report/" not in href or not href.endswith('.html'):
                continue
            
            report_candidates += 1
            
            # 3. 排除明顯的導航連結
            exclude_keywords = ["一覧", "List", "執筆者", "分野別", "お知らせ", "検索", "バックナンバー"]
            if any(kw in title for kw in exclude_keywords):
                continue
            
            # 4. 擴大日期搜尋範圍 - 這是關鍵改進!
            date_text = None
            search_contexts = []
            
            # 方法 A: 檢查連結的直接父元素
            parent = tag.find_parent()
            if parent:
                search_contexts.append(parent.get_text())
                
                # 檢查前一個兄弟元素 (日期可能在連結前面)
                prev = parent.find_previous_sibling()
                if prev:
                    search_contexts.append(prev.get_text())
                
                # 檢查後一個兄弟元素
                next_sib = parent.find_next_sibling()
                if next_sib:
                    search_contexts.append(next_sib.get_text())
            
            # 方法 B: 檢查包含此連結的整個容器 (li, div, tr, article)
            container = tag.find_parent(['li', 'div', 'tr', 'article', 'section', 'td'])
            if container:
                search_contexts.append(container.get_text())
            
            # 方法 C: 檢查連結文字本身 (有時日期就在標題裡)
            search_contexts.append(title)
            
            # 合併所有上下文
            full_context = " ".join(search_contexts)
            
            # 支援多種日期格式
            date_patterns = [
                r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}[日]?',  # 2026.02.16, 2026年2月16日
                r'20\d{2}[-]\d{1,2}[-]\d{1,2}',             # 2026-02-16
                r'20\d{2}/\d{1,2}/\d{1,2}',                 # 2026/2/16
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, full_context)
                if match:
                    date_text = match.group(0)
                    date_found += 1
                    break
            
            # 5. 找不到日期就跳過
            if not date_text:
                continue
            
            # 6. 檢查是否在30天內
            if not is_within_30_days(date_text):
                continue
            
            within_30_days += 1
            
            # 7. 加入清單
            seen_hrefs.add(href)
            full_link = urljoin(base_url, href)
            
            # 嘗試找到實際的 PDF 連結
            try:
                final_pdf = fetch_real_pdf_link(full_link)
            except Exception as e:
                print(f"    ⚠️  無法取得 PDF: {e}")
                final_pdf = full_link
            
            reports.append({
                "Source": "DLRI",
                "Date": date_text,
                "Name": title,
                "Link": final_pdf
            })
        
        # 除錯資訊
        print(f"    📊 總連結數: {total_links}")
        print(f"    📊 報告候選: {report_candidates}")
        print(f"    📊 找到日期: {date_found}")
        print(f"    📊 30天內: {within_30_days}")
        
    except requests.RequestException as e:
        print(f"  ❌ 網路錯誤: {e}")
    except Exception as e:
        print(f"  ❌ DLRI 失敗: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"  ✅ DLRI 找到 {len(reports)} 筆報告")
    return reports


def scrape_with_alternative_strategy():
    """
    替代策略:如果主要方法失敗,嘗試不同的方法
    
    可能的問題:
    1. 網站結構改變
    2. 報告頁面 URL 改變
    3. 日期格式改變
    """
    print("\n🔄 嘗試替代策略...")
    base_url = "https://www.dlri.co.jp"
    
    # 可能的報告清單頁面
    alternative_urls = [
        "https://www.dlri.co.jp/report_index.html",
        "https://www.dlri.co.jp/report.html",
        "https://www.dlri.co.jp/report/index.html",
        "https://www.dlri.co.jp/research/index.html",
    ]
    
    for url in alternative_urls:
        try:
            print(f"  嘗試: {url}")
            resp = requests.get(url, headers=HEADERS, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                
                # 分析頁面結構
                report_links = soup.find_all('a', href=re.compile(r'/report/.*\.html'))
                print(f"    ✓ 找到 {len(report_links)} 個報告連結")
                
                # 顯示前幾個樣本
                for i, link in enumerate(report_links[:3]):
                    print(f"      {i+1}. {link.get_text(strip=True)[:50]}")
                
                return soup  # 返回成功的頁面供進一步分析
                
        except Exception as e:
            print(f"    ✗ 失敗: {e}")
    
    return None


# 如果直接執行此腳本
if __name__ == "__main__":
    reports = scrape()
    
    if reports:
        print("\n📄 找到的報告:")
        for i, r in enumerate(reports, 1):
            print(f"{i}. [{r['Date']}] {r['Name']}")
            print(f"   {r['Link']}\n")
    else:
        print("\n❓ 沒有找到報告。可能的原因:")
        print("   1. 網站最近 30 天內沒有新報告")
        print("   2. 網站結構改變,日期解析失敗")
        print("   3. 網路連接問題")
        print("\n   建議:")
        print("   - 檢查 is_within_30_days() 函數是否正常工作")
        print("   - 手動訪問網站確認最近是否有新報告")
        print("   - 檢查網站 HTML 結構是否改變")
