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

USER_ID = os.getenv("S2B_ID", "")
USER_PW = os.getenv("S2B_PW", "")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

def handle_popups_safely(context, main_page):
    """[일반] 메인 외의 모든 팝업 닫기"""
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

def register_images(context, page, product):
    """이미지 업로드"""
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
    """스마트 에디터 입력"""
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
            else:
                print("    ⚠️ HTML 탭 없음")
    except Exception as e:
        print(f"    ❌ 에디터 입력 실패: {e}")

def register_delivery_info(page, product):
    """배송 및 인증 정보"""
    print("  🚚 배송/기타 정보 입력...")
    try:
        page.click('input[name="f_delivery_fee_kind"][value="1"]') # 무료
        page.click('input[name="f_delivery_method"][value="1"]')   # 택배
        page.click('input[name="delivery_area"][value="1"]')      # 전국
        page.click('input[name="f_delivery_group_yn"][value="N"]') # 합배송불가
        page.select_option('select[name="f_tax_method"]', '1')    # 과세
        page.select_option('select[name="f_delivery_limit"]', 'ZD000004') # 15일
        
        # KC인증 (모두 N)
        for kc in ['kids', 'elec', 'daily', 'broadcasting']:
            page.click(f'input[name="{kc}KcUseGubunChk"][value="N"]')
            
        print("    ✅ 배송/인증 완료")
    except: pass

def register_categories(page, product):
    """
    [신규] 카테고리 선택 (동적 로딩 대기 포함)
    """
    print("  📂 카테고리 선택 중...")
    
    cat1 = product.get('카테고리1_코드', '')
    cat2 = product.get('카테고리2_코드', '')
    
    # 1차 카테고리
    if cat1:
        try:
            print(f"    👉 1차 선택: {cat1}")
            page.select_option('select[name="f_category_code1"]', cat1)
            
            # 2차 카테고리 목록이 로드될 때까지 대기 (옵션 개수가 1개 초과가 될 때까지)
            if cat2:
                print("    ⏳ 2차 목록 로딩 대기...")
                try:
                    page.wait_for_function(
                        "document.querySelector('select[name=\"f_category_code2\"]').options.length > 1",
                        timeout=5000
                    )
                    time.sleep(0.5)
                    print(f"    👉 2차 선택: {cat2}")
                    page.select_option('select[name="f_category_code2"]', cat2)
                    print("    ✅ 카테고리 설정 완료")
                except:
                    print("    ⚠️ 2차 카테고리 로딩 실패 (코드 확인 필요)")
        except Exception as e:
            print(f"    ❌ 카테고리 선택 오류: {e}")
    else:
        print("    ⚠️ 카테고리 코드가 없습니다. (수동 선택 필요)")

def submit_product(page):
    """
    [신규] 저장 버튼 클릭 및 Dialog 처리
    """
    print("\n  💾 [최종 저장] 버튼 클릭 시도...")
    
    # Dialog 핸들러 등록 (alert, confirm 창이 뜨면 무조건 '수락')
    page.on("dialog", lambda dialog: dialog.accept())
    
    try:
        # '등록대기(저장)' 버튼 찾기 (보통 register('1') 함수 호출함)
        # S2B 버튼 Selector
        save_btn = page.locator("a[href*=\"javascript:register('1')\"]")
        
        if save_btn.is_visible():
            save_btn.click()
            print("    👉 저장 버튼 클릭함 (Dialog 자동 수락)")
        else:
            # 버튼을 못 찾으면 JS 직접 실행
            print("    👉 버튼 못 찾음, JS 직접 실행 시도...")
            page.evaluate("register('1')")
            
        # 저장 후 처리 대기 (서버 응답)
        print("    ⏳ 저장 처리 대기 중 (5초)...")
        time.sleep(5)
        
    except Exception as e:
        print(f"    ❌ 저장 처리 중 오류: {e}")

def register_product_full(context, page, product):
    print(f"\n>>> [상품 등록 시작] : {product.get('물품명', '이름없음')}")
    
    # 1. 초기화
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

        # [신규] 카테고리
        register_categories(page, product)
        
        # 이미지
        register_images(context, page, product)

        # 텍스트
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

        # 배송/인증
        register_delivery_info(page, product)

        # 스마트 에디터
        desc = product.get('상세설명', '<p>상세 설명입니다.</p>')
        register_smart_editor(page, desc)

        # 청렴계약서 체크 (S2B 필수)
        try:
            chk = page.locator('#uprightContract')
            if chk.is_visible() and not chk.is_checked():
                chk.check()
                print("  ✅ 청렴계약서 체크 완료")
        except: pass

        # [신규] 최종 저장
        # submit_product(page) 
        # ▲ 주의: 실제로 저장하려면 위 주석을 해제하세요. 
        # 지금은 안전을 위해 "입력 완료"까지만 보여드립니다.
        
        print("\n>>> ✅ 모든 입력이 완료되었습니다.")
        print(">>> (안전 모드: 실제 '저장' 버튼은 누르지 않았습니다. 코드 주석을 확인하세요.)")
        time.sleep(10)

    except Exception as e:
        print(f"!!! 등록 처리 중 에러: {e}")

def run_s2b_bot():
    print(">>> [S2B_Agent] 봇을 시작합니다...")
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
            register_product_full(context, page, product)

        except Exception as e:
            print(f"!!! 에러 발생: {e}")
        
        finally:
            print(">>> 브라우저를 종료합니다.")
            browser.close()

if __name__ == "__main__":
    run_s2b_bot()