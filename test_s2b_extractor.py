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
    print(f">>> [S2B Final v8] 모델명: {TEST_MODEL}")
    print("    👉 전략: 특정 텍스트가 포함된 '행(Row)' 전체를 가져와서 문자열 분해")
    
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

                # 3. 제조사 / 원산지 (Row Text Slicing 방식)
                manufacturer = "정보없음"
                origin = "정보없음"
                
                try:
                    # '제조사'와 '원산지'라는 글자가 모두 포함된 요소(td, th, span 등)를 찾음
                    # 그리고 그 중에서 가장 텍스트 길이가 짧은 것(상위 테이블 제외)을 선택
                    target_elements = page.get_by_text(re.compile(r"제조사.*원산지")).all()
                    
                    target_text = ""
                    min_len = 9999
                    
                    for el in target_elements:
                        # 요소의 부모 행(tr) 텍스트를 가져옴
                        try:
                            # 현재 요소가 속한 가장 가까운 tr 찾기
                            row_el = el.locator("xpath=./ancestor::tr[1]")
                            if row_el.count() > 0:
                                txt = row_el.inner_text().strip()
                                # 배송비 등 불필요한 정보가 너무 많이 섞인(길이가 긴) 행은 무시
                                if len(txt) < 150 and len(txt) < min_len:
                                    min_len = len(txt)
                                    target_text = txt
                        except: continue

                    if target_text:
                        # 텍스트 예시: "제조사 / 원산지 : 삼성전자 / SAMSUNG / 말레이시아"
                        # 1. 콜론(:)으로 라벨과 값 분리
                        if ":" in target_text:
                            value_part = target_text.split(":", 1)[1].strip()
                        else:
                            # 콜론이 없으면 라벨 제거
                            value_part = target_text.replace("제조사", "").replace("원산지", "").replace("/", "", 1).strip()
                        
                        # 2. 슬래시(/)로 값 분리
                        # "삼성전자 / SAMSUNG / 말레이시아" -> ["삼성전자", "SAMSUNG", "말레이시아"]
                        parts = [p.strip() for p in value_part.split("/") if p.strip()]
                        
                        if len(parts) >= 1:
                            origin = parts[-1]      # 맨 뒤는 항상 원산지
                            manufacturer = parts[0] # 맨 앞은 항상 제조사
                            
                            # 중간에 영문명 등이 있으면 괄호로 병기
                            if len(parts) >= 3:
                                manufacturer = f"{parts[0]} ({parts[1]})"

                except Exception as e:
                    print(f"    ⚠️ 파싱 오류: {e}")

                print(f"    🏭 제조사: {manufacturer}")
                print(f"    🌏 원산지: {origin}")
                
                # 4. KC 인증번호
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