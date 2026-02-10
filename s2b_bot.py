import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# 1. 환경 변수 및 설정
load_dotenv()

USER_ID = os.getenv("S2B_ID") 
USER_PW = os.getenv("S2B_PW")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

# [핵심] 봇은 오직 이 파일만 바라봅니다 (이미지 경로가 로컬로 되어 있는 완성본)
BOT_DATA_FILE = 's2b_bot_input.json' 
CATEGORY_FILE = 's2b_categories.json'

S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'

# [v4.2] 고정값 설정 (배송비 등)
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
# [유틸리티] 파일 로드 및 카테고리/팝업 처리
# ======================================================
def load_products():
    """AI 변환기가 생성한 최종 JSON 로드"""
    if not os.path.exists(BOT_DATA_FILE):
        print(f"❌ 오류: 입력 파일({BOT_DATA_FILE})이 없습니다.")
        return []
    try:
        with open(BOT_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"📂 변환된 데이터 {len(data)}개를 로드했습니다.")
            return data
    except Exception as e:
        print(f"❌ JSON 로드 실패: {e}")
        return []

def load_category_data():
    if not os.path.exists(CATEGORY_FILE): return {}
    try:
        with open(CATEGORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return {}

def remove_success_product(product_to_remove, all_products):
    """성공한 상품을 리스트에서 제거하고 파일 갱신 (중단 후 재시작 지원)"""
    remaining = [p for p in all_products if p['물품명'] != product_to_remove['물품명']]
    try:
        with open(BOT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, ensure_ascii=False, indent=4)
        print(f"    🗑️ 목록에서 제거됨 (남은 상품: {len(remaining)}개)")
    except Exception as e:
        print(f"    ⚠️ 파일 갱신 실패: {e}")

def handle_popups(page):
    """S2B 내부 팝업/알림창 닫기"""
    try:
        # 시스템 알림창 닫기
        page.evaluate("""() => {
            const popups = document.querySelectorAll('article.popup.alert');
            popups.forEach(p => { if(!p.classList.contains('hide')) p.classList.add('hide'); });
            
            // 닫기 버튼들 클릭
            const btns = document.querySelectorAll('.btn_popclose, span.btn_popclose a');
            btns.forEach(b => b.click());
        }""")
    except: pass

def global_dialog_handler(dialog):
    """브라우저 Alert/Confirm 자동 수락"""
    try: dialog.accept()
    except: pass

# ======================================================
# [기능] S2B 등록 로직 (업로드 전용)
# ======================================================
def register_categories(page, product):
    """카테고리 선택 (코드가 이미 있으면 바로 선택)"""
    print(f"  📂 카테고리 설정...")
    
    # AI 컨버터가 이미 코드를 찾아서 '카테고리X' 필드에 넣어줬다고 가정
    c1 = product.get('카테고리1')
    c2 = product.get('카테고리2')
    c3 = product.get('카테고리3')

    try:
        if c1:
            page.select_option('select[name="f_category_code1"]', value=str(c1))
            time.sleep(1.0)
        
        if c2:
            # 2차 카테고리 로딩 대기
            page.wait_for_function("document.querySelector('select[name=\"f_category_code2\"]').options.length > 1", timeout=5000)
            page.select_option('select[name="f_category_code2"]', value=str(c2))
            time.sleep(1.0)
            
        if c3:
            # 3차 카테고리 로딩 대기
            page.wait_for_function("document.querySelector('select[name=\"f_category_code3\"]').options.length > 1", timeout=5000)
            page.select_option('select[name="f_category_code3"]', value=str(c3))
            
        print("    ✅ 카테고리 선택 완료")
    except Exception as e:
        print(f"    ⚠️ 카테고리 선택 중 경고 (기본값 확인 필요): {e}")

def register_images(page, product):
    """로컬 이미지 파일 업로드"""
    print("  🖼️ 이미지 업로드...")
    
    # 1. 상세 이미지 (이미지 병합된 파일 경로)
    detail_path = product.get('상세이미지')
    if detail_path and os.path.exists(detail_path):
        try:
            # 파일 입력창이 안 보일 수 있으므로 강제로 보이게 하거나 바로 set_input_files 사용
            page.set_input_files('input[name="f_goods_explain_img_file"]', detail_path)
            time.sleep(1) # 업로드 처리 대기
            
            # 업로드 후 팝업이 뜰 경우 닫기
            handle_popups(page)
            print("    ✅ 상세이미지 등록됨")
        except Exception as e:
            print(f"    ❌ 상세이미지 업로드 실패: {e}")
    
    # 2. 기본 이미지 (대표 이미지)
    main_path = product.get('기본이미지1')
    if main_path and os.path.exists(main_path):
        try:
            page.set_input_files('input[name="f_img1_file"]', main_path)
            time.sleep(1)
            handle_popups(page)
            print("    ✅ 기본이미지 등록됨")
        except Exception as e:
            print(f"    ❌ 기본이미지 업로드 실패: {e}")

def register_base_info(page, product):
    """기본 정보 입력"""
    print("  📝 기본 정보 입력...")
    try:
        page.fill('input[name="f_goods_name"]', product['물품명'])
        page.fill('input[name="f_size"]', product['규격'])
        
        # 모델명 처리
        if product.get('모델명') and product['모델명'] != '없음':
            page.click('input[name="f_model_yn"][value="N"]')
            page.fill('input[name="f_model"]', product['모델명'])
        else:
            page.click('input[name="f_model_yn"][value="Y"]') # 모델명 없음

        # 가격 (쉼표 제거)
        price = str(product.get('제시금액', '0')).replace(',', '')
        page.fill('input[name="f_estimate_amt"]', price)
        
        page.fill('input[name="f_factory"]', product.get('제조사명', '기타'))
        page.fill('input[name="f_remain_qnt"]', FIXED_VALUES["재고수량"])
        
        # 재질
        material = product.get('소재재질') or product.get('재질') or "상세설명 참조"
        page.fill('input[name="f_material"]', material)
        
        page.select_option('select[name="f_credit"]', FIXED_VALUES["판매단위"])

        # 원산지 (국산/수입)
        origin = product.get('원산지', '국산')
        if '한국' in origin or '국산' in origin or '경기' in origin:
            page.click('input[name="f_home_divi"][value="1"]') # 국산
        else:
            page.click('input[name="f_home_divi"][value="2"]') # 수입
            try: page.select_option('#select_home_02', 'ZD000002') # 아시아 등 기본 선택
            except: pass
            
    except Exception as e:
        print(f"    ❌ 기본 정보 입력 오류: {e}")

def register_smart_editor(page):
    """상세설명(HTML) 입력"""
    print("  📝 상세설명 입력...")
    try:
        # 스마트에디터 프레임 찾기
        frame_el = page.wait_for_selector('iframe[src*="SmartEditor2Skin"]', timeout=5000)
        if frame_el:
            frame = frame_el.content_frame()
            time.sleep(1)
            # HTML 모드 전환 -> 내용 입력 -> Editor 모드 복귀
            if frame.locator('.se2_to_html').is_visible():
                frame.locator('.se2_to_html').click()
                frame.locator('.se2_input_htmlsrc').fill(COMPANY_INTRO_HTML)
                frame.locator('.se2_to_editor').click()
    except Exception as e:
        print(f"    ⚠️ 에디터 입력 실패 (무시됨): {e}")

def submit_product(page):
    """저장 버튼 클릭"""
    print("  💾 저장 요청...")
    try:
        # 청렴계약 동의 체크
        page.evaluate("if(document.querySelector('#uprightContract')) document.querySelector('#uprightContract').checked = true;")
        
        # 저장 스크립트 실행
        page.evaluate("if(typeof register === 'function') { register('1'); }")
        
        # 처리 대기 (화면 전환 등)
        time.sleep(5)
    except Exception as e:
        print(f"    ❌ 저장 실행 중 오류: {e}")

# ======================================================
# [메인 실행]
# ======================================================
def run_s2b_bot():
    print(">>> [S2B Bot] 시작 (Mode: Upload Only)")
    
    # 1. 데이터 로드
    products = load_products()
    if not products: return

    with sync_playwright() as p:
        # 브라우저 실행
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1600, "height": 1000}) # 화면 크게
        page = context.new_page()
        page.on("dialog", global_dialog_handler) # 알림창 자동 닫기

        try:
            # 2. 로그인
            print(f">>> 로그인 시도: {USER_ID}")
            page.goto(S2B_LOGIN_URL)
            page.wait_for_selector('form[name="vendor_loginForm"]', timeout=10000)
            page.fill('input[name="uid"]', USER_ID)
            page.fill('input[name="pwd"]', USER_PW)
            page.click('.btn_login > a')
            time.sleep(2)

            # 3. 상품 등록 루프
            for idx, product in enumerate(products):
                print(f"\n>>> [{idx+1}/{len(products)}] 등록 시작: {product['물품명']}")
                
                # 등록 페이지 이동
                page.goto(S2B_REGISTER_URL)
                time.sleep(2)
                handle_popups(page) # 팝업 정리

                # 정보 입력
                register_categories(page, product)
                register_base_info(page, product)
                # (KC 인증 정보 입력 로직은 필요 시 추가 - 현재는 기본정보 위주)
                register_images(page, product)
                register_smart_editor(page)
                
                # 배송비/납품정보 (기본값 클릭)
                page.click('input[name="f_delivery_fee_kind"][value="1"]') # 무료 등 설정
                # ... (필요 시 세부 설정 추가)

                # 최종 저장
                submit_product(page)
                
                print(f">>> ✅ [{idx+1}] 등록 완료")
                
                # 성공한 상품 목록에서 제거 (재실행 시 중복 방지)
                remove_success_product(product, products)
                
                time.sleep(2) # 쿨타임

        except Exception as e:
            print(f"!!! 봇 실행 중 치명적 오류: {e}")
        finally:
            browser.close()
            print(">>> 봇 종료")

if __name__ == "__main__":
    run_s2b_bot()