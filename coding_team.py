import os
import sys
import subprocess
import warnings
import time
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai.types import GenerateContentConfig

# 경고 무시
warnings.filterwarnings("ignore")

# 1. 환경 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# [필수] 테스트용 쿠팡 URL
TEST_COUPANG_URL = "https://www.coupang.com/vp/products/250854748?itemId=24696048102&vendorItemId=91705761409&sourceType=srp_product_ads&clickEventId=0d1f2fb0-0556-11f1-b9e9-1d76bf09c45d&korePlacement=15&koreSubPlacement=1&clickEventId=0d1f2fb0-0556-11f1-b9e9-1d76bf09c45d&korePlacement=15&koreSubPlacement=1&traceId=mlehoc0i"

# 2. 클라이언트 연결
try:
    gpt_client = OpenAI(api_key=OPENAI_API_KEY)
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"❌ API 설정 오류: {e}")
    sys.exit()

def load_s2b_rules():
    path = "s2b_rule.txt"
    return open(path, "r", encoding="utf-8").read() if os.path.exists(path) else "특별한 제약 없음."

S2B_RULES = load_s2b_rules()

# =========================================================
# 🤖 AI 개발팀 (Manager) v4.4 - CDP Stealth Mode
# =========================================================
class AI_Dev_Team:
    def __init__(self):
        print("="*60)
        print("🤖 [AI 팀장 v4.6] 전략 변경: CDP(Debug Port) 연결 모드")
        
        # [수정] API 클라이언트를 클래스 멤버 변수(self)로 초기화
        # (상단에서 import os, from openai import OpenAI 등이 되어 있어야 함)
        self.gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 크롬 자동 실행
        self.launch_chrome_debug()
        
        self.review_model = "gemini-2.5-pro"
        print(f"   - 검수 모델: {self.review_model}")
        print("="*60 + "\n")

    # [추가] 디버그 모드 크롬 자동 실행 함수
    def launch_chrome_debug(self):
        print("🚀 [System] 디버그 모드 Chrome 자동 실행 시도...")
        try:
            # 일반적인 크롬 설치 경로 확인
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            if not os.path.exists(chrome_path):
                chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            
            if not os.path.exists(chrome_path):
                print("   ⚠️ 크롬 경로를 찾을 수 없어 시스템 'chrome.exe' 명령어로 시도합니다.")
                chrome_path = "chrome.exe"

            # 사용자 요청 명령어 실행
            cmd = [
                chrome_path,
                "--remote-debugging-port=9222",
                r"--user-data-dir=C:\ChromeDebug"
            ]
            
            # 백그라운드 실행 (Popen)
            subprocess.Popen(cmd)
            print("   ✅ Chrome 실행 명령 전달 완료. (3초 대기)")
            time.sleep(3) # 브라우저 켜질 때까지 대기
        except Exception as e:
            print(f"   ⚠️ Chrome 자동 실행 실패 (수동 실행 필요): {e}")

    # [1] 코드 작성/수정 (ChatGPT)
    def ask_coder(self, task, attempt_history, existing_code=None):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 실패 내역 정리 (가장 최근 에러가 가장 중요)
        history_text = ""
        if attempt_history:
            last_error = attempt_history[-1]['reason']
            history_text = f"""
            [🚨 긴급 수정 요청]
            직전 실행에서 다음 오류가 발생했습니다. 이 오류를 해결하는 방향으로 코드를 수정하세요.
            
            [오류 로그]
            {last_error}
            """

        # 프롬프트 분기 (신규 vs 수정)
        if existing_code:
            prompt_type = "[코드 수정 모드]"
            base_prompt = f"""
            [현재 작성된 코드]
            {existing_code}
            
            [미션]
            위 '현재 코드'를 기반으로, '오류 로그'를 해결한 **완전한 Python 코드**를 다시 출력해.
            1. 기존의 성공한 로직(CDP 연결, 임포트 등)은 절대 삭제하지 마.
            2. 오류가 발생한 부분만 정밀하게 수정해.
            3. 주석에 'v4.{len(attempt_history)+1} Fix: [수정내용]'을 달아줘.
            """
        else:
            prompt_type = "[신규 작성 모드]"
            base_prompt = "처음부터 코드를 작성해. (CDP 9222 포트 연결 필수)"

        system_prompt = f"""
        너는 Python/Playwright 크롤링 전문가야.
        현재 쿠팡의 클래스명 난독화로 인해 일반적인 선택자는 모두 실패하고 있어.
        
        [🚨 긴급 전략: 메타 데이터 우선 (Meta-First Strategy)]
        데이터 수집 시 **눈에 보이는 요소(CSS)보다 메타 태그(Meta)를 최우선**으로 긁어야 해.
        
        1. **상품명 (Title)**:
           - 1순위: `page.locator('meta[property="og:title"]').get_attribute("content")`
           - 2순위: `page.locator('meta[name="twitter:title"]').get_attribute("content")`
           - 3순위: `h2` 태그들 중 텍스트 길이가 10자 이상인 것.
           
        2. **가격 (Price)**:
           - 1순위: `page.locator('meta[property="product:price:amount"]').get_attribute("content")` (존재할 경우)
           - 2순위: 스크립트 태그 내 `json` 데이터 파싱 (복잡하면 생략 가능).
           - 3순위: 화면에서 '원' 글자를 포함하는 텍스트(`:has-text("원")`)를 찾고 정규식으로 숫자만 추출.
           
        3. **이미지 (Image)**:
           - 1순위: `page.locator('meta[property="og:image"]').get_attribute("content")` (고해상도 썸네일)
           - 2순위: `img.prod-image__detail` (이건 자주 바뀌니 주의)
        
        [필수 구현 사항]
        - **CDP 연결**: `chromium.connect_over_cdp("http://localhost:9222")` 필수.
        - **대기 로직**: `page.wait_for_load_state("domcontentloaded")` 후 2초 추가 대기.
        - **출력 형식**: 성공 여부와 상관없이 수집된 변수들을 `print(f"Title: {{title}}")` 형태로 반드시 출력.
        - **예외 처리**: `try-except`를 사용하여 메타 태그가 없으면 다음 순위로 넘어가도록(Fallback) 구현.
        - **코드 상단**: "# Generated at: {current_time} (v4.8 - Meta First Strategy)"
        """
        
        user_msg = f"""
        [작업 지시서]
        {task}

        {history_text}
        
        {base_prompt}
        
        오직 실행 가능한 Python 코드 전체를 출력해. (마크다운 포맷)
        """

        try:
            # (기존 API 호출 로직 유지)
            response = self.gpt_client.chat.completions.create( # self.gpt_client로 변경 필요 (init에서 self로 선언했다면)
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ]
            )
            # ... (코드 파싱 로직 유지) ...
            code = response.choices[0].message.content
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            return code
        except Exception as e:
            print(f"❌ ChatGPT 통신 오류: {e}")
            return None

    # [메인 루프]
    def run(self, task, filename):
        attempt_history = []
        max_attempts = 3
        
        for attempt in range(max_attempts):
            print(f"\n🔄 [Cycle {attempt+1}/{max_attempts}] 코드 발전시키는 중...")
            
            # [중요] 매 루프마다 '현재 파일 상태'를 읽어야 누적 수정이 됨
            existing_code = None
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    existing_code = f.read()
                if attempt > 0:
                    print(f"   ℹ️ 직전 코드를 읽어와 수정을 시도합니다. (누적 업데이트)")

            # AI에게 코딩/수정 요청
            code = self.ask_coder(task, attempt_history, existing_code)
            
            if not code:
                print("   ⚠️ 코드가 생성되지 않았습니다. 중단.")
                return

            # 파일 저장 (덮어쓰기)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 실행 및 테스트
            success, log = self.execute_code(filename)
            
            if success:
                # 실행은 됐지만 S2B/데이터 검증 수행
                review = self.ask_reviewer(code, log)
                if "PASS" in review.upper() and "FAIL" not in review.upper():
                    print(f"\n🎉 [최종 승인] 모든 테스트 통과! 완벽합니다. 파일: {filename}")
                    return
                else:
                    print(f"   🚫 [반려] Gemini 규정 검수 실패.")
                    print(f"   📝 [피드백]: {review}")
                    attempt_history.append({"reason": f"실행은 성공했으나 검수 실패: {review}"})
            else:
                # 파이썬 실행 에러 발생
                print(f"   💥 [실행 오류] 에러 발생.")
                print(f"   📝 [로그]: {log[:500]}...") # 로그가 너무 길면 자름
                attempt_history.append({"reason": f"Python 실행 에러: {log}"})

        # 루프 종료 후
        print(f"\n🚨 [최종 보고] {max_attempts}회 시도 완료.")
        print(f"   마지막으로 수정된 코드가 {filename}에 저장되었습니다.")
        print("   사용자가 직접 실행하여 테스트해 볼 수 있습니다.")

    # [2] 실행 검증 (Local Execution)
    def execute_code(self, filename):
        print(f"🏃 [System] 실행 테스트 중... (URL 자동 입력)")
        try:
            process = subprocess.Popen(
                [sys.executable, filename],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=os.environ.copy()
            )
            # URL 입력
            stdout, stderr = process.communicate(input=f"{TEST_COUPANG_URL}\n", timeout=60)
            
            if process.returncode == 0:
                if "Error" in stdout or "Exception" in stdout:
                     return False, stdout
                print("   ✅ [실행 성공]")
                return True, stdout
            else:
                # 연결 실패 시 팁 제공
                if "Connection refused" in stderr:
                    print("   ⚠️ [주의] 크롬 디버그 모드가 실행되지 않은 것 같습니다.")
                    print("       cmd에서 'chrome.exe --remote-debugging-port=9222'를 먼저 실행하세요!")
                return False, stderr
        except Exception as e:
            return False, str(e)

    # [3] 검수 (Gemini)
    def ask_reviewer(self, code, execution_log):
        print(f"🧐 [Gemini] 데이터 및 규정 검수 ({self.review_model})...")
        
        system_instruction = """
        당신은 'S2B 데이터 검수관'입니다.
        
        [점검 항목]
        1. **CDP 연결 여부**: 코드가 `connect_over_cdp`를 사용하고 있는가?
        2. **데이터 수집**: 실행 로그에 '상품명', '가격', '이미지'가 출력되었는가?
        3. **S2B 금지어**: 결과 데이터에 '로켓', '최저가' 등이 포함되면 FAIL.

        [결과 출력]
        PASS 또는 FAIL: [이유]
        """
        
        prompt = f"""
        [코드]
        {code[:20000]}

        [실행 결과 로그]
        {execution_log[:5000]}
        """
        
        try:
            res = gemini_client.models.generate_content(
                model=self.review_model, 
                contents=prompt,
                config=GenerateContentConfig(system_instruction=system_instruction)
            )
            return res.text.strip() if res.text else "PASS"
        except Exception as e:
            return f"FAIL: API Error - {str(e)}"

    # [메인]
    def run(self, task, filename):
        attempt_history = []
        
        for attempt in range(3):
            print(f"\n🔄 [Cycle {attempt+1}/3] 개발 진행 중...")
            
            # [추가] 기존 파일이 있으면 읽어서 전달 (Refinement)
            existing_code = None
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        existing_code = f.read()
                    print(f"   ℹ️ 기존 {filename} 코드를 읽어 수정 모드로 진입합니다.")
                except:
                    pass

            code = self.ask_coder(task, attempt_history, existing_code)
            if not code: return

            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            
            success, log = self.execute_code(filename)
            
            if success:
                review = self.ask_reviewer(code, log)
                if "PASS" in review.upper() and "FAIL" not in review.upper():
                    print(f"\n🎉 [최종 승인] 모든 테스트 통과! 파일: {filename}")
                    return
                else:
                    print(f"   🚫 [반려] Gemini 검수 실패.")
                    print(f"   📝 [피드백]: {review}")
                    attempt_history.append({"reason": review})
            else:
                print(f"   💥 [실행 오류] 에러 발생.")
                print(f"   📝 [로그]: {log[:500]}...")
                attempt_history.append({"reason": log})

        print(f"\n🚨 [종료] 3회 시도 후 미해결. (디버그 모드 크롬이 켜져 있는지 확인하세요)")

if __name__ == "__main__":
    team = AI_Dev_Team()
    
    # [CDP 전용 작업 지시서]
    task_description = """
    [목표: coupang_crawler.py - CDP 기반 크롤링]
    
    1. **브라우저 연결 (Stealth 핵심)**:
       - Playwright의 `chromium.connect_over_cdp("http://localhost:9222")`를 사용하여
         이미 실행 중인 크롬 브라우저에 접속하라. (새 브라우저 실행 금지)
       - `context.pages[0]`을 가져와서 현재 열린 탭을 사용하거나 새 탭을 열어라.
       
    2. **데이터 수집 (S2B 필수)**:
       - URL 이동: 사용자 입력 URL로 `page.goto()`
       - 상품명 (특수문자 제거), 가격 (숫자만), 원산지/제조사, KC인증
       - 이미지: 메인/상세 이미지 다운로드 -> `C:\\S2B_Agent\\images`
       
    3. **출력**:
       - 수집된 데이터를 화면에 출력하고 `s2b_complete_data.json`에 저장.
       - 에러 처리: Timeout 시 재시도.
    """
    
    team.run(task_description, "coupang_crawler.py")