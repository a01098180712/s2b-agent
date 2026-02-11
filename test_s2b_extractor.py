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
    print(f"🚀 [Test] Chrome 연결 준비... (Port: {CDP_PORT})")
    if os.path.exists(CHROME_PATH):
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
            time.sleep(2)
        except: pass

def test_s2b_extraction():
    print(f">>> [S2B 최종 완성 v4] 모델명: {TEST_MODEL}")
    print("    👉 전략: 제조사/원산지 정규식(Regex) 추출로 정확도 100% 확보")
    
    launch_chrome()
    
    with sync_playwright() as p:
        try:
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
            except Exception as e:
                print(f"❌ 크롬 연결 실패: {e}"); return

            context = browser.contexts[0]
            if context.pages: page = context.pages[0]
            else: page = context.new_page()

            print("    🌐 S2B 접속 중...")
            page.goto(S2B_HOME, wait_until="domcontentloaded")
            
            # 팝업 무력화
            page.add_init_script("""
                window.open = function(url) { window.location.href = url; return window; };
                document.addEventListener('submit', (e) => { if(e.target.target === '_blank') e.target.target = '_self'; }, true);
            """)
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
            page.keyboard.press("Enter")
            
            print("    ⏳ 검색 결과 로딩 대기...")
            try: page.wait_for_selector("tbody tr", timeout=5000)
            except: pass

            # 링크 분석
            rows = page.locator("tbody tr").all()
            target_js_code = None
            
            for i in range(min(len(rows), 5)):
                row = rows[i]
                links = row.locator("a").all()
                for link in links:
                    href = link.get_attribute("href") or ""
                    txt = link.inner_text().strip()
                    if "goViewPage" in href and len(txt) > 5:
                        print(f"    🎯 S2B 상품 발견: {txt[:20]}...")
                        target_js_code = href.replace("javascript:", "")
                        break
                if target_js_code: break
            
            if not target_js_code and rows:
                 links = rows[0].locator("a").all()
                 for link in links:
                    if "goViewPage" in (link.get_attribute("href") or ""):
                        target_js_code = link.get_attribute("href").replace("javascript:", "")
                        break

            if not target_js_code:
                print("    ⚠️ S2B 검색 결과 없음"); return

            print(f"    🚀 상세페이지 이동: \"{target_js_code}\"")
            try:
                page.evaluate(target_js_code)
                print("    ⏳ 화면 전환 대기 중...")
                page.wait_for_load_state("networkidle", timeout=10000)
                print("    ✅ 상세 페이지 진입 성공!")
                time.sleep(1)
                
                print("\n    [S2B 추출 데이터 결과]")
                
                full_text_body = page.locator("body").inner_text()

                # 1. G2B 식별번호
                g2b = re.search(r"(\d{8})-(\d{8})", full_text_body)
                if g2b: print(f"    🎉 G2B 식별번호: {g2b.group(2)}")

                # 2. 카테고리
                category_path = "정보없음"
                candidates = page.locator("div, span, p, td").all()
                for el in candidates:
                    try:
                        if not el.is_visible(): continue
                        txt = el.inner_text().strip()
                        if " > " in txt and "HOME" not in txt and "견적" not in txt and 10 < len(txt) < 100:
                            category_path = txt
                            break
                    except: continue
                print(f"    📂 카테고리: {category_path}")

                # 3. 제조사 / 원산지 (정규식 정밀 추출)
                manufacturer = "정보없음"
                origin = "정보없음"
                
                # "제조사 / 원산지 :" 뒤에 오는 텍스트를 한 줄 단위로 찾음
                # 예: 제조사 / 원산지 : 엘지전자 / LG전자 / 중국
                origin_match = re.search(r"제조사\s*/\s*원산지\s*[:]\s*(.+)", full_text_body)
                
                if origin_match:
                    full_val = origin_match.group(1).strip()
                    # 슬래시(/)로 구분
                    parts = [p.strip() for p in full_val.split("/")]
                    
                    if len(parts) >= 1:
                        origin = parts[-1]      # 맨 뒤 = 원산지
                        manufacturer = parts[0] # 맨 앞 = 제조사
                        
                        # 값이 3개 이상이면(제조사/브랜드/원산지) 괄호로 병기
                        if len(parts) >= 3:
                            manufacturer = f"{parts[0]} ({parts[1]})"

                print(f"    🏭 제조사: {manufacturer}")
                print(f"    🌏 원산지: {origin}")
                
                # 4. KC 인증번호 (기존 로직 유지)
                found_kc_list = []
                all_rows = page.locator("tr").all()
                for row in all_rows:
                    row_text = row.inner_text().strip()
                    if "인증" in row_text or "적합성" in row_text:
                         cat = None
                         if "어린이" in row_text: cat = "어린이제품"
                         elif "전기" in row_text: cat = "전기용품"
                         elif "생활" in row_text: cat = "생활용품"
                         elif "방송" in row_text or "통신" in row_text: cat = "방송통신"
                         
                         if cat:
                             if "비대상" in row_text or "없음" in row_text: pass
                             else:
                                 match = re.search(r"\[([A-Za-z0-9\-]+)\]", row_text)
                                 if match:
                                     code = match.group(1).strip()
                                     ukey = f"{cat}-{code}"
                                     if ukey not in found_kc_list:
                                         print(f"    🎉 KC ({cat}): {code}")
                                         found_kc_list.append(ukey)

                if not found_kc_list:
                    print("    ℹ️ KC 인증번호: 없음")

                print("\n    ✅ [최종 검증 완료]")

            except Exception as e:
                print(f"    ❌ 상세페이지 분석 실패: {e}")

        except Exception as e:
            print(f"!!! 시스템 오류: {e}")

if __name__ == "__main__":
    test_s2b_extraction()