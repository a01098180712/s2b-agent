import json
import time
import os
import subprocess
import random
import re
from playwright.sync_api import sync_playwright

# ======================================================
# [설정]
# ======================================================
TARGET_URLS = [
    "https://www.coupang.com/vp/products/7410479243?itemId=19199625171&vendorItemId=86317012667",
    "https://www.coupang.com/vp/products/9124094477?itemId=26840740061&vendorItemId=93127986643",
    "https://www.coupang.com/vp/products/8466469683?itemId=24496597951&vendorItemId=91538631793"
]

OUTPUT_FILE = 's2b_results.json'
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DIR = r"C:\ChromeDev"

RESTART_EVERY_N = 50      
BATCH_SLEEP_EVERY_N = 10 
BATCH_SLEEP_DURATION = 60 

# ======================================================
# [모듈] 브라우저 제어
# ======================================================
def launch_chrome():
    print(f"🚀 [System] Chrome 실행 중... (Port: {CDP_PORT})")
    if not os.path.exists(CHROME_PATH):
        print(f"❌ 크롬 실행 파일을 찾을 수 없습니다: {CHROME_PATH}")
        return False

    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1920,1080"
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return True
    except: return False

def kill_chrome():
    try:
        subprocess.run('wmic process where "name=\'chrome.exe\' and commandline like \'%ChromeDev%\'" call terminate', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
    except: pass

# ======================================================
# [모듈 2] 데이터 추출
# ======================================================
def extract_all_specs(page):
    info_dict = {}
    try:
        rows = page.locator("table tr").all()
        for row in rows:
            try:
                texts = row.locator("th, td").all_inner_texts()
                if len(texts) >= 2:
                    info_dict[texts[0].strip()] = texts[1].strip()
            except: continue
    except: pass

    try:
        items = page.locator("ul.prod-description-attribute > li").all_inner_texts()
        for item in items:
            if ":" in item:
                parts = item.split(":", 1)
                info_dict[parts[0].strip()] = parts[1].strip()
    except: pass
    return info_dict

def extract_kc_by_regex(text):
    patterns = [
        r"[A-Z]{2}[0-9]{4,5}-[0-9]{4,5}[A-Z]?", 
        r"[A-Z]{2,4}-[A-Z]{3}-[A-Z]{3}-[\w]+",
        r"R-R-[\w]+-[\w]+"
    ]
    found = set()
    for pat in patterns:
        found.update(re.findall(pat, text))
    return " / ".join(list(found))

def get_best_value(info_dict, keywords, default_val=""):
    for key, val in info_dict.items():
        if any(kw in key for kw in keywords):
            if val and "상세" not in val and "참조" not in val:
                return val
    return default_val

def crawl_item(page, url):
    print(f"▶ 이동: {url[:60]}...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=5000)
    except: pass 

    item = {
        "url": url, "name": "N/A", "price": 0, "image": "", 
        "kc": "상세설명참조", "maker": "협력업체", "origin": "중국", "model": "없음",
        "category": "미분류" # [추가] 카테고리 필드
    }

    try:
        if "/login/" in page.url:
            print("    ⚠️ 로그인 필요 페이지 -> 건너뜀")
            return None

        # [추가] 쿠팡 카테고리(Breadcrumb) 추출
        try:
            # 쿠팡의 breadcrumb id는 보통 'breadcrumb'
            breadcrumb = page.locator("#breadcrumb").first.inner_text()
            # 줄바꿈 등을 '>' 로 변경하여 깔끔하게 정리
            item["category"] = breadcrumb.replace("\n", " > ").strip()
        except:
            item["category"] = "미분류"

        # JSON-LD 파싱
        json_data = page.locator('script[type="application/ld+json"]').first.inner_text()
        data = json.loads(json_data)
        if isinstance(data, list): data = data[0]

        item["name"] = data.get("name", "N/A")
        item["image"] = data.get("image", "")
        if isinstance(item["image"], list): item["image"] = item["image"][0]

        offers = data.get("offers", {})
        if isinstance(offers, list): offers = offers[0]
        item["price"] = int(offers.get("price", 0))

        content = page.content()
        if "무료배송" not in content:
            item["price"] += 3000
            print("   - 배송비 3,000원 추가됨")

    except Exception as e:
        print(f"   ⚠️ 기본 파싱 실패: {e}")
        return None

    try:
        full_text = page.locator("body").inner_text()
        all_specs = extract_all_specs(page)
        
        # KC
        kc_table = get_best_value(all_specs, ["인증", "허가", "신고", "KC"], "")
        kc_regex = extract_kc_by_regex(full_text)
        kc_combined = set()
        if kc_regex: kc_combined.update(kc_regex.split(" / "))
        if kc_table: kc_combined.add(kc_table)
        clean_kc = [k for k in kc_combined if "상세" not in k and "참조" not in k]
        if clean_kc: item["kc"] = " / ".join(clean_kc)

        # Maker
        maker = get_best_value(all_specs, ["제조자", "수입자", "판매업자", "제조사"], "")
        if maker: item["maker"] = maker
        else:
            if "삼성전자" in full_text: item["maker"] = "삼성전자"
            elif "LG전자" in full_text: item["maker"] = "LG전자"

        # Origin
        origin = get_best_value(all_specs, ["제조국", "원산지", "국가"], "")
        if origin: item["origin"] = origin

        # Model
        model = get_best_value(all_specs, ["모델명", "모델번호", "품명"], "")
        if not model:
            match = re.search(r"\(([A-Za-z0-9-]{5,})\)", item["name"])
            if match: model = match.group(1)
        if model: item["model"] = model

    except Exception as e:
        print(f"   ⚠️ 상세정보 분석 오류: {e}")

    print(f"   ✅ 수집: {item['name'][:10]}... (카테고리: {item['category'][:15]}...)")
    return item

def run_crawler():
    urls_to_crawl = TARGET_URLS
    results = []

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                done = set(i['url'] for i in saved)
                urls_to_crawl = [u for u in TARGET_URLS if u not in done]
                results = saved
                if urls_to_crawl: print(f"📂 기존 {len(saved)}개 유지. 신규 {len(urls_to_crawl)}개 시작.")
        except: pass

    if not urls_to_crawl:
        print("🎉 모든 URL 완료.")
        return

    chunk_size = RESTART_EVERY_N
    for i in range(0, len(urls_to_crawl), chunk_size):
        chunk = urls_to_crawl[i : i + chunk_size]
        kill_chrome()
        launch_chrome()
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0]
                page = context.new_page()
                
                for j, url in enumerate(chunk):
                    if (i + j) > 0 and (i + j) % BATCH_SLEEP_EVERY_N == 0:
                        print(f"\n☕ 휴식 {BATCH_SLEEP_DURATION}초...")
                        time.sleep(BATCH_SLEEP_DURATION)
                    
                    data = crawl_item(page, url)
                    if data:
                        results.append(data)
                        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=4)
                    
                    time.sleep(random.uniform(2, 5))
            except: continue

    print(f"\n🎉 완료. 총 {len(results)}개 저장.")

if __name__ == "__main__":
    run_crawler()