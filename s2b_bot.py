import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import time

# 1. 환경 변수 로드
load_dotenv()

# ======================================================
# [설정] URL 및 계정 정보
# ======================================================
S2B_LOGIN_URL = 'https://www.s2b.kr/S2BNCustomer/Login.do?type=sp&userDomain='
# upload.js에 있던 등록 페이지 URL
S2B_REGISTER_URL = 'https://www.s2b.kr/S2BNVendor/rema100.do?forwardName=goRegistView'

USER_ID = os.getenv("S2B_ID", "")
USER_PW = os.getenv("S2B_PW", "")
HEADLESS = os.getenv("HEADLESS_MODE", "false").lower() == "true"

def handle_initial_popups(context):
    """로그인 직후 뜨는 팝업 처리"""
    print("  🔍 초기 팝업 확인 중...")
    time.sleep(2)
    for page in context.pages:
        try:
            if 'certificateInfo_pop.jsp' in page.url:
                print(f"  ✅ 인증서 팝업 닫기: {page.url}")
                page.close()
        except:
            pass

def close_page_popups(page):
    """
    페이지 내부에 뜨는 레이어 팝업 닫기 (upload.js 로직 이식)
    등록 페이지 들어갔을 때 뜨는 공지사항 등을 제거합니다.
    """
    print("  🔍 페이지 내 팝업 닫기 시도...")
    try:
        # 1. 일반적인 닫기 버튼들 시도
        # upload.js의 selector: span.btn_popclose a, .btn_popclose 등
        close_btns = page.locator("span.btn_popclose a, .btn_popclose, [class*='close']")
        count = close_btns.count()
        if count > 0:
            for i in range(count):
                if close_btns.nth(i).is_visible():
                    close_btns.nth(i).click()
                    print(f"    👉 팝업 닫기 버튼 클릭 ({i+1})")
                    time.sleep(1)
        else:
            print("    👉 닫을 팝업이 없습니다.")
    except Exception as e:
        print(f"    ⚠️ 팝업 처리 중 경미한 오류(무시): {e}")

def register_dummy_product(page):
    """
    [테스트] 등록 페이지로 이동하여 상품명과 가격만 입력해봄
    목표: 폼 제어 권한 확인
    """
    print("\n>>> [테스트] 상품 등록 페이지로 이동합니다...")
    page.goto(S2B_REGISTER_URL, timeout=60000, wait_until="domcontentloaded")
    
    # 중요: 페이지 로딩 및 팝업 대기
    time.sleep(3)
    close_page_popups(page)

    print(">>> 상품 등록 폼 확인 중...")
    try:
        # upload.js의 핵심 selector: input[name="f_goods_name"]
        # 이 필드가 보여야 등록 페이지가 정상 로딩된 것임
        page.wait_for_selector('input[name="f_goods_name"]', state="visible", timeout=30000)
        print("  ✅ 등록 폼 발견!")

        # 1. 상품명 입력 테스트
        test_name = "[테스트] S2B_Agent 자동입력 확인"
        print(f"  👉 상품명 입력 시도: {test_name}")
        page.fill('input[name="f_goods_name"]', test_name)
        
        # 2. 가격 입력 테스트
        test_price = "1000"
        print(f"  👉 견적금액 입력 시도: {test_price}")
        page.fill('input[name="f_estimate_amt"]', test_price)

        print(">>> ✅ 폼 제어 테스트 성공! (입력된 상태로 10초 대기)")
        time.sleep(10) # 사용자가 화면을 볼 수 있게 대기

    except Exception as e:
        print(f"!!! 폼 제어 실패: {e}")
        print("  (힌트: 로그인이 풀렸거나, 페이지 로딩이 너무 느릴 수 있습니다.)")

def run_s2b_bot():
    print(">>> [S2B_Agent] 봇을 시작합니다...")
    
    if not USER_ID or not USER_PW:
        print("!!! 오류: .env 파일 설정을 확인하세요.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, args=["--start-maximized"])
        context = browser.new_context(no_viewport=True)
        
        # --- 로그인 절차 ---
        print(f">>> 로그인 페이지 이동: {S2B_LOGIN_URL}")
        page = context.new_page()
        try:
            page.goto(S2B_LOGIN_URL, timeout=60000, wait_until="domcontentloaded")
        except:
            pass

        try:
            print(">>> 아이디 입력창 대기...")
            page.wait_for_selector('form[name="vendor_loginForm"] [name="uid"]', state="visible", timeout=30000)
            
            page.fill('form[name="vendor_loginForm"] [name="uid"]', USER_ID)
            page.fill('form[name="vendor_loginForm"] [name="pwd"]', USER_PW)
            page.click('form[name="vendor_loginForm"] .btn_login > a')
            print(">>> 로그인 버튼 클릭. 이동 대기...")
            
            # 메인 페이지 로딩 대기 (충분히)
            time.sleep(5)
            handle_initial_popups(context)
            
            # --- [신규] 등록 페이지 테스트 ---
            register_dummy_product(page)

        except Exception as e:
            print(f"!!! 에러 발생: {e}")
        
        finally:
            print(">>> 브라우저를 종료합니다.")
            browser.close()

if __name__ == "__main__":
    run_s2b_bot()