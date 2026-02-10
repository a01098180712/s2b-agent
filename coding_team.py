import os
import sys
import subprocess
import warnings
import time
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai.types import GenerateContentConfig

# 경고 무시
warnings.filterwarnings("ignore")

# 1. 환경 설정
load_dotenv()

if not os.getenv("OPENAI_API_KEY") or not os.getenv("GEMINI_API_KEY"):
    print("❌ .env 파일에 API Key가 설정되지 않았습니다.")
    sys.exit()

# [사용자 요청 3개 URL]
TARGET_URLS = [
    "https://www.coupang.com/vp/products/8610798143?itemId=19665760789&vendorItemId=86771432026&q=%EC%A0%84%EC%9E%90%EB%A0%88%EC%9D%B8%EC%A7%80&searchId=d027098a15810727&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg787wn",
    "https://www.coupang.com/vp/products/7249246657?itemId=18436391484&vendorItemId=92006548412&q=%EC%84%A0%ED%92%8D%EA%B8%B0&searchId=c4876bb75295792&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg78m1r",
    "https://www.coupang.com/vp/products/6359373947?itemId=13418949659&vendorItemId=92995378125&q=%EB%85%B8%ED%8A%B8%EB%B6%81&searchId=e154f8483813228&sourceType=search&itemsCount=36&searchRank=2&rank=2&traceId=mlg7936e",
]

class AI_Dev_Team:
    def __init__(self):
        print("="*70)
        print("🤖 [AI 팀장 v6.2] 성공 모델 확장 (Expansion Phase)")
        print("   - 기반: v5.4.1 성공 로직 (JSON-LD + Timeout 5s)")
        print("   - 확장: Loop(3개) + KC인증/배송비/제조사 정밀 파싱")
        
        self.gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        self.coder_model = "gpt-4o"
        self.reviewer_model = "gemini-2.5-pro"
        
        self.launch_chrome_debug()
        print("="*70 + "\n")

    def launch_chrome_debug(self):
        print("🚀 [System] 디버그 모드 Chrome 상태 확인...")
        try:
            cmd = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "--remote-debugging-port=9222",
                r"--user-data-dir=C:\ChromeDebug"
            ]
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            print("   ✅ Chrome 디버그 포트(9222) 연결 준비 완료.")
        except Exception as e:
            print(f"   ⚠️ Chrome 자동 실행 실패: {e}")

    # [1] 코드 작성
    def ask_coder(self, task, attempt_history, existing_code=None):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        feedback_prompt = ""
        if attempt_history:
            last_review = attempt_history[-1]['review']
            last_log = attempt_history[-1]['log']
            feedback_prompt = f"""
            [🚨 이전 시도 실패 분석 (By Gemini)]
            <조언>{last_review}</조언>
            <로그>{last_log}</로그>
            """

        # [중요] 기존 코드가 있으면 참고하되, 구조 변경(Loop)을 위해 새로 작성 유도
        base_prompt = "성공한 로직(JSON-LD, Timeout 5s)을 유지하며, 3개 URL Loop 구조로 확장하세요."

        # [핵심] 시스템 프롬프트: 성공 DNA + S2B 필수 항목 추가
        system_prompt = """
        당신은 S2B 크롤링 전문가입니다.
        우리는 이미 'JSON-LD 파싱'과 '5초 타임아웃'으로 쿠팡 크롤링에 성공했습니다.
        이 성공 방식을 유지하면서 기능을 확장해야 합니다.
        
        [🚨 절대 원칙 (Violations = FAIL)]
        1. **CDP 연결**: `chromium.connect_over_cdp("http://localhost:9222")` 필수.
        2. **타임아웃 5초**: `page.goto(url, timeout=5000)` 및 `try-except` 필수.
        3. **브라우저 종료 금지**: `browser.close()` 절대 금지.
        
        [확장 기능 구현 가이드]
        URL 리스트를 순회하며 아래 데이터를 수집하여 `s2b_results.json`에 저장하세요.
        
        ```python
        results = []
        for url in urls:
            print(f"▶ Crawling: {url}")
            try:
                page.goto(url, timeout=5000)
            except: pass # 게릴라 전술 유지
            
            # [1] 기본 정보 (JSON-LD 우선 - 성공 로직)
            item = {"url": url, "name": "N/A", "price": 0, "image": "", "kc": "상세설명참조", "maker": "상세설명참조", "origin": "상세설명참조"}
            try:
                json_data = page.locator('script[type="application/ld+json"]').first.inner_text()
                data = json.loads(json_data)
                if isinstance(data, list): data = data[0]
                
                item["name"] = data.get("name", "N/A")
                item["image"] = data.get("image", "")
                if isinstance(item["image"], list): item["image"] = item["image"][0]
                
                offers = data.get("offers", {})
                if isinstance(offers, list): offers = offers[0]
                item["price"] = int(offers.get("price", 0))
                
                # [2] 배송비 합산 (화면 텍스트 파싱)
                # "무료배송"이 없으면 3000원 추가 (단순화 전략)
                content_text = page.content()
                if "무료배송" not in content_text:
                    item["price"] += 3000
                    print("   - 배송비 3,000원 추가됨")
                else:
                    print("   - 무료배송 상품")

            except Exception as e:
                print(f"   ⚠️ 기본 파싱 실패: {e}")
            
            # [3] S2B 필수정보 (KC/제조사/원산지) - 화면 렌더링 필요시 try-except
            # '필수 표기정보' 테이블 파싱 시도
            try:
                # 테이블이 로드될 때까지 아주 잠깐 대기 (최대 2초)
                # 실패하면 그냥 넘어감 (전체 프로세스 보호)
                page.wait_for_selector(".product-essential-info", timeout=2000)
                
                # KC 인증
                kc_el = page.locator("th:has-text('인증') + td")
                if kc_el.count() > 0: item["kc"] = kc_el.first.inner_text()
                
                # 제조국(원산지)
                origin_el = page.locator("th:has-text('제조국') + td")
                if origin_el.count() > 0: item["origin"] = origin_el.first.inner_text()
                
                # 제조자
                maker_el = page.locator("th:has-text('제조자') + td")
                if maker_el.count() > 0: item["maker"] = maker_el.first.inner_text()
                
            except:
                pass # 테이블 없으면 '상세설명참조' 유지

            results.append(item)
            print(f"   ✅ 수집 완료: {item['name']} / {item['price']}원")
            time.sleep(3) # 밴 방지용 대기
            
        # 결과 저장
        with open("s2b_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        ```
        """
        
        user_msg = f"""
        [작업 지시서]
        {task}
        {feedback_prompt}
        {base_prompt}
        오직 실행 가능한 Python 코드 전체를 출력해.
        """

        try:
            response = self.gpt_client.chat.completions.create(
                model=self.coder_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                timeout=600
            )
            code = response.choices[0].message.content
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            return code
        except Exception as e:
            print(f"❌ ChatGPT 통신 오류: {e}")
            return None

    # [2] 실행 검증
    def execute_code(self, filename):
        print(f"🏃 [System] 코드 실행 중... (최대 180초 대기)")
        try:
            process = subprocess.Popen(
                [sys.executable, "-u", filename],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=os.environ.copy()
            )
            stdout, stderr = process.communicate(timeout=180) 
            return process.returncode == 0, stdout + "\n" + stderr
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "TIMEOUT: 코드 실행 시간이 180초를 초과했습니다."
        except Exception as e:
            return False, str(e)

    # [3] 전략 검수
    def ask_reviewer(self, code, execution_log):
        print(f"🧐 [Gemini] 로그 분석 및 S2B 요건 검수 ({self.reviewer_model})...")
        
        system_instruction = """
        당신은 'S2B 데이터 검증관'입니다.
        
        [검수 기준]
        1. **연속성**: 3개의 URL 처리가 모두 로그에 있는가?
        2. **가격**: 가격이 0이 아닌가? (배송비 로직 작동 확인)
        3. **추가정보**: KC, 제조사 정보 추출 시도 흔적이 있는가?
        4. **생존**: 스크립트가 에러 없이 끝까지 완료되었는가?
        
        [출력]
        PASS 또는 FAIL: [이유] / [해결책]
        """
        
        prompt = f"""
        [작성된 코드]
        {code[:15000]}
        [실행 로그]
        {execution_log[:10000]}
        """
        
        try:
            res = self.gemini_client.models.generate_content(
                model=self.reviewer_model, 
                contents=prompt,
                config=GenerateContentConfig(system_instruction=system_instruction)
            )
            return res.text.strip() if res.text else "PASS"
        except Exception as e:
            return f"FAIL: Gemini API Error - {str(e)}"

    def run(self, task, filename):
        attempt_history = []
        max_attempts = 3
        
        for attempt in range(max_attempts):
            print(f"\n🔄 [Cycle {attempt+1}/{max_attempts}] 협업 사이클 시작...")
            
            existing_code = None
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f: existing_code = f.read()
                    if attempt > 0: print(f"   ℹ️ 이전 코드를 로드하여 개선 작업을 시작합니다.")
                except: pass

            print("   ✍️ ChatGPT가 코드를 작성/수정하고 있습니다... (기다려주세요)")
            code = self.ask_coder(task, attempt_history, existing_code)
            
            if not code: return

            with open(filename, "w", encoding="utf-8") as f: f.write(code)
            
            success_exec, log = self.execute_code(filename)
            
            review = self.ask_reviewer(code, log)
            
            if "PASS" in review.upper() and "FAIL" not in review.upper():
                print(f"\n🎉 [최종 승인] 프로젝트 성공! 파일: {filename}")
                print(f"   📝 [최종 로그]\n{log}")
                return
            else:
                print(f"   🚫 [전략 피드백] Gemini가 개선안을 도출했습니다.")
                print(f"   📝 [내용]: {review}")
                attempt_history.append({"review": review, "log": log})

        print(f"\n🚨 [최종 보고] {max_attempts}회 시도 완료.")

if __name__ == "__main__":
    team = AI_Dev_Team()
    
    # URL 리스트를 JSON 문자열로 변환하여 전달
    targets_json = json.dumps(TARGET_URLS)
    
    task_description = f"""
    [목표: coupang_crawler.py - 성공 모델 확장]
    1. **대상 URL 리스트**: {targets_json}
    2. **환경**: 포트 9222 Chrome (CDP 연결).
    3. **수집**: 
       - 기본: 상품명, 가격(배송비포함), 이미지 (JSON-LD 사용)
       - 상세: KC인증, 제조사, 원산지 (상세정보 테이블 파싱)
    4. **주의**: `browser.close()` 금지. 타임아웃 5초 무시.
    """
    
    team.run(task_description, "coupang_crawler.py")