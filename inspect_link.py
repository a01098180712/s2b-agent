import time
import os
import subprocess
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
    print(f"🚀 [Inspect V3] Chrome 실행 중... (Port: {CDP_PORT})")
    try:
        subprocess.run('wmic process where "name=\'chrome.exe\'" call terminate', 
                      shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
    except: pass

    if not os.path.exists(CHROME_PATH):
        print(f"❌ 크롬 없음: {CHROME_PATH}"); return False
    
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

def inspect_link_v3():
    print(f">>> [S2B 링크 정밀 분석 V3] 모델: {TEST_MODEL}")
    launch_chrome()
    
    with sync_playwright() as p:
        try:
            try: browser = p.chromium.connect_over_cdp(CDP_URL)
            except: print("❌ 크롬 연결 실패"); return

            context = browser.contexts[0]
            if context.pages: page = context.pages[0]
            else: page = context.new_page()

            print("    🌐 S2B 접속...")
            page.goto(S2B_HOME, wait_until="domcontentloaded")
            time.sleep(2)
            
            # 검색
            search_input = None
            for sel in ["input#unifiedSearchQuery", "input[name='query']", "input[type='text']"]:
                if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                    search_input = page.locator(sel).first; break
            
            if not search_input: print("    ❌ 검색창 없음"); return

            print(f"    🔍 검색어 입력: {TEST_MODEL}")
            search_input.click(); search_input.clear()
            page.keyboard.type(TEST_MODEL, delay=100)
            time.sleep(0.5); page.keyboard.press("Enter")
            
            print("    ⏳ 검색 결과 대기 (3초)...")
            time.sleep(3)

            # [핵심 변경] listCategory 제외하고 진짜 상품 링크 찾기
            print("    🔍 진짜 상품 링크(제목) 선별 중...")
            
            rows = page.locator("tbody tr").all()
            target_link = None
            
            for row in rows:
                links = row.locator("a").all()
                for link in links:
                    txt = link.inner_text().strip()
                    href = link.get_attribute("href") or ""
                    
                    # 1. 텍스트가 충분히 길어야 함 (상품명일 확률 높음)
                    # 2. href에 'listCategory'가 없어야 함 (제조사 필터 제외)
                    # 3. 텍스트에 모델명이 포함되면 금상첨화
                    
                    clean_model = TEST_MODEL.replace("-", "").lower()
                    clean_txt = txt.replace("-", "").lower()

                    if len(txt) > 15 and "listCategory" not in href:
                        target_link = link
                        print(f"    🎯 후보 발견: {txt[:20]}... (href: {href[:30]}...)")
                        
                        # 모델명까지 일치하면 확정
                        if clean_model in clean_txt:
                            print("       ✅ 모델명 일치! 확정합니다.")
                            break
                if target_link: break

            if target_link:
                print("\n" + "="*60)
                print("    🕵️ [진짜 상품 링크 정보]")
                print(f"    - 텍스트: {target_link.inner_text().strip()}")
                print(f"    - href: {target_link.get_attribute('href')}")
                print(f"    - onclick: {target_link.get_attribute('onclick')}")
                
                html = target_link.evaluate("el => el.outerHTML")
                print(f"    - HTML: {html}")
                print("="*60 + "\n")
                print("    ✅ 'href' 안에 있는 자바스크립트 코드가 정답입니다!")
            else:
                print("    ❌ 상품명 링크를 찾지 못했습니다. (검색 결과가 없거나 구조가 다름)")

        except Exception as e:
            print(f"!!! 오류: {e}")

if __name__ == "__main__":
    inspect_link_v3()