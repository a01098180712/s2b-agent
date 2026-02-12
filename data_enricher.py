import time
import re
import warnings
from playwright.sync_api import sync_playwright

# 경고 메시지 숨김
warnings.filterwarnings("ignore")

class S2B_Enricher:
    """
    S2B 사이트 전용 정보 보강 클래스 (Golden Key Extractor)
    - 역할: 모델명을 받아 G2B식별번호, 카테고리, 제조사, 원산지, KC인증정보를 추출
    - 특징: 하이브리드 전략 (S2B 데이터 우선 + 정밀 파싱)
    """
    
    def __init__(self, cdp_url="http://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.s2b_home = "https://www.s2b.kr/S2BNCustomer/S2B/"

    def fetch_s2b_details(self, model_name):
        """
        [핵심 함수] 실제 모델명을 인자(Argument)로 받아서 크롤링을 수행합니다.
        """
        if not model_name:
            print("    ⚠️ 모델명이 비어있어 S2B 검색을 건너뜁니다.")
            return None

        print(f"    🕵️ [S2B Enricher] 모델명 '{model_name}' 정보 탐색 중...")
        
        with sync_playwright() as p:
            try:
                # 1. 브라우저 연결
                try:
                    browser = p.chromium.connect_over_cdp(self.cdp_url)
                except Exception as e:
                    print(f"    ❌ 크롬 연결 실패: {e}")
                    return None

                context = browser.contexts[0]
                if context.pages: page = context.pages[0]
                else: page = context.new_page()

                # 2. S2B 접속 및 팝업 무력화 (필수)
                page.goto(self.s2b_home, wait_until="domcontentloaded")
                page.add_init_script("""
                    window.open = function(url) { window.location.href = url; return window; };
                    document.addEventListener('submit', (e) => { 
                        if(e.target.target === '_blank') e.target.target = '_self'; 
                    }, true);
                """)
                time.sleep(0.5)

                # 3. 검색어 입력 (외부에서 받은 model_name 사용)
                search_input = None
                for sel in ["input#unifiedSearchQuery", "input[name='query']", "input[type='text']"]:
                    if page.locator(sel).count() > 0 and page.locator(sel).first.is_visible():
                        search_input = page.locator(sel).first; break
                
                if not search_input: return None

                search_input.click(); search_input.clear()
                page.keyboard.type(model_name, delay=50) # <-- 여기에 실제 데이터가 들어갑니다
                page.keyboard.press("Enter")
                
                try: page.wait_for_selector("tbody tr", timeout=3000)
                except: pass

                # 4. 상세페이지 링크(goViewPage) 탐색
                rows = page.locator("tbody tr").all()
                target_js_code = None
                
                for i in range(min(len(rows), 5)):
                    row = rows[i]
                    links = row.locator("a").all()
                    for link in links:
                        href = link.get_attribute("href") or ""
                        txt = link.inner_text().strip()
                        if "goViewPage" in href and len(txt) > 5:
                            target_js_code = href.replace("javascript:", "")
                            break
                    if target_js_code: break
                
                if not target_js_code:
                    print("    ⚠️ S2B 검색 결과 없음 (AI 변환 값 사용 예정)")
                    return None

                # 5. 상세페이지 진입
                page.evaluate(target_js_code)
                page.wait_for_load_state("networkidle", timeout=5000)
                time.sleep(1)

                # =========================================================
                # [데이터 추출 로직] (v8 성공 로직 적용)
                # =========================================================
                result = {
                    "g2b_code": "",
                    "category": "",
                    "manufacturer": "",
                    "origin": "",
                    "kc_list": []
                }
                
                full_text = page.locator("body").inner_text()
                
                # (1) G2B 식별번호
                g2b_match = re.search(r"(\d{8})-(\d{8})", full_text)
                if g2b_match: result["g2b_code"] = g2b_match.group(2)

                # (2) 카테고리
                candidates = page.locator("div, span, p, td").all()
                for el in candidates:
                    try:
                        if not el.is_visible(): continue
                        txt = el.inner_text().strip()
                        if " > " in txt and "HOME" not in txt and "견적" not in txt and 10 < len(txt) < 100:
                            result["category"] = txt
                            break
                    except: continue

                # (3) 제조사 / 원산지 (정밀 파싱)
                try:
                    target_elements = page.get_by_text(re.compile(r"제조사.*원산지")).all()
                    target_text = ""
                    min_len = 9999
                    for el in target_elements:
                        try:
                            row_el = el.locator("xpath=./ancestor::tr[1]")
                            if row_el.count() > 0:
                                txt = row_el.inner_text().strip()
                                if len(txt) < 200 and len(txt) < min_len:
                                    min_len = len(txt)
                                    target_text = txt
                        except: continue

                    if target_text:
                        val_part = ""
                        if ":" in target_text: val_part = target_text.split(":", 1)[1].strip()
                        else: val_part = target_text.replace("제조사", "").replace("원산지", "").replace("/", "", 1).strip()
                        
                        parts = [p.strip() for p in val_part.split("/") if p.strip()]
                        if len(parts) >= 1:
                            result["origin"] = parts[-1]
                            result["manufacturer"] = parts[0]
                            if len(parts) >= 3: result["manufacturer"] = f"{parts[0]} ({parts[1]})"
                except: pass

                # (4) KC 인증번호
                all_rows = page.locator("tr").all()
                found_kc = []
                for row in all_rows:
                    row_txt = row.inner_text().strip()
                    if "인증" in row_txt or "적합성" in row_txt:
                        cat = None
                        if "어린이" in row_txt: cat = "어린이제품"
                        elif "전기" in row_txt: cat = "전기용품"
                        elif "생활" in row_txt: cat = "생활용품"
                        elif "방송" in row_txt or "통신" in row_txt: cat = "방송통신"
                        
                        if cat and "비대상" not in row_txt and "없음" not in row_txt:
                            match = re.search(r"\[([A-Za-z0-9\-]+)\]", row_txt)
                            if match:
                                code = match.group(1).strip()
                                item = {"category": cat, "code": code}
                                if item not in found_kc: found_kc.append(item)
                result["kc_list"] = found_kc

                print(f"    ✅ 확보 완료: G2B({result['g2b_code']}), 제조사({result['manufacturer']})")
                return result

            except Exception as e:
                print(f"    ❌ 오류 발생: {e}")
                return None