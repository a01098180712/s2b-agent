import time
import os
import subprocess
import requests
import re  # 정규표현식 모듈 추가
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

# ======================================================
# [설정]
# ======================================================
TEST_URL = "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026"
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
OUTPUT_FILENAME = "merged_detail_v26.jpg"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DIR = r"C:\ChromeDev"

# ======================================================
# [기능 1] 크롬 자동 실행
# ======================================================
def ensure_chrome_running():
    print(f"♻️ [System] Chrome 상태 점검...")
    try:
        requests.get(f"{CDP_URL}/json/version", timeout=1)
        print("    ✅ Chrome이 실행 중입니다.")
        return
    except:
        print("    ℹ️ Chrome 실행 시작...")

    if not os.path.exists(CHROME_PATH):
        print(f"    ❌ 오류: 크롬 경로 확인 필요: {CHROME_PATH}")
        return

    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DIR}",
        "--no-first-run",
        "--window-size=1920,1080"
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
    except Exception as e:
        print(f"    ❌ 실행 실패: {e}")

# ======================================================
# [기능 2] 이미지 병합
# ======================================================
def merge_images_vertical(image_urls):
    print(f"\n🧩 [Merger] 추출된 {len(image_urls)}장의 이미지 다운로드...")
    valid_images = []
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.coupang.com/"
    }
    
    for i, url in enumerate(image_urls):
        try:
            if url.startswith("//"): url = "https:" + url
            
            # 타임아웃 5초
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                
                # [필터링]
                # HTML 소스에서 긁어오면 아이콘이나 작은 장식 요소도 포함될 수 있으니
                # 크기 필터링을 반드시 해야 합니다.
                if img.width >= 300: 
                    valid_images.append(img)
                    print(f"   ✅ [확보] {url[-30:]} ({img.width}x{img.height})")
                else:
                    # print(f"   ❌ [탈락] 너무 작음: {img.width}x{img.height}")
                    pass
            else:
                print(f"   ⚠️ 다운로드 실패: {url}")
        except: pass

    if not valid_images:
        print("❌ 병합할 유효한 이미지가 없습니다.")
        return

    # 캔버스 생성
    max_width = max(img.width for img in valid_images)
    total_height = sum(img.height for img in valid_images)
    
    print(f"   📏 최종 캔버스: {max_width}x{total_height}px (총 {len(valid_images)}장)")
    
    merged_img = Image.new('RGB', (max_width, total_height), (255, 255, 255))
    y_offset = 0
    for img in valid_images:
        if img.width != max_width:
            new_height = int(img.height * (max_width / img.width))
            img = img.resize((max_width, new_height), Image.LANCZOS)
        
        merged_img.paste(img, (0, y_offset))
        y_offset += img.height

    merged_img.save(OUTPUT_FILENAME, quality=90)
    print(f"\n✅ [성공] 저장 완료: {OUTPUT_FILENAME}")

# ======================================================
# [메인] V26 로직 (HTML Raw String Parsing)
# ======================================================
def test_v26_html_parsing():
    print(f"🧪 [Test V26] HTML 원문 추출 및 정규식(Regex) 파싱")
    ensure_chrome_running()
    print(f"🔗 URL: {TEST_URL}")

    with sync_playwright() as p:
        try:
            print(f"🔌 Chrome 연결 중...")
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            if context.pages: page = context.pages[0]
            else: page = context.new_page()

            if TEST_URL not in page.url:
                page.goto(TEST_URL, wait_until="domcontentloaded")
                time.sleep(2)

            # 1. 버튼 클릭 (일단 내용은 로딩시켜야 함)
            print("    🔍 버튼 클릭 시도...")
            try:
                btn = page.locator(".product-detail-etc-view-btn, #productDetail button").first
                if btn.is_visible():
                    btn.click(force=True)
                    print("    🖱️ 버튼 클릭 완료 (3초 대기)")
                    time.sleep(3)
            except: pass

            # 2. 스크롤 (HTML 로딩 유도)
            print("    📜 HTML 데이터 확보를 위한 스크롤...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)") 
            time.sleep(2)

            # 3. [핵심] 상세 영역의 HTML 소스코드 전체를 문자열로 가져옴
            print("    📥 상세 영역 HTML 소스코드 추출 중...")
            
            # .product-detail-content-inside 영역의 HTML을 통째로 가져옵니다.
            # innerHTML은 현재 브라우저가 알고 있는 모든 태그 구조를 텍스트로 반환합니다.
            detail_html = page.evaluate("""() => {
                const container = document.querySelector('.product-detail-content-inside');
                return container ? container.innerHTML : "";
            }""")
            
            if not detail_html:
                # 만약 위 클래스가 없다면 vendorInventory 시도
                print("    ⚠️ 1차 영역 없음, 백업 영역(#vendorInventory) 시도...")
                detail_html = page.evaluate("""() => {
                    const container = document.querySelector('#vendorInventory');
                    return container ? container.innerHTML : "";
                }""")

            print(f"    📄 확보된 HTML 길이: {len(detail_html)}자")

            # 4. [Python] 정규표현식으로 이미지 URL 강제 추출
            # 패턴: http로 시작하고, 중간에 "나 ' 같은게 없고, jpg/png/gif 등으로 끝나는 문자열
            print("    🧬 정규식(Regex)으로 이미지 URL 발굴 중...")
            
            # 패턴 설명:
            # http[s]? : http 또는 https
            # :// : ://
            # [^"'\s<>]+ : 따옴표, 공백, 꺽쇠가 아닌 문자가 연속됨
            # \. : 점(.)
            # (?:jpg|jpeg|png|gif|bmp|webp) : 확장자 (그룹화하되 캡처 안 함)
            pattern = r'(https?://[^"\'\s<>]+\.(?:jpg|jpeg|png|gif|bmp|webp))'
            
            found_urls = re.findall(pattern, detail_html)
            
            # 중복 제거 및 필터링
            candidate_urls = []
            seen = set()
            
            for url in found_urls:
                # URL 정제 (가끔 쿼리스트링 등이 붙어있을 수 있음)
                clean_url = url.split('?')[0] # 물음표 뒤 제거 (선택사항, 일단 유지)
                
                # 쿠팡 CDN 도메인 확인 (외부 광고 제외 목적)
                if 'coupangcdn.com' in url or 'vendor_inventory' in url or 'retail' in url:
                    if url not in seen:
                        candidate_urls.append(url)
                        seen.add(url)
            
            print(f"    🔎 HTML 분석 결과: {len(candidate_urls)}개의 이미지 주소 발견!")
            
            # 5. 병합
            if candidate_urls:
                merge_images_vertical(candidate_urls)
            else:
                print("❌ HTML 소스 내에서 이미지 URL을 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 오류: {e}")

if __name__ == "__main__":
    test_v26_html_parsing()