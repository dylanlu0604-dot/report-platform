import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import time
from scrapers.utils import HEADERS, is_within_30_days

def scrape():
    """
    中國信託銀行 - 市場評論爬蟲
    
    來源: https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html
    抓取: 最近 30 天內的市場評論 PDF 報告
    """
    print("🔍 正在爬取 CTBC (中國信託銀行 - 市場評論)...")
    reports = []
    seen_urls = set()
    
    base_url = "https://www.ctbcbank.com"
    target_url = "https://www.ctbcbank.com/twrbo/zh_tw/wm_index/wm_investreport/market-comment.html"
    
    try:
        # 取得列表頁
        resp = requests.get(target_url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 策略 1: 直接找 PDF 連結
        pdf_links = soup.find_all('a', href=re.compile(r'\.pdf$', re.IGNORECASE))
        
        if pdf_links:
            print(f"  找到 {len(pdf_links)} 個 PDF 連結")
            
            for link in pdf_links:
                pdf_url = urljoin(base_url, link['href'])
                
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)
                
                # 提取標題
                title = link.get_text(strip=True)
                
                # 如果連結文字太短,從父元素找
                if len(title) < 5:
                    parent = link.find_parent(['li', 'div', 'tr', 'td'])
                    if parent:
                        title = re.sub(r'\s+', ' ', parent.get_text(strip=True))
                
                # 還是太短就用檔名
                if len(title) < 5:
                    from urllib.parse import unquote
                    filename = pdf_url.split('/')[-1].replace('.pdf', '')
                    title = unquote(filename)
                
                # 提取日期
                date_text = None
                parent = link.find_parent(['li', 'div', 'tr', 'td'])
                
                if parent:
                    search_text = parent.get_text()
                else:
                    search_text = title + " " + pdf_url
                
                # 多種日期格式
                date_patterns = [
                    r'20\d{2}年\d{1,2}月\d{1,2}日',
                    r'20\d{2}/\d{1,2}/\d{1,2}',
                    r'20\d{2}\.\d{1,2}\.\d{1,2}',
                    r'20\d{2}-\d{1,2}-\d{1,2}',
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, search_text)
                    if match:
                        date_text = match.group(0)
                        break
                
                # 沒日期就跳過
                if not date_text:
                    continue
                
                # 檢查 30 天內
                if not is_within_30_days(date_text):
                    continue
                
                # 清理標題
                title = re.sub(r'20\d{2}[年/.\-]\d{1,2}[月/.\-]\d{1,2}[日]?', '', title)
                title = re.sub(r'\.pdf$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s+', ' ', title).strip()
                
                reports.append({
                    "Source": "CTBC",
                    "Date": date_text,
                    "Name": title,
                    "Link": pdf_url
                })
        
        # 策略 2: 如果沒有直接 PDF,找報告詳情頁
        if len(reports) == 0:
            print("  未找到直接 PDF,嘗試報告詳情頁...")
            
            report_keywords = ['報告', '評論', '分析', '展望', '觀點']
            detail_links = []
            
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.get_text(strip=True)
                
                if '.pdf' not in href.lower() and any(kw in text for kw in report_keywords):
                    full_url = urljoin(base_url, href)
                    if 'ctbcbank.com' in full_url:
                        detail_links.append((full_url, text))
            
            print(f"  找到 {len(detail_links)} 個詳情頁")
            
            # 訪問詳情頁
            for detail_url, preview_title in detail_links[:20]:
                if detail_url in seen_urls:
                    continue
                seen_urls.add(detail_url)
                
                try:
                    detail_resp = requests.get(detail_url, headers=HEADERS, timeout=10)
                    detail_resp.encoding = 'utf-8'
                    detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
                    
                    # 找 PDF
                    pdf_link = detail_soup.find('a', href=re.compile(r'\.pdf$', re.I))
                    if not pdf_link:
                        continue
                    
                    pdf_url = urljoin(detail_url, pdf_link['href'])
                    if pdf_url in seen_urls:
                        continue
                    seen_urls.add(pdf_url)
                    
                    # 標題
                    h1 = detail_soup.find('h1')
                    title = h1.get_text(strip=True) if h1 else preview_title
                    
                    # 日期
                    date_text = None
                    for pattern in date_patterns:
                        match = re.search(pattern, detail_resp.text)
                        if match:
                            date_text = match.group(0)
                            break
                    
                    if not date_text or not is_within_30_days(date_text):
                        continue
                    
                    title = re.sub(r'20\d{2}[年/.\-]\d{1,2}[月/.\-]\d{1,2}[日]?', '', title)
                    title = re.sub(r'\s+', ' ', title).strip()
                    
                    reports.append({
                        "Source": "CTBC",
                        "Date": date_text,
                        "Name": title,
                        "Link": pdf_url
                    })
                    
                    time.sleep(0.3)
                    
                except Exception:
                    continue
        
    except Exception as e:
        print(f"  ❌ CTBC 爬取失敗: {e}")
    
    print(f"  ✅ CTBC 找到 {len(reports)} 筆報告")
    return reports
