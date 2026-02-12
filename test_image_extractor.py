import time
import requests
from io import BytesIO
from PIL import Image
from playwright.sync_api import sync_playwright

# 테스트할 URL
TEST_URL = "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026"
CDP_URL = "http://127.0.0.1:9222"
OUTPUT_FILENAME = "test_merged_result.jpg"

def merge_images_vertical(image_urls):
    """
    URL 리스트를 받아 다운로드 후 세로로 긴 하나의 이미지로 병합합니다.
    """
    print(f"\n🧩 [Merger] {len(image_urls)}개의 조각 이미지를 병합합니다...")
    
    images = []
    
    # 1. 이미지 다운로드
    for i, url in enumerate(image_urls):
        try:
            # 프로토콜 처리 (//로 시작하는 경우 https 붙임)
            if url.startswith("//"): url = "https:" + url
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content)).convert("RGB")
                images.append(img)
                print(f"   ⬇️ 다운로드 성공 [{i+1}/{len(image_urls)}]: {url[:60]}...")
            else:
                print(f"   ❌ 다운로드 실패: {url}")
        except Exception as e:
            print(f"   ⚠️ 에러 발생: {e}")

    if not images:
        print("❌ 병합할 이미지가 없습니다.")
        return

    # 2. 캔버스 크기 계산 (폭은 최대값, 높이는 합산)
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)
    
    print(f"   📏 최종 이미지 크기: {max_width}x{total_height}px")

    # 3. 캔버스 생성 및 붙이기
    merged_img = Image.new('RGB', (max_width, total_height), (255, 255, 255))
    y_offset = 0
    for img in images:
        # 폭이 다르면 중앙 정렬 또는 좌측 정렬 (여기선 좌측)
        # 만약 리사이징이 필요하면: img = img.resize((max_width, int(img.height * max_width / img.width)))
        merged_img.paste(img, (0, y_offset))
        y_offset += img.height

    # 4. 저장
    merged_img.save(OUTPUT_FILENAME, quality=90)
    print(f"\n✅ [Success] 병합 완료! 파일을 확인하세요: {OUTPUT_FILENAME}")
    print(f"   (이 파일이 S2B에 등록될 최종 결과물입니다)")


def test_image_extraction_and_merge():
    print(f"🧪 [Test V8] 상세 이미지 추출 및 병합(Merge) 테스트")
    print(f"🔗 URL: {TEST_URL}")

    # 크롬이 켜져있다고 가정 (CDP 연결)
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            if context.pages: page = context.pages[0]
            else: page = context.new_page()

            if TEST_URL not in page.url:
                page.goto(TEST_URL, wait_until="domcontentloaded")
                time.sleep(2)

            # ---------------------------------------------------------
            # [Step 1] 버튼 클릭 및 스크롤 (V7 로직)
            # ---------------------------------------------------------
            print("    🔍 '상품정보 더보기' 버튼 클릭 시도...")
            clicked = False
            try:
                # 텍스트 또는 클래스로 버튼 찾기
                btn = page.locator("text='상품정보 더보기'").or_(page.locator(".product-detail-etc-view-btn")).first
                if btn.is_visible():
                    btn.click(force=True)
                    clicked = True
                    print("    🖱️ 버튼 클릭 완료. 3초 대기...")
                    time.sleep(3)
            except: pass
            
            # 스크롤 다운
            print("    📜 이미지 로딩 스크롤 진행 중...")
            page.evaluate("""async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 800;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if(totalHeight >= scrollHeight || totalHeight > 50000){
                            clearInterval(timer);
                            resolve();
                        }
                    }, 50);
                });
            }""")
            time.sleep(2)

            # ---------------------------------------------------------
            # [Step 2] 이미지 URL 수집 (정밀 타겟팅)
            # ---------------------------------------------------------
            print("    📸 이미지 URL 수집 중...")
            detail_images = []
            
            # 1순위: 판매자 직접 등록 이미지 (#vendorInventory) - 보통 이것만 있으면 됨
            # 2순위: 기본 상세 설명 (#productDetail)
            target_ids = ["#vendorInventory", "#productDetail", ".product-detail-content-border"]
            
            for target in target_ids:
                if page.locator(target).count() > 0:
                    # 해당 영역 안의 이미지들
                    imgs = page.locator(f"{target} img").all()
                    print(f"       👉 [{target}] 영역에서 {len(imgs)}개 발견")
                    
                    for img in imgs:
                        src = img.get_attribute("src") or img.get_attribute("data-src")
                        if src and "http" in src:
                            # 썸네일/아이콘/로고 등 노이즈 제거
                            if any(x in src for x in ["blank.gif", "icon", "logo", "rating", "badge"]): continue
                            
                            # (중요) 'thumbnail'이 포함되어 있더라도 vendor_inventory 경로는 실제 이미지일 수 있음.
                            # 하지만 너무 작은 썸네일(60x60 등)은 걸러야 함.
                            # 일단 다 수집하고 병합 단계에서 눈으로 확인
                            
                            if src not in detail_images:
                                detail_images.append(src)

            # 비상 대책: 컨테이너에서 못 찾았으면 전체에서 'vendor_inventory' 키워드 검색
            if not detail_images:
                print("    ⚠️ 컨테이너 추출 실패. 비상 검색 가동...")
                all_imgs = page.locator("img").all()
                for img in all_imgs:
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src and "vendor_inventory" in src and src not in detail_images:
                        detail_images.append(src)

            print(f"\n📊 추출된 조각 이미지: {len(detail_images)}장")

            # ---------------------------------------------------------
            # [Step 3] 이미지 병합 및 저장
            # ---------------------------------------------------------
            if detail_images:
                merge_images_vertical(detail_images)
            else:
                print("❌ 병합할 이미지가 없습니다.")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    test_image_extraction_and_merge()