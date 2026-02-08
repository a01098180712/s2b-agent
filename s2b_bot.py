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
TEST_MODE = False 

S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'
DATA_FILE = 's2b_complete_data.json'
CATEGORY_FILE = 's2b_categories.json'

USER_ID = os.getenv("S2B_ID", "taurus06") 
USER_PW = os.getenv("S2B_PW", "rlathdxo06!")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# [v4.2] 고정값 설정
FIXED_VALUES = {
    "재고수량": "999",
    "제주배송비": "5000",
    "반품배송비": "5000",
    "교환배송비": "10000",
    "납품기간": "ZD000004",  # 15일
    "판매단위": "ZD000048",  # 개
    "과세여부": "1",         # 과세
}

COMPANY_INTRO_HTML = """<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p style="font-size: 15pt; font-weight: bold; text-align: center;">【 에스엔비몰 】학교장터 전문 공급업체</p>
<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
<p style="font-size: 11pt;">에스엔비몰은 학교장터 전문 공급업체로, 학교 및 교육기관에 양질의 제품을 공급하고 있습니다.</p>
<p>&nbsp;</p> <br>
<p style="font-size: 15pt; font-weight: bold;">▣ 우리의 약속</p>
<p style="font-size: 11pt;"> ✓ 신속하고 안전한 배송을 약속드립니다<br> ✓ 불량 상품은 무료 교환/반품 처리를 원칙으로 합니다<br> ✓ 대량 구매 시 할인 혜택이 있습니다</p>
<p>&nbsp;</p> <br>
<p style="font-size: 15pt; font-weight: bold;">▣ 문의 안내</p>
<p style="font-size: 11pt;">궁금하신 사항은 언제든지 문의해 주세요.<br>성실히 답변 드리겠습니다.</p>
<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>"""

# ======================================================
# [유틸리티]
# ======================================================
def load_category_data():
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CATEGORY_FILE)
    if not os.path.exists(file_path): return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            print("📂 카테고리 데이터 로드 완료")
            return json.load(f)
    except: return {}

def resolve_category_codes(product, categories):
    if not categories: return None, None, None
    c1_val = product.get('카테고리1') or product.get('카테고리1_코드')
    c2_val = product.get('카테고리2') or product.get('카테고리2_코드')
    c3_val = product.get('카테고리3') or product.get('카테고리3_코드')
    c1_code, c2_code, c3_code = None, None, None

    if c1_val:
        if str(c1_val).isdigit(): c1_code = str(c1_val)
        elif 'category1' in categories:
            for item in categories['category1']:
                if item['text'] == c1_val:
                    c1_code = item['value']; break
            if not c1_code:
                for item in categories['category1']:
                    if c1_val in item['text'] or item['text'] in c1_val:
                        c1_code = item['value']; break
    
    if c1_code and c2_val:
        if str(c2_val).isdigit(): c2_code = str(c2_val)
        elif 'category2' in categories and c1_code in categories['category2']:
            for item in categories['category2'][c1_code]:
                if item['text'] == c2_val:
                    c2_code = item['value']; break
            if not c2_code:
                for item in categories['category2'][c1_code]:
                    if c2_val in item['text'] or item['text'] in c2_val:
                        c2_code = item['value']; break

    if c1_code and c2_code and c3_val:
        key = f"{c1_code}_{c2_code}"
        if str(c3_val).isdigit(): c3_code = str(c3_val)
        elif 'category3' in categories and key in categories['category3']:
            for item in categories['category3'][key]:
                if item['text'] == c3_val:
                    c3_code = item['value']; break
            if not c3_code:
                for item in categories['category3'][key]:
                    if c3_val in item['text'] or item['text'] in c3_val:
                        c3_code = item['value']; break
    
    return c1_code, c2_code, c3_code

def handle_popups_safely(context, main_page):
    """새 창(Window)으로 뜨는 팝업 닫기"""
    try:
        time.sleep(1)
        for p in context.pages:
            if p != main_page:
                try: 
                    if not p.is_closed(): p.close()
                except: pass
    except: pass

def close_interface_popups(page):
    """
    [v4.3] 페이지 내부의 레이어 팝업 및 알림창을 강제로 닫습니다.
    """
    print("    🧹 [Popup] 내부 팝업/알림창 정리 시도...")
    try:
        page.evaluate("""() => {
            const popups = document.querySelectorAll('article.popup.alert');
            popups.forEach(popup => {
                if (!popup.classList.contains('hide')) {
                    popup.classList.add('hide');
                }
            });
            const closeButtons = [
                'span.btn_popclose a', '.btn_popclose',
                '[class*="close"]', '[onclick*="close"]'
            ];
            for (const selector of closeButtons) {
                const btn = document.querySelector(selector);
                if (btn && btn.offsetParent !== null) {
                    btn.click();
                    break;
                }
            }
        }""")
        time.sleep(1)
    except Exception as e:
        print(f"    ⚠️ 팝업 정리 중 오류(무시됨): {e}")

def enable_scroll(page):
    """
    [v4.4] 페이지의 스크롤바를 강제로 활성화하여 전체 내용을 확인할 수 있게 합니다.
    """
    try:
        page.evaluate("""() => {
            document.documentElement.style.overflow = 'auto';
            document.body.style.overflow = 'auto';
            document.body.style.height = 'auto';
        }""")
        # print("    🔧 스크롤바 활성화 완료")
    except: pass

def handle_post_upload_popup(context):
    try:
        time.sleep(2)
        pages = context.pages
        for p in pages:
            if "preview" in p.url.lower() or "pop" in p.url.lower():
                try:
                    if not p.is_closed():
                        p.close()
                        print("    👉 이미지 미리보기/팝업 닫음")
                except: pass
    except: pass

def load_products():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return []

def remove_success_product(product_to_remove):
    products = load_products()
    updated_products = [
        p for p in products 
        if not (p.get('물품명') == product_to_remove.get('물품명') and p.get('규격') == product_to_remove.get('규격'))
    ]
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_products, f, ensure_ascii=False, indent=4)
        print(f"    🗑️ 데이터 파일에서 삭제 완료 ({len(products)} -> {len(updated_products)})")
    except Exception as e:
        print(f"    ❌ 데이터 파일 갱신 실패: {e}")

def global_dialog_handler(dialog):
    try: dialog.accept()
    except: pass

# ======================================================
# [기능] 등록 단계별 함수
# ======================================================

def register_categories(page, product, categories):
    print(f"\n  📂 [{product.get('물품명')}] 카테고리 설정...")
    c1, c2, c3 = resolve_category_codes(product, categories)
    if not c1:
        print(f"    ⚠️ 매칭 실패: '{product.get('카테고리1')}' 코드를 찾지 못했습니다.")
        return
    try:
        page.select_option('select[name="f_category_code1"]', value=str(c1))
        time.sleep(1.0) 
        if c2:
            try: page.wait_for_function("document.querySelector('select[name=\"f_category_code2\"]').options.length > 1", timeout=5000)
            except: pass
            time.sleep(0.5)
            page.select_option('select[name="f_category_code2"]', value=str(c2))
            time.sleep(1.0)
            if c3:
                try: page.wait_for_function("document.querySelector('select[name=\"f_category_code3\"]').options.length > 1", timeout=5000)
                except: pass
                time.sleep(0.5)
                page.select_option('select[name="f_category_code3"]', value=str(c3))
                time.sleep(0.5)
        print("    ✅ 카테고리 설정 완료")
    except Exception as e:
        print(f"    ❌ 카테고리 선택 중 오류: {e}")

def register_base_info(page, product):
    print("  📝 기본 정보 및 원산지 입력...")
    try:
        if product.get('물품명'): page.fill('input[name="f_goods_name"]', product['물품명'])
        if product.get('규격'): page.fill('input[name="f_size"]', product['규격'])
        
        model_name = product.get('모델명', '')
        if model_name and model_name != '없음':
            page.click('input[name="f_model_yn"][value="N"]')
            page.fill('input[name="f_model"]', model_name)
        else:
            page.click('input[name="f_model_yn"][value="Y"]')

        price = str(product.get('제시금액', '0')).replace(',', '')
        page.fill('input[name="f_estimate_amt"]', price)
        if product.get('제조사명'): page.fill('input[name="f_factory"]', product['제조사명'])
        page.fill('input[name="f_remain_qnt"]', FIXED_VALUES["재고수량"])
        
        material = product.get('소재재질', '')
        if not material: material = "상세설명 참조"
        page.fill('input[name="f_material"]', material)
        
        page.select_option('select[name="f_credit"]', FIXED_VALUES["판매단위"])

        origin = product.get('원산지', '')
        if '한국' in origin or '국내' in origin:
            page.click('input[name="f_home_divi"][value="1"]')
        else:
            page.click('input[name="f_home_divi"][value="2"]')
            try: page.select_option('#select_home_02', 'ZD000002')
            except: pass
        print("    ✅ 기본 정보 입력 완료")
    except Exception as e:
        print(f"    ❌ 기본 정보 입력 중 오류: {e}")

def register_cert_info(context, page, product):
    print("  🏆 인증 정보(KC/G2B) 처리 (v4.2: 모두 해당없음)...")
    try:
        kcs = ['kids', 'elec', 'daily', 'broadcasting']
        for kc in kcs:
            try: page.click(f'input[name="{kc}KcUseGubunChk"][value="N"]')
            except: pass
        print("    ✅ 인증 정보 설정 완료 (KC: N / G2B: Skip)")
    except Exception as e:
        print(f"    ❌ 인증 정보 처리 중 오류: {e}")

def register_images(context, page, product):
    print("  🖼️ 이미지 업로드 처리...")
    detail_img_path = product.get('상세이미지', '')
    if detail_img_path and os.path.exists(detail_img_path):
        try:
            page.set_input_files('input[name="f_goods_explain_img_file"]', detail_img_path)
            handle_post_upload_popup(context)
            print("    ✅ 상세이미지 완료")
        except: print("    ❌ 상세이미지 실패")
    
    time.sleep(1)
    img1_path = product.get('기본이미지1', '')
    if img1_path and os.path.exists(img1_path):
        try:
            page.set_input_files('input[name="f_img1_file"]', img1_path)
            handle_post_upload_popup(context)
            print("    ✅ 기본이미지 완료")
        except: print("    ❌ 기본이미지 실패")

def register_smart_editor(page, html_content):
    """
    [v4.4] Iframe 내부의 에디터 버튼을 직접 제어하여 HTML 입력
    """
    print("  📝 상세설명(HTML) 입력 중... (Iframe Control)")
    try:
        # 1. Iframe 찾기
        frame_element = page.wait_for_selector('iframe[src*="SmartEditor2Skin"]', timeout=10000)
        frame = frame_element.content_frame()
        
        if frame:
            time.sleep(1)
            # 2. HTML 탭 클릭
            try:
                if frame.locator('.se2_to_html').is_visible():
                    frame.locator('.se2_to_html').click()
                    time.sleep(0.5)
            except: pass

            # 3. 입력
            try:
                frame.locator('.se2_input_htmlsrc').fill(html_content)
                time.sleep(0.5)
                # 4. Editor 탭 복귀
                frame.locator('.se2_to_editor').click()
                print("    ✅ 회사소개 문구 입력 완료")
            except Exception as e:
                print(f"    ⚠️ 입력 실패: {e}")
        else:
            print("    ❌ 에디터 프레임 없음")
    except Exception as e:
        print(f"    ❌ 에디터 오류: {e}")

def register_delivery_fees(page):
    print("  🚚 배송비 및 납품정보 입력...")
    try:
        page.click('input[name="f_delivery_fee_kind"][value="1"]')
        page.click('input[name="f_delivery_method"][value="1"]')
        page.click('input[name="delivery_area"][value="1"]')
        page.click('input[name="f_delivery_group_yn"][value="N"]')
        page.select_option('select[name="f_delivery_limit"]', FIXED_VALUES["납품기간"]) 
        page.select_option('select[name="f_tax_method"]', FIXED_VALUES["과세여부"])
        
        return_fee = FIXED_VALUES["반품배송비"]
        exchange_fee = FIXED_VALUES["교환배송비"]
        page.evaluate(f"""() => {{
            const ret = document.querySelector('input[name="f_return_fee"]');
            const exch = document.querySelector('input[name="f_exch_fee"]'); 
            if(ret) ret.value = '{return_fee}';
            if(exch) exch.value = '{exchange_fee}';
        }}""")

        try:
            jeju_chk = page.locator('input[name="f_jeju_delivery_yn"]')
            if not jeju_chk.is_checked(): jeju_chk.click()
            page.fill('input[name="f_jeju_delivery_fee"]', FIXED_VALUES["제주배송비"])
        except: pass
        print("    ✅ 배송비 설정 완료")
    except Exception as e:
        print(f"    ❌ 배송비 입력 중 오류: {e}")

def submit_product(page):
    print("\n  💾 [Action] 등록대기(저장) 실행...")
    try:
        page.evaluate("""
            const chk = document.querySelector('#uprightContract');
            if(chk && !chk.checked) { chk.checked = true; }
        """)
        
        # JS 함수 직접 호출
        page.evaluate("if(typeof register === 'function') { register('1'); }")

        # [v4.3] 사용자 요청: 등록 결과 확인을 위해 30초 대기
        print("    ⏳ [Wait] 등록 결과 확인을 위해 30초 대기합니다...")
        time.sleep(30)
        
    except Exception as e:
        print(f"    ❌ 저장 처리 중 오류: {e}")

# ======================================================
# [메인]
# ======================================================
def run_s2b_bot():
    print(">>> [S2B_Agent] 봇 시작 (v4.4 - 스크롤활성화 & 에디터수정)")
    categories = load_category_data()
    products = load_products()
    if not products:
        print("!!! 데이터 파일이 비어있거나 없습니다.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1400, "height": 1000})
        
        print(f">>> 로그인 페이지 이동: {S2B_LOGIN_URL}")
        page = context.new_page()
        page.on("dialog", global_dialog_handler)
        
        try:
            # 1. 로그인
            page.goto(S2B_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
            if "Login.do" in page.url:
                page.wait_for_selector('form[name="vendor_loginForm"] [name="uid"]', state="visible", timeout=30000)
                page.fill('form[name="vendor_loginForm"] [name="uid"]', USER_ID)
                page.fill('form[name="vendor_loginForm"] [name="pwd"]', USER_PW)
                page.click('form[name="vendor_loginForm"] .btn_login > a')
            
            handle_popups_safely(context, page)

            # 2. 루프
            for i, product in enumerate(products):
                print(f"\n>>> [상품 {i+1}/{len(products)}] 등록 시작: {product.get('물품명')}")
                
                try: page.goto(S2B_REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
                except: pass
                
                time.sleep(3) 
                handle_popups_safely(context, page) 
                close_interface_popups(page)
                
                # [v4.4] 스크롤 활성화 호출
                enable_scroll(page)

                try: page.wait_for_selector('input[name="f_goods_name"]', state="visible", timeout=30000)
                except: 
                    print("    ⚠️ 등록 폼 로드 실패, 건너뜀")
                    continue

                register_categories(page, product, categories)
                if TEST_MODE:
                    time.sleep(3)
                    continue
                register_base_info(page, product)
                register_cert_info(context, page, product)
                register_images(context, page, product)
                
                # [v4.4] 수정된 에디터 함수 호출
                register_smart_editor(page, COMPANY_INTRO_HTML)
                
                register_delivery_fees(page)
                submit_product(page)
                
                print(f">>> ✅ [상품 {i+1}] 처리 요청 완료.")
                remove_success_product(product)

        except Exception as e:
            print(f"!!! 치명적 에러 발생: {e}")
        finally:
            print(">>> 작업을 종료합니다.")
            try: page.close() 
            except: pass
            time.sleep(1)
            browser.close()

if __name__ == "__main__":
    run_s2b_bot()