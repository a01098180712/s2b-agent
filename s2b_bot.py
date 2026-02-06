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
S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'
DATA_FILE = 's2b_complete_data.json'
CATEGORY_FILE = 's2b_categories.json'

USER_ID = os.getenv("S2B_ID", "")
USER_PW = os.getenv("S2B_PW", "")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# ======================================================
# [핵심] 카테고리 데이터 로드 및 검색
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
    if not categories:
        return None, None, None

    # 1. 소분류(3차) 검색 (가장 정확)
    for parent_key, items in categories.items():
        if '_' in parent_key: 
            for item in items:
                if item['text'] in product_name:
                    cat1, cat2 = parent_key.split('_')
                    print(f"  🔍 매칭 성공(소분류): {item['text']}")
                    return cat1, cat2, item['value']

    # 2. 중분류(2차) 검색
    for parent_key, items in categories.items():
        if parent_key != 'category1' and '_' not in parent_key and parent_key.isdigit():
            for item in items:
                if item['text'] in product_name:
                    print(f"  🔍 매칭 성공(중분류): {item['text']}")
                    return parent_key, item['value'], None

    # 3. 대분류(1차) 검색
    if 'category1' in categories:
        for item in categories['category1']:
            if item['text'] in product_name:
                print(f"  🔍 매칭 성공(대분류): {item['text']}")
                return item['value'], None, None

    return None, None, None

# ======================================================
# [기능] 봇 유틸리티
# ======================================================
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

def load_first_product():
    if not os.path.exists(DATA_FILE): return None
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data[0] if data else None
    except: return None

# ======================================================
# [수정됨] 카테고리 등록 (upload.js 로직 적용)
# ======================================================
def register_categories(page, product, categories):
    """
    upload.js의 로직을 Playwright로 이식
    (순차적 선택 및 options.length 대기 로직 적용)
    """
    print("  📂 카테고리 선택 시작...")
    
    # 1. 코드가 데이터에 이미 있으면 사용, 없으면 이름으로 찾기
    c1 = product.get('카테고리1_코드')
    c2 = product.get('카테고리2_코드')
    c3 = product.get('카테고리3_코드')
    
    if not c1:
        # 데이터에 코드가 없으면 자동 검색
        c1, c2, c3 = find_category_codes(categories, product.get('물품명', ''))

    if not c1:
        print("    ⚠️ 카테고리 코드를 찾을 수 없어 건너뜁니다.")
        return

    try:
        # [Step 1] 1차 카테고리 선택
        print(f"    👉 1차 선택: {c1}")
        page.select_option('select[name="f_category_code1"]', value=c1)
        time.sleep(2) # upload.js: await delay(2000)

        # [Step 2] 2차 카테고리 처리
        if c2:
            # 2차 옵션이 로드될 때까지 대기 (options.length > 1)
            # upload.js: waitForFunction(...)
            print("    ⏳ 2차 목록 로딩 대기...")
            try:
                page.wait_for_function(
                    "document.querySelector('select[name=\"f_category_code2\"]').options.length > 1",
                    timeout=5000
                )
            except:
                print("    ⚠️ 2차 로딩 타임아웃 (무시하고 진행)")

            time.sleep(0.5)
            print(f"    👉 2차 선택: {c2}")
            page.select_option('select[name="f_category_code2"]', value=c2)
            time.sleep(2) # upload.js: await delay(2000)

            # [Step 3] 3차 카테고리 처리
            if c3:
                # 3차 옵션이 로드될 때까지 대기
                print("    ⏳ 3차 목록 로딩 대기...")
                try:
                    page.wait_for_function(
                        "document.querySelector('select[name=\"f_category_code3\"]').options.length > 1",
                        timeout=5000
                    )
                except:
                    print("    ⚠️ 3차 로딩 타임아웃")

                time.sleep(0.5)
                print(f"    👉 3차 선택: {c3}")
                page.select_option('select[name="f_category_code3"]', value=c3)
                time.sleep(0.5)

        print("    ✅ 카테고리 설정 완료")

    except Exception as e:
        print(f"    ❌ 카테고리 선택 중 오류: {e}")

# ======================================================
# [기능] 나머지 등록 함수들
# ======================================================
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

def register_smart_editor(page, description):
    print("  📝 상세설명 입력 중...")
    try:
        iframe_element = page.wait_for_selector('iframe[src*="SmartEditor2Skin"]', timeout=10000)
        frame = iframe_element.content_frame()
        if frame:
            time.sleep(1)
            html_btn = frame.locator('.se2_to_html')
            if html_btn.is_visible():
                html_btn.click()
                time.sleep(0.5)
                frame.locator('.se2_input_htmlsrc').fill(description)
                frame.locator('.se2_to_editor').click()
                print("    ✅ 에디터 내용 주입 성공")
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

def register_product_full(context, page, product, categories):
    print(f"\n>>> [상품 등록 시작] : {product.get('물품명', '이름없음')}")
    handle_popups_safely(context, page)
    
    try: page.goto(S2B_REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
    except: pass
    time.sleep(3)
    handle_popups_safely(context, page)
    try: 
        if page.locator(".btn_popclose").first.is_visible():
            page.locator(".btn_popclose").first.click()
    except: pass

    print(">>> 폼 입력 시작...")
    try:
        page.wait_for_selector('input[name="f_goods_name"]', state="visible", timeout=30000)

        # [수정됨] 카테고리 등록 (upload.js 로직 적용됨)
        register_categories(page, product, categories)
        
        # 이미지, 텍스트 등 나머지 등록
        register_images(context, page, product)

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

        register_delivery_info(page, product)
        
        desc = product.get('상세설명', '<p>상세 설명입니다.</p>')
        register_smart_editor(page, desc)

        try:
            chk = page.locator('#uprightContract')
            if chk.is_visible() and not chk.is_checked():
                chk.check()
        except: pass

        # submit_product(page) # 실제 저장하려면 주석 해제

        print("\n>>> ✅ 모든 입력이 완료되었습니다.")
        time.sleep(5)

    except Exception as e:
        print(f"!!! 등록 처리 중 에러: {e}")

# ======================================================
# [메인] 실행
# ======================================================
def run_s2b_bot():
    print(">>> [S2B_Agent] 봇을 시작합니다...")
    categories = load_category_data()
    product = load_first_product()
    
    if not product:
        print("!!! 데이터 파일 확인 필요")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        print(f">>> 로그인 페이지 이동: {S2B_LOGIN_URL}")
        page = context.new_page()
        
        try:
            page.goto(S2B_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector('form[name="vendor_loginForm"] [name="uid"]', state="visible", timeout=30000)
            page.fill('form[name="vendor_loginForm"] [name="uid"]', USER_ID)
            page.fill('form[name="vendor_loginForm"] [name="pwd"]', USER_PW)
            page.click('form[name="vendor_loginForm"] .btn_login > a')
            
            handle_popups_safely(context, page)
            register_product_full(context, page, product, categories)

        except Exception as e:
            print(f"!!! 에러 발생: {e}")
        finally:
            print(">>> 브라우저를 종료합니다.")
            browser.close()

if __name__ == "__main__":
    run_s2b_bot()