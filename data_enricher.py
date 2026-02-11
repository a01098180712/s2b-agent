import json
import time
import os
import subprocess
import random
import re
from playwright.sync_api import sync_playwright

# ======================================================
# [설정]
# ======================================================
DATA_FILE = 's2b_bot_input.json'
CDP_PORT = 9222
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"

# S2B 메인 주소 (로그인 상태면 메인으로 이동됨)
S2B_SEARCH_HOME = "https://www.s2b.kr/S2BNCustomer/S2B/"
G2B_SEARCH_URL = "https://goods.g2b.go.kr:8053/search/unifiedSearch.do?searchWord={keyword}"

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DIR = r"C:\ChromeDev"

# ======================================================
# [모듈 1] 브라우저 제어
# ======================================================
def launch_chrome():
    print(f"🚀 [System] 데이터 수집용 Chrome 실행 중... (Port: {CDP_PORT})")
    if not os.path.exists(CHROME_PATH):
        print(f"❌ 크롬 실행 파일을 찾을 수 없습니다: {CHROME_PATH}")
        return False

    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={CHROME_USER_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "--window-size=1600,1000"
    ]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"    ❌ Chrome 실행 실패: {e}")
        return False

def kill_chrome():
    try:
        subprocess.run(
            'wmic process where "name=\'chrome.exe\' and commandline like \'%ChromeDev%\'" call terminate',
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        time.sleep(2)
    except: pass

# ======================================================
# [모듈 2] S2B 사이트 검색 로직 (강화됨)
# ======================================================
def search_from_s2b(context, page, model_name):
    """
    S2B에서 모델명 검색 -> KC/G2B 번호 추출 (로직 강화)
    """
    print(f"    [1단계] S2B 사이트 검색 시도: {model_name}")
    
    try:
        # S2B 메인 이동
        page.goto(S2B_SEARCH_HOME, wait_until="domcontentloaded", timeout=20000)
        time.sleep(2) # 로딩 대기

        # -------------------------------------------------
        # [수정 1] 검색창 찾기 및 입력 강화
        # -------------------------------------------------
        search_input = None
        # S2B 상단 검색창의 가능한 선택자들을 순차적으로 시도
        selectors = [
            "input#unifiedSearchQuery", # ID가 명확한 경우
            "input[name='query']", 
            "input[title*='검색']", 
            "input[type='text']" # 최후의 수단
        ]
        
        for sel in selectors:
            if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                search_input = page.locator(sel).first
                break
        
        if not search_input:
            print("    ⚠️ S2B 검색창을 찾을 수 없습니다. (선택자 확인 필요)")
            return None

        # 입력: 사람처럼 한 글자씩 타이핑 (보안 키패드 우회)
        search_input.click()
        search_input.clear()
        time.sleep(0.5)
        # page.keyboard.type을 사용하여 한 글자씩 입력
        page.keyboard.type(model_name, delay=100) 
        time.sleep(0.5)
        
        # -------------------------------------------------
        # [수정 2] 검색 실행 (엔터 + 버튼 클릭 이중 시도)
        # -------------------------------------------------
        page.keyboard.press("Enter")
        time.sleep(1)
        
        # 엔터로 반응 없으면 돋보기 버튼 클릭 시도
        try:
            # 검색 버튼(보통 input 옆에 있는 a 태그나 button)
            search_btn = page.locator("a.btn_search, button.btn_search, img[alt='검색']").first
            if search_btn.is_visible():
                search_btn.click()
        except: pass

        # -------------------------------------------------
        # [수정 3] 결과 대기 및 파싱
        # -------------------------------------------------
        print("    ⏳ 검색 결과 로딩 중...")
        time.sleep(3) # 충분한 대기
        
        # 결과 없음 체크
        content = page.content()
        if "검색된 결과가 없습니다" in content or "조회된 데이터가 없습니다" in content:
            print("    ⚠️ S2B 검색 결과 없음")
            return None

        # 상세 페이지 진입 (팝업 감지)
        # 결과 리스트의 첫 번째 상품 클릭
        try:
            with context.expect_page(timeout=10000) as popup_info:
                # 테이블의 첫 번째 행의 링크 클릭
                # 보통 tbody tr:first-child a
                first_link = page.locator("tbody tr").first.locator("a").first
                if first_link.count() > 0:
                    first_link.click()
                else:
                    print("    ⚠️ 결과 목록에서 링크를 찾을 수 없습니다.")
                    return None
            
            popup = popup_info.value
            popup.wait_for_load_state("domcontentloaded")
            time.sleep(2)
            
            # 정보 추출
            popup_text = popup.locator("body").inner_text()
            result = {}
            
            # G2B 번호 (물품목록번호 16자리 중 뒤 8자리)
            # 패턴: 숫자8자리-숫자8자리
            g2b_match = re.search(r"(\d{8})-(\d{8})", popup_text)
            if g2b_match:
                result['g2b'] = g2b_match.group(2)
                print(f"    🎉 S2B에서 G2B 번호 발견: {result['g2b']}")
            
            # KC 번호 (다양한 패턴)
            kc_patterns = [
                r"[A-Z]{2}\d{5}-\d{4}[A-Z]?",  # 안전인증 (HU07...)
                r"[A-Z]{2,4}-[A-Z]{3}-.+",     # 방송통신 (MSIP...)
                r"[A-Z]{2}\d{2}-\d{2}-\d{4}",  # 기타
                r"제\s?\d{4}-.+호"             # 제 2022-... 호
            ]
            
            for pat in kc_patterns:
                matches = re.findall(pat, popup_text)
                if matches:
                    # 너무 짧거나 이상한 값 필터링
                    valid_kc = [m for m in matches if len(m) > 5]
                    if valid_kc:
                        result['kc'] = valid_kc[0]
                        print(f"    🎉 S2B에서 KC 번호 발견: {result['kc']}")
                        break
            
            popup.close()
            return result

        except Exception as e:
            print(f"    ⚠️ 상세 페이지 진입/분석 실패: {e}")
            return None

    except Exception as e:
        print(f"    ❌ S2B 검색 프로세스 오류: {e}")
        return None

# ======================================================
# [모듈 3] G2B 사이트 검색 로직 (유지)
# ======================================================
def search_from_g2b(page, model_name):
    print(f"    [2단계] G2B 목록시스템 검색 시도: {model_name}")
    try:
        clean_model = re.sub(r'[^a-zA-Z0-9가-힣\s]', '', model_name).strip()
        target_url = G2B_SEARCH_URL.format(keyword=clean_model)
        
        page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(1.5)
        
        if "검색된 결과가 없습니다" in page.content():
            print("    ⚠️ G2B 결과 없음")
            return None

        body_text = page.locator("body").inner_text()
        match = re.search(r"(\d{8})-(\d{8})", body_text)
        
        if match:
            id_code = match.group(2)
            print(f"    ✅ G2B에서 번호 확보: {id_code}")
            return {'g2b': id_code}
        return None
    except: return None

# ======================================================
# [실행] 메인 루프
# ======================================================
def run_enricher():
    print(">>> [Data Enricher] 데이터 보강 (S2B 검색 강화판)")
    if not os.path.exists(DATA_FILE): return

    with open(DATA_FILE, 'r', encoding='utf-8') as f: data = json.load(f)

    # 모델명이 있는 상품만 대상
    targets = [i for i, item in enumerate(data) if item.get('모델명') and item.get('모델명') != '없음']
    
    if not targets: print("🎉 처리할 대상이 없습니다."); return

    kill_chrome(); launch_chrome()

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_URL)
            context = browser.contexts[0]
            page = context.new_page()
            updated_cnt = 0
            
            for i, idx in enumerate(targets):
                item = data[idx]
                model = item['모델명']
                print(f"\n[{i+1}/{len(targets)}] '{item['물품명']}' (모델: {model})")
                
                # 1. S2B 검색 (강화된 로직)
                result = search_from_s2b(context, page, model)
                
                # 2. 실패 시 G2B 검색
                if not result or not result.get('g2b'):
                    g2b_res = search_from_g2b(page, model)
                    if g2b_res:
                        if not result: result = {}
                        result['g2b'] = g2b_res['g2b']

                # 3. 데이터 업데이트
                if result:
                    has_change = False
                    
                    if result.get('g2b'):
                        print(f"    🔄 G2B 번호 업데이트: {result['g2b']}")
                        data[idx]['G2B분류번호'] = result['g2b']
                        has_change = True
                    
                    if result.get('kc'):
                        print(f"    🔄 KC 번호 교체 (S2B 우선) & 기존 백업")
                        kc_val = result['kc']
                        
                        # 기존 정보 백업
                        for key in ['KC_전기_번호', 'KC_생활_번호', 'KC_방송_번호', 'KC_어린이_번호']:
                            if data[idx].get(key):
                                data[idx][f'{key}_Backup'] = data[idx][key]
                                data[idx][key] = ""
                        
                        # 새 정보 입력 (간단 분류)
                        if "HU" in kc_val or "SU" in kc_val or re.match(r'[A-Z]{2}\d{5}', kc_val):
                            data[idx]['KC_전기_번호'] = kc_val
                        elif "MSIP" in kc_val or "R-R" in kc_val:
                            data[idx]['KC_방송_번호'] = kc_val
                        else:
                            data[idx]['KC_생활_번호'] = kc_val
                        
                        has_change = True
                    
                    if has_change:
                        updated_cnt += 1
                        with open(DATA_FILE, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=4)
                
                # 봇 탐지 방지 (랜덤 딜레이)
                time.sleep(random.uniform(2, 4))
            
            print(f"\n🎉 작업 완료! {updated_cnt}개 업데이트됨.")
            
        except Exception as e: print(f"오류: {e}")
        finally: print(">>> 종료")

if __name__ == "__main__":
    run_enricher()