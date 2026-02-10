import json
import time
import os
import subprocess
import random
import re # [추가] 정규표현식 사용
from playwright.sync_api import sync_playwright

# ======================================================
# [설정] 크롤링 타겟 및 운영 정책
# ======================================================
TARGET_URLS = [
    "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026&q=%EC%A0%84%EC%9E%90%EB%A0%88%EC%9D%B8%EC%A7%80&searchId=d027098a15810727&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg787wn",
    "https://www.coupang.com/vp/products/7249246657?itemId=18436391484&vendorItemId=92006548412&q=%EC%84%A0%ED%92%8D%EA%B8%B0&searchId=c4876bb75295792&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg78m1r",
    "https://www.coupang.com/vp/products/6359373947?itemId=13418949659&vendorItemId=92995378125&q=%EB%85%B8%ED%8A%B8%EB%B6%81&searchId=e154f8483813228&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg7936e",
    # ... 추가 URL
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
    """
    페이지 내의 모든 테이블과 스펙 리스트를 딕셔너리로 통합 추출
    """
    info_dict = {}
    
    # 1. 모든 테이블 스캔 (표 형태 정보)
    try:
        rows = page.locator("table tr").all()
        for row in rows:
            try:
                # th-td 구조 또는 td-td 구조 모두 대응
                texts = row.locator("th, td").all_inner_texts()
                if len(texts) >= 2:
                    key = texts[0].strip()
                    val = texts[1].strip()
                    if key and val:
                        info_dict[key] = val
            except: continue
    except: pass

    # 2. 상단 스펙 리스트 (ul > li 형태)
    try:
        items = page.locator("ul.prod-description-attribute > li").all_inner_texts()
        for item in items:
            if ":" in item:
                parts = item.split(":", 1)
                info_dict[parts[0].strip()] = parts[1].strip()
    except: pass
    
    return info_dict

def extract_kc_by_regex(text):
    """
    페이지 전체 텍스트에서 KC 인증 번호 패턴을 찾아냄
    패턴 예: HU07445-11007Z, MSIP-REI-SEC-ECOSOLO, R-R-Kp1-...
    """
    patterns = [
        r"[A-Z]{2}[0-9]{4,5}-[0-9]{4,5}[A-Z]?",  # 안전인증 (예: HU07445-11007Z)
        r"[A-Z]{2,4}-[A-Z]{3}-[A-Z]{3}-[\w]+",   # 전자파 적합성 (예: MSIP-REI-...)
        r"R-R-[\w]+-[\w]+"                       # 방송통신 (예: R-R-SEC-...)
    ]
    
    found = set()
    for pat in patterns:
        matches = re.findall(pat, text)
        for m in matches:
            found.add(m)
            
    return " / ".join(list(found))

def get_best_value(info_dict, keywords, default_val=""):
    """딕셔너리에서 키워드 매칭 (상세설명참조 제외)"""
    for key, val in info_dict.items():
        if any(kw in key for kw in keywords):
            # '상세설명'이나 '참조'가 들어간 무의미한 값은 무시
            if val and "상세" not in val and "참조" not in val:
                return val
    return default_val

def crawl_item(page, url):
    print(f"▶ 이동: {url[:60]}...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=5000)
    except: pass 

    # [1] 기본 정보 (JSON-LD 우선)
    item = {
        "url": url, "name": "N/A", "price": 0, "image": "", 
        "kc": "상세설명참조", "maker": "협력업체", "origin": "중국", "model": "없음"
    }

    try:
        # 성인인증 페이지 체크
        if "/login/" in page.url:
            print("    ⚠️ 로그인 필요 페이지 -> 건너뜀")
            return None

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

    # [2] 정밀 스펙 추출 (New Logic)
    try:
        # 페이지 전체 텍스트 확보 (Regex용)
        full_text = page.locator("body").inner_text()
        
        # 모든 테이블/스펙 정보 딕셔너리화
        all_specs = extract_all_specs(page)
        
        # 1. KC 인증 (Regex + Table 조합)
        kc_from_table = get_best_value(all_specs, ["인증", "허가", "신고", "KC"], "")
        kc_from_regex = extract_kc_by_regex(full_text) # 정규식으로 페이지 전체 스캔
        
        # 정규식 결과를 우선하되, 테이블 정보도 병합
        kc_combined = set()
        if kc_from_regex: kc_combined.update(kc_from_regex.split(" / "))
        if kc_from_table: kc_combined.add(kc_from_table)
        
        if kc_combined:
            # '상세설명참조' 같은 쓰레기 데이터 제거
            clean_kc = [k for k in kc_combined if "상세" not in k and "참조" not in k]
            if clean_kc: item["kc"] = " / ".join(clean_kc)

        # 2. 제조사 (우선순위: 삼성/LG 등 브랜드 > 협력업체)
        maker = get_best_value(all_specs, ["제조자", "수입자", "판매업자", "제조사"], "")
        # 제조사에 '삼성', 'LG' 등이 포함되면 그 값을 살림. 없으면 협력업체.
        if maker: item["maker"] = maker
        else:
            # 텍스트에서 '삼성전자' 같은 브랜드가 보이면 추출 시도 (간단 예시)
            if "삼성전자" in full_text: item["maker"] = "삼성전자"
            elif "LG전자" in full_text: item["maker"] = "LG전자"

        # 3. 원산지
        origin = get_best_value(all_specs, ["제조국", "원산지", "국가"], "")
        if origin: item["origin"] = origin

        # 4. 모델명 (테이블 > 제목 > Regex)
        model = get_best_value(all_specs, ["모델명", "모델번호", "품명"], "")
        if not model:
            # 제목에 모델명이 있는 경우가 많음 (예: ... 다이얼식 23L (MS23C...))
            # 괄호 안의 영문+숫자 패턴 시도
            match = re.search(r"\(([A-Za-z0-9-]{5,})\)", item["name"])
            if match: model = match.group(1)
        
        if model: item["model"] = model

    except Exception as e:
        print(f"   ⚠️ 상세정보 정밀 분석 중 오류: {e}")

    print(f"   ✅ 수집 완료: {item['name'][:10]}... (모델:{item['model']} / KC:{item['kc'][:15]}...)")
    return item

# ======================================================
# [실행] 메인 루프
# ======================================================
def run_crawler():
    urls_to_crawl = TARGET_URLS
    results = []

    if os.path.exists(OUTPUT_FILE):
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
                crawled_urls = set(item['url'] for item in saved_data)
                urls_to_crawl = [u for u in TARGET_URLS if u not in crawled_urls]
                results = saved_data
                if urls_to_crawl:
                    print(f"📂 기존 데이터 {len(saved_data)}개 확인. 신규 {len(urls_to_crawl)}개 수집 시작.")
        except: pass

    if not urls_to_crawl:
        print("🎉 모든 URL이 이미 수집되었습니다.")
        return

    total_count = len(urls_to_crawl)
    
    for i in range(0, total_count, RESTART_EVERY_N):
        chunk = urls_to_crawl[i : i + RESTART_EVERY_N]
        
        kill_chrome()
        launch_chrome()
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                context = browser.contexts[0]
                page = context.new_page()
                
                for j, url in enumerate(chunk):
                    global_idx = i + j + 1
                    
                    if global_idx > 1 and (global_idx - 1) % BATCH_SLEEP_EVERY_N == 0:
                        print(f"\n☕ [Break] {BATCH_SLEEP_EVERY_N}개 수집 완료. {BATCH_SLEEP_DURATION}초 휴식...")
                        time.sleep(BATCH_SLEEP_DURATION)
                    
                    data = crawl_item(page, url)
                    if data:
                        results.append(data)
                        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                            json.dump(results, f, ensure_ascii=False, indent=4)
                    
                    time.sleep(random.uniform(2, 5))

            except Exception as e:
                print(f"❌ 브라우저 연결/실행 중 오류: {e}")
                continue

    print(f"\n🎉 전체 작업 완료! 총 {len(results)}개 저장됨: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_crawler()