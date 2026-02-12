import time
import os
import subprocess
import requests
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

# ======================================================
# [설정]
# ======================================================
TEST_URL = "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026"
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
OUTPUT_FILENAME = "merged_detail_v15.jpg"

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
# [기능 2] 이미지 병합 (정밀 검증)
# ======================================================
def merge_images_vertical(image_urls):
    print(f"\n🧩 [Merger] 수집된 {len(image_urls)}개의 URL 정밀 검증 중...")
    valid_images = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.coupang.com/"
    }
    
    for i, url in enumerate(image_urls):
        try:
            if url.startswith("//"): url = "https:" + url
            
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                
                # [Python 필터링]
                # 가로 400px 이상 & 세로 30px 이상 (본문 이미지 기준)
                if img.width >= 400 and img.height >= 30:
                    valid_images.append(img)
                    print(f"   ✅ [통과] {url[-30:]} ({img.width}x{img.height})")
                else:
                    # 너무 작은 이미지는 탈락 (아이콘 등)
                    pass 
            else:
                print(f"   ⚠️ 다운로드 실패({response.status_code}): {url[-30:]}")
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
# [메인] V15 로직 (좌표 기반 스마트 스캔)
# ======================================================
def test_v15_smart_scan():
    print(f"🧪 [Test V15] 좌표 기반 스마트 스캔 (컨테이너 무관)")
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

            # 1. 버튼 클릭 (여러 선택자 시도)
            print("    🔍 '더보기' 버튼 클릭 시도...")
            try:
                # 텍스트, 클래스 등 다양하게 시도
                btn = page.locator("text='상품정보 더보기'").or_(page.locator(".product-detail-etc-view-btn")).first
                if btn.is_visible():
                    btn.click(force=True)
                    print("    🖱️ 버튼 클릭 완료")
                    time.sleep(3)
                else:
                    print("    ℹ️ 버튼이 이미 눌렸거나 안 보입니다.")
            except: pass

            # 2. 스크롤 (로딩 유도)
            print("    📜 전체 스크롤 (이미지 로딩)...")
            page.evaluate("""async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 800;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if(totalHeight >= scrollHeight){
                            clearInterval(timer);
                            resolve();
                        }
                    }, 100);
                });
            }""")
            time.sleep(3)

            # 3. [핵심] 좌표 기반 이미지 수집 (Smart Scan)
            print("    📸 스마트 스캔 중 (본문 위치 이미지 선별)...")
            
            raw_urls = page.evaluate("""() => {
                const results = [];
                const imgs = document.querySelectorAll('img');
                
                // 화면 중앙 X좌표 계산 (반응형 대응)
                const viewportWidth = window.innerWidth;
                const centerX = viewportWidth / 2;
                
                imgs.forEach(img => {
                    const rect = img.getBoundingClientRect();
                    const src = img.getAttribute('src') || img.getAttribute('data-src');
                    
                    if(!src) return;
                    
                    // 1. 제외 키워드 (광고, 아이콘 등)
                    if(src.includes('blank.gif') || src.includes('icon') || src.includes('travel') || src.includes('banner')) return;
                    
                    // 2. 좌표 필터링 (가장 강력함!)
                    // - 이미지가 화면 중앙 영역에 걸쳐 있어야 함 (사이드바/배너 제외)
                    // - rect.left < centerX < rect.right
                    const isInCenter = (rect.left < centerX && rect.right > centerX);
                    
                    // - 너비가 300px 이상 (너무 작은 썸네일 제외)
                    const isWideEnough = (rect.width > 300 || img.naturalWidth > 300);
                    
                    if (isInCenter && isWideEnough) {
                        if(src.includes('http')) {
                            results.push(src);
                        }
                    }
                });
                return results;
            }""")

            # 중복 제거
            candidate_urls = []
            seen = set()
            for url in raw_urls:
                if url.startswith("//"): url = "https:" + url
                if url not in seen:
                    candidate_urls.append(url)
                    seen.add(url)
            
            print(f"    🔎 후보군 발견: {len(candidate_urls)}장 (위치/크기 통과)")
            
            # 4. 병합
            if candidate_urls:
                merge_images_vertical(candidate_urls)
            else:
                print("❌ 조건에 맞는 이미지를 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 오류: {e}")

if __name__ == "__main__":
    test_v15_smart_scan()
    