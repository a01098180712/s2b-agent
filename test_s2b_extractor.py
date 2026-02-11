import time
import os
import subprocess
import re
from playwright.sync_api import sync_playwright

# ======================================================
# [설정]
# ======================================================
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
S2B_HOME = "https://www.s2b.kr/S2BNCustomer/S2B/"
TEST_MODEL = "MS23C3535AK" 

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DIR = r"C:\ChromeDev"

def launch_chrome():
    print(f"🚀 [Test] Chrome 실행 중... (Port: {CDP_PORT})")
    
    # 기존 크롬 종료 (충돌 방지)
    try:
        subprocess.run('wmic process where "name=\'chrome.exe\'" call terminate', 
                      shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
    except: pass

    if not os.path.exists(CHROME_PATH):
        print(f"❌ 크롬 없음: {CHROME_PATH}"); return False
    
    # 팝업 차단 해제 필수
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--start-maximized",
        "--disable-popup-blocking",       
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars"
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"❌ 실행 실패: {e}"); return False

def test_s2b_extraction():
    print(f">>> [S2B 최종 공략] 모델명: {TEST_MODEL}")
    print("    👉 전략: href 속성 추출 -> JS 함수 직접 실행 (Direct Execute)")
    
    launch_chrome()
    
    with sync_playwright() as p:
        try:
            try: browser = p.chromium.connect_over_cdp(CDP_URL)
            except: print("❌ 크롬 연결 실패"); return

            context = browser.contexts[0]
            try: context.grant_permissions(["popups"], origin=S2B_HOME)
            except: pass

            if context.pages: page = context.pages[0]
            else: page = context.new_page()

            print("    🌐 S2B 접속 중...")
            page.goto(S2B_HOME, wait_until="domcontentloaded")
            time.sleep(2)
            
            # 검색
            search_input = None
            for sel in ["input#unifiedSearchQuery", "input[name='query']", "input[type='text']"]:
                if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                    search_input = page.locator(sel).first; break
            
            if not search_input: print("    ❌ 검색창 없음"); return

            print(f"    🔍 검색어 입력: {TEST_MODEL}")
            search_input.click(); search_input.clear(); time.sleep(0.5)
            page.keyboard.type(TEST_MODEL, delay=100)
            time.sleep(0.5); page.keyboard.press("Enter")
            
            print("    ⏳ 검색 결과 대기 (3초)...")
            time.sleep(3)

            # ---------------------------------------------------------
            # [핵심] 1. 진짜 링크 찾기 -> 2. JS 코드 추출 -> 3. 실행
            # ---------------------------------------------------------
            print("    🖱️ 타겟 링크 탐색 및 코드 추출...")
            
            rows = page.locator("tbody tr").all()
            if not rows: print("    ⚠️ 검색 결과 없음"); return

            target_js_code = None
            clean_search_model = TEST_MODEL.replace("-", "").lower()
            
            # 상위 5개 행만 스캔
            for i in range(min(len(rows), 5)):
                row = rows[i]
                links = row.locator("a").all()
                
                for link in links:
                    txt = link.inner_text().strip()
                    href = link.get_attribute("href") or ""
                    
                    # 조건: 텍스트가 길고(상품명), href에 'goViewPage'가 있어야 함
                    if len(txt) > 10 and "goViewPage" in href:
                        # 모델명까지 맞으면 금상첨화
                        clean_txt = txt.replace("-", "").lower()
                        if clean_search_model in clean_txt:
                            print(f"    🎯 [정확도 100%] 타겟 발견: {txt[:20]}...")
                            target_js_code = href.replace("javascript:", "") # "goViewPage('...')"
                            break
                
                if target_js_code: break
            
            if not target_js_code:
                print("    ⚠️ 정확한 모델명을 못 찾음. 첫 번째 유효 링크로 시도...")
                # 첫 번째 행의 goViewPage 링크라도 잡기
                if rows:
                    links = rows[0].locator("a").all()
                    for link in links:
                        href = link.get_attribute("href") or ""
                        if "goViewPage" in href:
                            target_js_code = href.replace("javascript:", "")
                            break

            if not target_js_code:
                print("    ❌ 실행할 자바스크립트 코드를 찾지 못했습니다.")
                return

            print(f"    🚀 자바스크립트 강제 실행: \"{target_js_code}\"")

            # [팝업 열기]
            # 클릭이 아니라, 브라우저에게 코드를 실행하라고 명령함 (차단 불가)
            try:
                with context.expect_page(timeout=5000) as new_page_info:
                    page.evaluate(target_js_code)
                
                popup_page = new_page_info.value
                print("    ✅ 팝업 열기 성공! (JS Injection)")
                
                popup_page.wait_for_load_state("domcontentloaded")
                time.sleep(1.5)
                
                # 데이터 추출
                full_text = popup_page.locator("body").inner_text()
                
                print("\n    [데이터 추출 결과]")
                g2b = re.search(r"(\d{8})-(\d{8})", full_text)
                kc = re.search(r"([A-Z]{2}\d{5}-\d{4}[A-Z]?)", full_text)
                
                if g2b: print(f"    🎉 G2B 식별번호: {g2b.group(2)}")
                else: print("    ⚠️ G2B 번호 없음")
                
                if kc: print(f"    🎉 KC 번호: {kc.group(1)}")
                else: print("    ⚠️ KC 번호 없음")
                
                time.sleep(2)
                popup_page.close()
                print("\n    ✅ 테스트 최종 완료")

            except Exception as e:
                print(f"    ❌ 팝업 실행 중 오류: {e}")

        except Exception as e:
            print(f"!!! 시스템 오류: {e}")

if __name__ == "__main__":
    test_s2b_extraction()