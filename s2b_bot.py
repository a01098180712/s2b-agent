import os
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# 1. 설정
load_dotenv()
USER_ID = os.getenv("S2B_ID") 
USER_PW = os.getenv("S2B_PW")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

BOT_DATA_FILE = 's2b_bot_input.json' 
S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'

# [고정값]
FIXED_VALUES = {
    "재고수량": "999",
    "제주배송비": "5000",
    "반품배송비": "5000",
    "교환배송비": "10000",
    "납품기간": "ZD000004",  # 15일
    "판매단위": "ZD000048",  # 개
    "과세여부": "1",         # 과세
    "회사소개": """<p style="font-size: 15pt; font-weight: bold;">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</p>
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
}

# ======================================================
# [유틸리티]
# ======================================================

def load_products():
    if not os.path.exists(BOT_DATA_FILE): return []
    with open(BOT_DATA_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def remove_success_product(product_to_remove, all_products):
    remaining = [p for p in all_products if p['물품명'] != product_to_remove['물품명']]
    with open(BOT_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(remaining, f, ensure_ascii=False, indent=4)

def close_popups(context, page):
    """[Popup] 새 창 닫기 + 내부 팝업 숨기기"""
    for p in context.pages:
        if p != page:
            try: 
                if not p.is_closed(): p.close()
            except: pass
    
    for i in range(3):
        try:
            page.evaluate("""() => {
                const popups = document.querySelectorAll('article.popup.alert');
                popups.forEach(p => { 
                    if(!p.classList.contains('hide')) p.classList.add('hide'); 
                });
            }""")
            selectors = ['span.btn_popclose a', '.btn_popclose', '[class*="close"]', '[onclick*="close"]']
            for sel in selectors:
                if page.locator(sel).count() > 0:
                    page.locator(sel).first.click(timeout=500)
            time.sleep(0.5)
        except: pass

def enable_page_scroll(page):
    """스크롤 강제 활성화"""
    print("    🔧 화면 스크롤 활성화...")
    try:
        page.evaluate("""() => {
            document.documentElement.style.overflow = 'auto';
            document.documentElement.style.overflowY = 'scroll';
            document.body.style.overflow = 'auto';
            document.body.style.overflowY = 'scroll';
            document.body.style.height = 'auto';
            document.body.style.minHeight = '100vh';
            document.body.style.position = 'static';
            window.scrollTo(0, 0);
        }""")
    except: pass

def global_dialog_handler(dialog):
    """일반 알림창 핸들러"""
    try:
        msg = dialog.message
        print(f"    💬 [S2B 알림] {msg}")
        dialog.accept()
    except: pass

# ======================================================
# [기능] 등록 함수
# ======================================================

def register_g2b_info(page, product):
    """G2B 물품분류번호 입력"""
    g2b_code = product.get('G2B분류번호')
    if g2b_code:
        print(f"  🏛️ G2B 분류번호 입력: {g2b_code}")
        try:
            if page.locator('input[name="f_uid2"]').count() > 0:
                page.fill('input[name="f_uid2"]', g2b_code)
                print("    ✅ 입력 완료")
        except Exception as e:
            print(f"    ❌ G2B 입력 중 오류: {e}")
    else:
        print("    ℹ️ G2B 번호 데이터 없음")

def register_kc_info(page, product):
    """
    [핵심 수정] KC 인증 입력 재시도 로직 (Fallback: S2B -> Backup -> None)
    """
    print("  🛡️ KC 인증 정보 입력 (순차적 재시도 모드)...")

    # 기존 핸들러 잠시 제거 (충돌 방지)
    page.remove_listener("dialog", global_dialog_handler)
    
    dialog_messages = []
    def kc_dialog_handler(dialog):
        msg = dialog.message
        dialog_messages.append(msg)
        print(f"    ⚠️ [KC 경고] {msg}")
        try: dialog.accept()
        except: pass

    page.on("dialog", kc_dialog_handler)

    kc_config = {
        "KC_전기_번호": {"type": "elec"},
        "KC_생활_번호": {"type": "daily"},
        "KC_어린이_번호": {"type": "kids"},
        "KC_방송_번호": {"type": "broadcasting"}
    }
    
    for json_key, config in kc_config.items():
        kc_type = config['type']
        
        # 1순위: 메인 KC번호 (S2B 조회값)
        primary_code = product.get(json_key)
        # 2순위: 백업 KC번호 (크롤링값)
        backup_code = product.get(f"{json_key}_Backup")
        
        radio_name = f"{kc_type}KcUseGubunChk"
        if page.locator(f'input[name="{radio_name}"]').count() == 0: continue

        # --- 입력 시도 내부 함수 ---
        def try_kc_input(code):
            if not code or len(code) < 3: return False
            dialog_messages.clear()
            try:
                page.click(f'input[name="{radio_name}"][value="Y"]')
                page.fill(f"#{kc_type}KcCertId", code)
                page.evaluate(f"KcCertRegist('{kc_type}')")
                time.sleep(1.5)
                
                # 에러 메시지 확인
                for msg in dialog_messages:
                    if "존재하지 않습니다" in msg or "확인해주세요" in msg:
                        return False # 실패
                return True # 성공
            except: return False

        # --- 실행 로직 ---
        success = False
        
        # 1차 시도: Primary Code (S2B)
        if primary_code:
            print(f"    ▶ 1차 시도 ({kc_type}): {primary_code}")
            if try_kc_input(primary_code):
                print(f"      ✅ 1차 성공")
                success = True
                close_popups(page.context, page)
            else:
                print(f"      ❌ 1차 실패 (유효하지 않음)")
        
        # 2차 시도: Backup Code (Crawler)
        if not success and backup_code:
            print(f"    ▶ 2차 시도 (백업): {backup_code}")
            if try_kc_input(backup_code):
                print(f"      ✅ 2차 성공")
                success = True
                close_popups(page.context, page)
            else:
                print(f"      ❌ 2차 실패")

        # 3차 시도: 해당없음 (모두 실패)
        if not success:
            if primary_code or backup_code:
                print(f"    🔄 모든 시도 실패 -> '해당없음(N)' 처리")
            try: page.click(f'input[name="{radio_name}"][value="N"]')
            except: pass

    # 핸들러 복구
    page.remove_listener("dialog", kc_dialog_handler)
    page.on("dialog", global_dialog_handler)

def register_smart_editor(page):
    print("  📝 상세설명(HTML) 입력...")
    try:
        iframe_element = page.wait_for_selector('iframe[src*="SmartEditor2Skin"]', timeout=5000)
        if not iframe_element:
            page.fill('textarea[name="f_goods_explain"]', FIXED_VALUES["회사소개"])
            return

        frame = iframe_element.content_frame()
        if not frame: return
        time.sleep(1)

        if frame.locator('.se2_to_html').is_visible():
            frame.click('.se2_to_html')
            time.sleep(0.5)
        
        intro_html = FIXED_VALUES["회사소개"]
        frame.evaluate("""(html) => {
            const input = document.querySelector('.se2_input_htmlsrc');
            if(input) {
                input.value = html;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""", intro_html)
        time.sleep(0.5)

        if frame.locator('.se2_to_editor').is_visible():
            frame.click('.se2_to_editor')
            time.sleep(0.5)
        print("    ✅ 상세설명 입력 완료")

    except:
        try:
            page.evaluate(f"""
                const ta = document.querySelector('textarea[name="f_goods_explain"]');
                if(ta) {{ ta.value = `{FIXED_VALUES["회사소개"]}`; }}
            """)
        except: pass

def submit_product(context, page):
    """저장 버튼 클릭 후 20초 대기 (팝업 확인용)"""
    print("  💾 저장 시도...")
    try:
        page.evaluate("if(document.querySelector('#uprightContract')) document.querySelector('#uprightContract').checked = true;")
        
        print("    🖱️ '등록대기(저장)' 버튼 클릭 실행 (JS)...")
        page.evaluate("if(typeof register === 'function') { register('1'); }")
        
        print("    ⏱️ [점검] 버튼 클릭 완료. 팝업 생성 여부를 눈으로 확인하세요 (20초 대기)...")
        time.sleep(20)
        
        print("    🔎 팝업/알림 자동 감지 및 처리 시작...")
        
        popup_handled = False
        for _ in range(3): 
            for p in context.pages:
                if "rema100_statusWaitPopup" in p.url:
                    print(f"      👉 저장 확정 팝업 발견! ({p.url})")
                    try:
                        p.wait_for_load_state()
                        p.evaluate("fnConfirm('1')") 
                        print("      ✅ '수정완료' 버튼 클릭 성공")
                        time.sleep(1)
                        p.close()
                        popup_handled = True
                    except: pass
                    break
            if popup_handled: break
            time.sleep(1)
            
        if not popup_handled:
            print("      ℹ️ 팝업이 감지되지 않음 (알림창으로 끝났거나, 클릭이 무시됨)")

    except Exception as e:
        print(f"    ❌ 저장 실행 오류: {e}")

# ======================================================
# [메인 루프]
# ======================================================

def run_s2b_bot():
    print(">>> [S2B Bot] 시작 (v5.10 - Final Full Check)")
    products = load_products()
    if not products: return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = context.new_page()
        
        page.on("dialog", global_dialog_handler) 

        # 1. 로그인
        print(f">>> 로그인 시도: {S2B_LOGIN_URL}")
        page.goto(S2B_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")

        if "Login.do" in page.url:
            print(">>> 로그인 정보 입력...")
            page.wait_for_selector('form[name="vendor_loginForm"] [name="uid"]', state="visible", timeout=30000)
            page.fill('form[name="vendor_loginForm"] [name="uid"]', USER_ID)
            page.fill('form[name="vendor_loginForm"] [name="pwd"]', USER_PW)
            page.click('form[name="vendor_loginForm"] .btn_login > a')
            time.sleep(2)
            close_popups(context, page)

        # 2. 상품 등록
        for idx, product in enumerate(products):
            print(f"\n>>> [{idx+1}/{len(products)}] '{product['물품명']}' 등록 시작")
            
            try: page.goto(S2B_REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
            except: pass
            
            print("    ⏳ 페이지 준비 대기 (3초)...")
            time.sleep(3)
            close_popups(context, page)

            print("    📝 기본 정보 입력")
            page.fill('input[name="f_goods_name"]', product['물품명'])
            page.fill('input[name="f_size"]', product['규격'])
            if product.get('모델명') and product['모델명'] != '없음':
                page.click('input[name="f_model_yn"][value="N"]')
                page.fill('input[name="f_model"]', product['모델명'])
            else:
                page.click('input[name="f_model_yn"][value="Y"]')
            
            page.fill('input[name="f_estimate_amt"]', str(product.get('제시금액', '0')).replace(',', ''))
            page.fill('input[name="f_factory"]', product.get('제조사명', '기타'))
            
            print("    📂 카테고리 선택")
            c1, c2, c3 = product.get('카테고리1'), product.get('카테고리2'), product.get('카테고리3')
            if c1: 
                page.select_option('select[name="f_category_code1"]', str(c1))
                time.sleep(0.5)
            if c2: 
                page.wait_for_function("document.querySelector('select[name=\"f_category_code2\"]').options.length > 1")
                page.select_option('select[name="f_category_code2"]', str(c2))
                time.sleep(0.5)
            if c3: 
                page.wait_for_function("document.querySelector('select[name=\"f_category_code3\"]').options.length > 1")
                page.select_option('select[name="f_category_code3"]', str(c3))

            print("    🖼️ 이미지 업로드")
            if product.get('기본이미지1') and os.path.exists(product.get('기본이미지1')):
                page.set_input_files('input[name="f_img1_file"]', product.get('기본이미지1'))
                time.sleep(1)
                close_popups(context, page)
            if product.get('상세이미지') and os.path.exists(product.get('상세이미지')):
                page.set_input_files('input[name="f_goods_explain_img_file"]', product.get('상세이미지'))
                time.sleep(1)
                close_popups(context, page)

            page.fill('input[name="f_remain_qnt"]', FIXED_VALUES["재고수량"])
            page.fill('input[name="f_material"]', product.get('소재재질') or "상세설명 참조")
            
            if '한국' in product.get('원산지', '') or '국산' in product.get('원산지', ''):
                page.click('input[name="f_home_divi"][value="1"]')
            else:
                page.click('input[name="f_home_divi"][value="2"]')
                try: page.select_option('#select_home_02', 'ZD000002') 
                except: pass

            page.click('input[name="f_delivery_fee_kind"][value="1"]')
            page.click('input[name="f_delivery_method"][value="1"]')
            page.click('input[name="delivery_area"][value="1"]')
            page.click('input[name="f_delivery_group_yn"][value="N"]') 
            page.select_option('select[name="f_tax_method"]', FIXED_VALUES["과세여부"])
            page.select_option('select[name="f_credit"]', FIXED_VALUES["판매단위"])
            page.select_option('select[name="f_delivery_limit"]', FIXED_VALUES["납품기간"])

            page.evaluate(f"""() => {{
                const ret = document.querySelector('input[name="f_return_fee"]');
                const exch = document.querySelector('input[name="f_exch_fee"]'); 
                if(ret) ret.value = '{FIXED_VALUES["반품배송비"]}';
                if(exch) exch.value = '{FIXED_VALUES["교환배송비"]}';
            }}""")

            try:
                if not page.is_checked('input[name="f_jeju_delivery_yn"]'):
                    page.click('input[name="f_jeju_delivery_yn"]')
                page.fill('input[name="f_jeju_delivery_fee"]', FIXED_VALUES["제주배송비"])
            except: pass

            register_g2b_info(page, product) # [NEW] G2B번호
            register_kc_info(page, product) # [UPDATED] KC Fallback
            register_smart_editor(page)
            enable_page_scroll(page)

            submit_product(context, page) # [Wait 20s included]

            print("\n    👀 [Check] 화면 전환 확인 (30초 대기)...")
            time.sleep(30)
            
            print(f">>> ✅ [{idx+1}] 완료")
            remove_success_product(product, products)

        browser.close()
        print(">>> 봇 종료")

if __name__ == "__main__":
    run_s2b_bot()