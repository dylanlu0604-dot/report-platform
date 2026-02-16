import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
from scrapers.utils import HEADERS, is_within_30_days, fetch_real_pdf_link

def scrape():
    print("\n🔍 正在爬取 DLRI (第一生命經濟研究所) - 🕵️ 偵探模式啟動...")
    base_url = "https://www.dlri.co.jp"
    target_url = "https://www.dlri.co.jp/report/"
    reports = []
    
    try:
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        print(f"  [偵探回報] 🌐 HTTP 狀態碼: {resp.status_code} (如果是 200 代表成功進入網站)")
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        links = soup.find_all('a', href=True)
        print(f"  [偵探回報] 📄 網頁中總共找到了 {len(links)} 個 <a> 連結標籤")
        
        seen_hrefs = set()
        
        for tag in links:
            href = tag['href']
            title = tag.get_text(strip=True)
            
            # 尋找網址裡有 /report/ 的連結
            if "/report/" not in href:
                continue
                
            # 排除明顯是導覽列的無用連結
            if any(kw in title for kw in ["一覧", "List", "執筆者", "分野別", "お知らせ"]): 
                continue
                
            if href in seen_hrefs: continue
            seen_hrefs.add(href)
            
            print(f"  ----------------------------------------")
            print(f"  [偵探回報] 🎯 發現候選報告: {title[:30]}... ({href})")
            
            # 開始找日期
            date_text = "未知日期"
            parent = tag.find_parent()
            if parent:
                parent_text = parent.get_text()
                prev = parent.find_previous_sibling()
                if prev:
                    parent_text += " " + prev.get_text()
                
                match = re.search(r'20\d{2}[./年]\d{1,2}[./月]\d{1,2}日?', parent_text)
                if match: 
                    date_text = match.group(0)
            
            print(f"  [偵探回報] 📅 解析出的日期: {date_text}")
            
            if date_text != "未知日期":
                if is_within_30_days(date_text):
                    link = urljoin(base_url, href)
                    final_pdf = fetch_real_pdf_link(link)
                    reports.append({
                        "Source": "DLRI", 
                        "Date": date_text, 
                        "Name": title, 
                        "Link": final_pdf
                    })
                    print(f"    ✔️ 成功加入清單！")
                else:
                    print(f"    ❌ 被踢除 (原因: 日期超過 30 天)")
            else:
                print(f"    ❌ 被踢除 (原因: 找不到有效日期格式)")
                
    except Exception as e:
        print(f"  ❌ DLRI 失敗: {e}")
    
    print(f"  ✅ DLRI 最終找到 {len(reports)} 筆報告\n")
    return reports
