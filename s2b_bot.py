import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# 1. 환경 변수 로드
load_dotenv()

# ======================================================
# [설정]
# ======================================================
# ★ 실전 모드 설정 (False = 실제 등록 진행)
TEST_MODE = False 

S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'
DATA_FILE = 's2b_complete_data.json'
CATEGORY_FILE = 's2b_categories.json'

USER_ID = os.getenv("S2B_ID", "")
USER_PW = os.getenv("S2B_PW", "")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# [신규] 에스엔비몰 회사 소개 및 배송 안내 (고정 입력용)
COMPANY_INTRO_HTML = """
<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p style="font-size: 15pt; font-weight: bold; text-align: center;">【 에스엔비몰 】학교장터 전문 공급업체</p>
<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p style="font-size: 11pt;">에스엔비몰은 학교장터 전문 공급업체로, 학교 및 교육기관에 양질의 제품을 공급하고 있습니다.</p>
<p>&nbsp;</p> <br>
<p style="font-size: 15pt; font-weight: bold;">▣ 우리의 약속</p>
<p style="font-size: 11pt;"> ✓ 신속하고 안전한 배송을 약속드립니다<br> ✓ 불량 상품은 무료 교환/반품 처리를 원칙으로 합니다<br> ✓ 대량 구매 시 할인 혜택이 있습니다</p>
<p>&nbsp;</p> <br>
<p style="font-size: 15pt; font-weight: bold;">▣ 문의 안내</p>
<p style="font-size: 11pt;">궁금하신 사항은 언제든지 문의해 주세요.<br>성실히 답변 드리겠습니다.</p>
<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
"""

# ======================================================
# [핵심] 데이터 로드 및 유틸리티
# ======================================================
def load_category_data():
    """s2b_categories.json 파일 로드"""
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CATEGORY_FILE)
    if not os.path.exists(file_path):
        print(f"⚠️ 경고: 카테고리 파일({CATEGORY_FILE})이 없습니다.")
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print("📂 카테고리 데이터 로드 완료")
            return json.load(f)
    except Exception as e:
        print(f"❌ 카테고리 로드 실패: {e}")
        return {}

def find_category_codes(categories, product_name):
    """상품명을 분석하여 카테고리 코드(대/중/소) 찾기"""
    if not categories: return None, None, None

    # 1. 소분류(3차) 검색
    for parent_key, items in categories.items():
        if '_' in parent_key: 
            for item in items:
                if item['text'] in product_name:
                    cat1, cat2 = parent_key.split('_')
                    print(f"  🔍 매칭 성공(3차): {item['text']}")
                    return cat1, cat2, item['value']

    # 2. 중분류(2차) 검색
    for parent_key, items in categories.items():
        if parent_key != 'category1' and '_' not in parent_key and parent_key.isdigit():
            for item in items:
                if item['text'] in product_name:
                    print(f"  🔍 매칭 성공(2차): {item['text']}")
                    return parent_key, item['value'], None

    # 3. 대분류(1차) 검색
    if 'category1' in categories:
        for item in categories['category1']:
            if item['text'] in product_name:
                print(f"  🔍 매칭 성공(1차): {item['text']}")
                return item['value'], None, None

    return None, None, None

def handle_popups_safely(context, main_page):
    """메인 외의 모든 팝업 닫기"""
    try:
        time.sleep(1)
        all_pages = context.pages
        if len(all_pages) <= 1: return
        for p in all_pages:
            if p != main_page:
                try:
                    if not p.is_closed(): p.close()
                except: pass
    except: pass

def handle_post_upload_popup(context):
    """이미지 업로드 직후 팝업 처리"""
    print("    ⏳ 이미지 팝업 감지 중...")
    for _ in range(4):
        time.sleep(0.5)
        for p in context.pages:
            if "preview" in p.url.lower() or "pop" in p.url.lower():
                try:
                    if not p.is_closed():
                        print(f"    🗑️ 이미지 팝업 닫기: {p.url[:30]}...")
                        p.close()
                        return
                except: pass

def load_products():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

# ======================================================
# [기능] 등록 단계별 함수들
# ======================================================
def register_categories(page, product, categories):
    print(f"\n  📂 [{product.get('물품명')}] 카테고리 설정...")
    
    c1 = product.get('카테고리1_코드')
    c2 = product.get('카테고리2_코드')
    c3 = product.get('카테고리3_코드')
    
    if not c1:
        c1, c2, c3 = find_category_codes(categories, product.get('물품명', ''))

    if not c1:
        print("    ⚠️ 매칭 실패: 카테고리 코드를 찾을 수 없습니다.")
        return

    try:
        # 1차
        page.select_option('select[name="f_category_code1"]', value=c1)
        time.sleep(1.5) 

        # 2차
        if c2:
            try:
                page.wait_for_function(
                    "document.querySelector('select[name=\"f_category_code2\"]').options.length > 1",
                    timeout=5000
                )
            except: pass
            time.sleep(0.5)
            page.select_option('select[name="f_category_code2"]', value=c2)
            time.sleep(1.5)

            # 3차
            if c3:
                try:
                    page.wait_for_function(
                        "document.querySelector('select[name=\"f_category_code3\"]').options.length > 1",
                        timeout=5000
                    )
                except: pass
                time.sleep(0.5)
                page.select_option('select[name="f_category_code3"]', value=c3)
                time.sleep(0.5)
        print("    ✅ 카테고리 설정 완료")

    except Exception as e:
        print(f"    ❌ 카테고리 선택 중 오류: {e}")

def register_images(context, page, product):
    print("  🖼️ 이미지 업로드 처리...")
    img1_path = product.get('기본이미지1', '')
    if img1_path and os.path.exists(img1_path):
        try:
            page.set_input_files('input[name="f_img1_file"]', img1_path)
            handle_post_upload_popup(context)
            print("    ✅ 기본이미지 완료")
        except: print("    ❌ 기본이미지 실패")

    time.sleep(1) 
    detail_img_path = product.get('상세이미지', '')
    if detail_img_path and os.path.exists(detail_img_path):
        try:
            page.set_input_files('input[name="f_goods_explain_img_file"]', detail_img_path)
            handle_post_upload_popup(context)
            print("    ✅ 상세이미지 완료")
        except: print("    ❌ 상세이미지 실패")

def register_smart_editor(page, html_content):
    print("  📝 상세설명(회사소개) 입력 중...")
    try:
        iframe_element = page.wait_for_selector('iframe[src*="SmartEditor2Skin"]', timeout=10000)
        frame = iframe_element.content_frame()
        if frame:
            time.sleep(1)
            html_btn = frame.locator('.se2_to_html')
            if html_btn.is_visible():
                html_btn.click()
                time.sleep(0.5)
                # HTML 직접 주입
                frame.locator('.se2_input_htmlsrc').fill(html_content)
                frame.locator('.se2_to_editor').click()
                print("    ✅ 회사소개 문구 주입 성공")
    except Exception as e:
        print(f"    ❌ 에디터 입력 실패: {e}")

def register_delivery_info(page, product):
    print("  🚚 배송/기타 정보 입력...")
    try:
        page.click('input[name="f_delivery_fee_kind"][value="1"]') # 무료
        page.click('input[name="f_delivery_method"][value="1"]')   # 택배
        page.click('input[name="delivery_area"][value="1"]')      # 전국
        page.click('input[name="f_delivery_group_yn"][value="N"]') # 합배송불가
        page.select_option('select[name="f_tax_method"]', '1')    # 과세
        page.select_option('select[name="f_delivery_limit"]', 'ZD000004') # 15일
        
        for kc in ['kids', 'elec', 'daily', 'broadcasting']:
            page.click(f'input[name="{kc}KcUseGubunChk"][value="N"]')
        print("    ✅ 배송/인증 완료")
    except: pass

def submit_product(page):
    print("\n  💾 [최종 저장] 버튼 클릭 시도...")
    page.on("dialog", lambda dialog: dialog.accept())
    try:
        save_btn = page.locator("a[href*=\"javascript:register('1')\"]")
        if save_btn.is_visible():
            save_btn.click()
            print("    👉 저장 버튼 클릭함 (Dialog 자동 수락)")
        else:
            print("    👉 버튼 못 찾음, JS 직접 실행 시도...")
            page.evaluate("register('1')")
        print("    ⏳ 저장 처리 대기 중 (5초)...")
        time.sleep(5)
    except Exception as e:
        print(f"    ❌ 저장 처리 중 오류: {e}")

# ======================================================
# [메인] 봇 실행
# ======================================================
def run_s2b_bot():
    print(">>> [S2B_Agent] 봇을 시작합니다 (실전 모드)...")
    
    categories = load_category_data()
    products = load_products()
    
    if not products:
        print("!!! 데이터 파일이 비어있거나 없습니다.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        print(f">>> 로그인 페이지 이동: {S2B_LOGIN_URL}")
        page = context.new_page()
        
        try:
            # 1. 로그인
            page.goto(S2B_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector('form[name="vendor_loginForm"] [name="uid"]', state="visible", timeout=30000)
            page.fill('form[name="vendor_loginForm"] [name="uid"]', USER_ID)
            page.fill('form[name="vendor_loginForm"] [name="pwd"]', USER_PW)
            page.click('form[name="vendor_loginForm"] .btn_login > a')
            handle_popups_safely(context, page)

            # 2. 상품 등록 루프
            for i, product in enumerate(products):
                print(f"\n>>> [상품 {i+1}/{len(products)}] 등록 시작")
                
                # 등록 페이지 이동
                try: page.goto(S2B_REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
                except: pass
                time.sleep(2)
                handle_popups_safely(context, page)
                
                try: 
                    if page.locator(".btn_popclose").first.is_visible():
                        page.locator(".btn_popclose").first.click()
                except: pass

                page.wait_for_selector('input[name="f_goods_name"]', state="visible", timeout=30000)

                # [1] 카테고리
                register_categories(page, product, categories)
                
                # ★ 테스트 모드면 여기서 멈춤
                if TEST_MODE:
                    print("👀 [테스트 모드] 카테고리 확인 후 건너뜁니다.")
                    time.sleep(3)
                    continue

                # [2] 이미지
                register_images(context, page, product)

                # [3] 기본 텍스트 입력
                if product.get('물품명'): page.fill('input[name="f_goods_name"]', product['물품명'])
                if product.get('규격'): page.fill('input[name="f_size"]', product['규격'])
                
                model_name = product.get('모델명', '')
                if model_name and model_name != '없음':
                    page.click('input[name="f_model_yn"][value="N"]')
                    page.fill('input[name="f_model"]', model_name)
                else:
                    page.click('input[name="f_model_yn"][value="Y"]')

                if product.get('제조사명'): page.fill('input[name="f_factory"]', product['제조사명'])
                
                price = str(product.get('제시금액', '0'))
                page.fill('input[name="f_estimate_amt"]', price)
                page.fill('input[name="f_remain_qnt"]', '999')

                # [4] 배송/인증 정보
                register_delivery_info(page, product)
                
                # [5] 스마트 에디터 (회사소개 고정 문구 입력)
                register_smart_editor(page, COMPANY_INTRO_HTML)

                # 청렴계약서 체크
                try:
                    chk = page.locator('#uprightContract')
                    if chk.is_visible() and not chk.is_checked():
                        chk.check()
                except: pass

                # [6] 최종 저장 (활성화됨)
                submit_product(page)

                print(f">>> ✅ [상품 {i+1}] 처리 완료.")

        except Exception as e:
            print(f"!!! 에러 발생: {e}")
        finally:
            print(">>> 작업을 종료합니다.")
            browser.close()

if __name__ == "__main__":
    run_s2b_bot()