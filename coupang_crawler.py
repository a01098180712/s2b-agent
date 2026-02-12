import json
import time
import os
import subprocess
import random
import re
from playwright.sync_api import sync_playwright

# [NEW] S2B 데이터 보강 모듈 임포트
from data_enricher import S2B_Enricher 

# ======================================================
# [설정] 크롤링 타겟 및 운영 정책
# ======================================================
TARGET_URLS = [
    "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026&q=%EC%A0%84%EC%9E%90%EB%A0%88%EC%9D%B8%EC%A7%80&searchId=d027098a15810727&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg787wn",
    "https://www.coupang.com/vp/products/7249246657?itemId=18436391484&vendorItemId=92006548412&q=%EC%84%A0%ED%92%8D%EA%B8%B0&searchId=c4876bb75295792&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg78m1r",
    "coupang.com/vp/products/8036829511?itemId=23843669090&vendorItemId=90869617914&q=삼성%20노트북&searchId=a93c62df4465418&sourceType=search&itemsCount=36&searchRank=1&rank=1&traceId=mlj3nf0o"
    # ... 필요한 URL 계속 추가
]

OUTPUT_FILE = 's2b_results.json'
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

# [환경] 크롬 경로
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DIR = r"C:\ChromeDev"

# [정책] 안정성 설정
RESTART_EVERY_N = 50      
BATCH_SLEEP_EVERY_N = 10 
BATCH_SLEEP_DURATION = 60 

# ======================================================
# [모듈 1] 브라우저 생명주기 관리
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
    except Exception as e:
        print(f"    ❌ Chrome 실행 실패: {e}")
        return False

def kill_chrome():
    print("♻️ [System] 메모리 초기화를 위해 Chrome 재시작 준비...")
    try:
        subprocess.run(
            'wmic process where "name=\'chrome.exe\' and commandline like \'%ChromeDev%\'" call terminate',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    except: pass

# ======================================================
# [모듈 2] 데이터 정밀 추출기 (Regex & All-Table Scan)
# ======================================================
def extract_all_specs(page):
    info_dict = {}
    try:
        rows = page.locator("table tr").all()
        for row in rows:
            try:
                texts = row.locator("th, td").all_inner_texts()
                if len(texts) >= 2:
                    key = texts[0].strip()
                    val = texts[1].strip()
                    if key and val:
                        info_dict[key] = val
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
        matches = re.findall(pat, text)
        for m in matches:
            found.add(m)
    return " / ".join(list(found))

def get_best_value(info_dict, keywords, default_val=""):
    for key, val in info_dict.items():
        if any(kw in key for kw in keywords):
            if val and "상세" not in val and "참조" not in val:
                return val
    return default_val

# [NEW] 상세 이미지 추출 함수 (버튼 클릭 + 스크롤)
def get_detail_images_with_scroll(page):
    print("    📜 [System] 상세 이미지 확보 시작...")
    
    # 1. '상품정보 더보기' 버튼 클릭
    try:
        more_btns = page.locator("button, a").filter(has_text=re.compile(r"상품정보|더보기|펼치기")).all()
        clicked = False
        for btn in more_btns:
            if btn.is_visible():
                btn.click(force=True)
                clicked = True
                break
        if clicked:
            print("    🖱️ '상품정보 더보기' 버튼 클릭 성공")
            time.sleep(2)
    except: pass

    # 2. 스크롤 다운 (Lazy Loading 유도)
    try:
        page.evaluate("""async () => {
            await new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 300;
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if(totalHeight >= scrollHeight || totalHeight > 30000){
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")
        time.sleep(2)
    except: pass

    # 3. 이미지 URL 추출
    detail_images = []
    try:
        # 주요 컨테이너 탐색
        containers = page.locator("#productDetail, .product-detail-content-border, #vendorInventory").all()
        if not containers:
            # 컨테이너를 못 찾으면 바디 전체에서 검색 (차선책)
            containers = [page.locator("body")]

        for cont in containers:
            imgs = cont.locator("img").all()
            for img in imgs:
                src = img.get_attribute("src") or img.get_attribute("data-src")
                if src and "http" in src and ".gif" not in src and "blank" not in src:
                    if src not in detail_images:
                        detail_images.append(src)
    except Exception as e:
        print(f"    ⚠️ 이미지 추출 중 에러: {e}")
        
    return detail_images

# ======================================================
# [핵심] 크롤링 로직 (Phase 1 전용)
# ======================================================
def crawl_item(page, url): 
    print(f"▶ 이동: {url[:60]}...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=10000)
    except: pass 

    item = {
        "url": url, "name": "N/A", "price": 0, "image": "", 
        "kc": "상세설명참조", "maker": "협력업체", "origin": "중국", "model": "",
        "g2b_code": "", "category": "기타",
        "detail_images": [] 
    }

    try:
        if "/login/" in page.url:
            print("    ⚠️ 로그인 필요 페이지 -> 건너뜀")
            return None

        # JSON-LD 파싱
        try:
            json_data = page.locator('script[type="application/ld+json"]').first.inner_text()
            data = json.loads(json_data)
            if isinstance(data, list): data = data[0]
            item["name"] = data.get("name", "N/A")
            item["image"] = data.get("image", "")
            if isinstance(item["image"], list): item["image"] = item["image"][0]
            offers = data.get("offers", {})
            if isinstance(offers, list): offers = offers[0]
            item["price"] = int(offers.get("price", 0))
        except: pass

        content = page.content()
        if "무료배송" not in content: item["price"] += 3000

        # [NEW] 상세 이미지 추출 실행
        item["detail_images"] = get_detail_images_with_scroll(page)
        print(f"    📸 상세 이미지 {len(item['detail_images'])}장 확보")

        # 정밀 스펙 추출
        full_text = page.locator("body").inner_text()
        all_specs = extract_all_specs(page)
        
        model = get_best_value(all_specs, ["모델명", "모델번호", "품명"], "")
        if not model:
            match = re.search(r"\(([A-Za-z0-9-]{5,})\)", item["name"])
            if match: model = match.group(1)
        item["model"] = model

        item["maker"] = get_best_value(all_specs, ["제조자", "수입자", "판매업자", "제조사"], "협력업체")
        item["origin"] = get_best_value(all_specs, ["제조국", "원산지", "국가"], "중국")

        kc_regex = extract_kc_by_regex(full_text)
        if kc_regex: item["kc"] = kc_regex

    except Exception as e:
        print(f"   ⚠️ 파싱 에러: {e}")
        return None

    print(f"   ✅ 쿠팡 수집 완료: {item['name'][:10]}... | 모델:{item['model']}")
    return item

# ======================================================
# [실행] 메인 루프 (Phase 1 & Phase 2)
# ======================================================
def run_crawler():
    # --------------------------------------------------
    # [PHASE 1] 쿠팡 상품 정보 수집 (Playwright Context 1)
    # --------------------------------------------------
    print("\n🚀 [PHASE 1] 쿠팡 상품 정보 수집 시작...")
    
    urls_to_crawl = TARGET_URLS
    results = []

    # 기존 데이터 로드
    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                crawled_urls = set(item['url'] for item in saved_data)
                urls_to_crawl = [u for u in TARGET_URLS if u not in crawled_urls]
                results = saved_data
        except: pass

    if urls_to_crawl:
        kill_chrome()
        launch_chrome()
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0]
                page = context.new_page()
                
                for i, url in enumerate(urls_to_crawl):
                    print(f"\n[{i+1}/{len(urls_to_crawl)}] 처리 중...")
                    data = crawl_item(page, url) 
                    
                    if data:
                        results.append(data)
                        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=4)
                    
                    time.sleep(random.uniform(2, 4))
            except Exception as e:
                print(f"❌ Phase 1 에러: {e}")
            finally:
                try: context.close()
                except: pass
                try: browser.close()
                except: pass
        
        kill_chrome() # 브라우저 완전 종료 (리소스 해제)
        print("✅ [PHASE 1] 쿠팡 수집 완료. 브라우저 종료됨.\n")
    else:
        print("🎉 신규 수집할 URL이 없습니다. Phase 2로 넘어갑니다.\n")

    # --------------------------------------------------
    # [PHASE 2] S2B 데이터 보강 (Playwright Context 2)
    # --------------------------------------------------
    print("🚀 [PHASE 2] S2B 데이터 보강(Enrichment) 시작...")
    
    # S2B Enricher 초기화 (새로운 브라우저 세션 시작)
    enricher = S2B_Enricher() 
    
    # 최신 데이터 다시 로드
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
    else:
        print("❌ 처리할 데이터 파일이 없습니다.")
        return

    updated_count = 0
    for idx, item in enumerate(current_data):
        # 모델명이 있고 아직 G2B 코드가 없는 경우에만 S2B 검색 시도
        if item.get("model") and len(item["model"]) > 3 and not item.get("g2b_code"):
            
            print(f"🔹 [{idx+1}/{len(current_data)}] S2B 검색: {item['model']}")
            s2b_data = enricher.fetch_s2b_details(item["model"])
            
            if s2b_data:
                print("    🎉 매칭 성공! 데이터 병합 중...")
                # S2B 데이터 우선 적용 (Golden Key)
                if s2b_data["category"]: item["category"] = s2b_data["category"]
                if s2b_data["manufacturer"]: item["maker"] = s2b_data["manufacturer"]
                if s2b_data["origin"]: item["origin"] = s2b_data["origin"]
                if s2b_data["g2b_code"]: item["g2b_code"] = s2b_data["g2b_code"]
                
                # KC 정보 병합
                s2b_kc_strs = [f"{k['category']}:{k['code']}" for k in s2b_data["kc_list"]]
                if s2b_kc_strs:
                    current_kc = item["kc"].split(" / ") if item["kc"] != "상세설명참조" else []
                    combined = list(set(current_kc + s2b_kc_strs))
                    item["kc"] = " / ".join(combined)
                
                updated_count += 1
            else:
                print("    ⚠️ 매칭 실패. 기존 데이터 유지.")
            
            # 중간 저장 (데이터 보호)
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, ensure_ascii=False, indent=4)
            
            time.sleep(1) # S2B 서버 부하 방지
        else:
            print(f"    Pass: 모델명 없음 or 이미 완료됨 ({item.get('name')[:10]}...)")

    print(f"\n🎉 전체 작업 종료! 총 {len(current_data)}개 중 {updated_count}개 보강됨.")

if __name__ == "__main__":
    run_crawler()