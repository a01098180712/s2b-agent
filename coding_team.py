import os
import sys
import shutil
import subprocess
import warnings
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from google import genai

# 경고 무시
warnings.filterwarnings("ignore")

# 1. 환경 설정
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 테스트용 쿠팡 URL (사용자 제공)
TEST_COUPANG_URL = "https://www.coupang.com/vp/products/84423419?itemId=22521950655&vendorItemId=92392491533&pickType=COU_PICK&q=%EB%A8%BC%EC%A7%80+%EC%A0%9C%EA%B1%B0+%EC%97%90%EC%96%B4+%EC%8A%A4%ED%94%84%EB%A0%88%EC%9D%B4&searchId=40a49e5b23169008&sourceType=search&itemsCount=36&searchRank=1&rank=1&traceId=mldb2blk"

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
# 🤖 AI 개발팀 (Manager) v3.0 - Execution & Debugging
# =========================================================
class AI_Dev_Team:
    def __init__(self):
        print("="*60)
        print("🤖 [AI 팀장 v3.0] 실전 코딩/실행/디버깅 시스템 가동")
        print("   - 코드를 작성하고 실제로 실행하여 검증합니다.")
        print(f"   - 테스트 URL: {TEST_COUPANG_URL[:30]}...")
        print("="*60 + "\n")

    # [1] 코드 작성/수정 (ChatGPT)
    def ask_coder(self, task, error_log=None):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if error_log:
            print(f"\n🚑 [ChatGPT] 에러를 분석하고 코드를 수정합니다...")
            print(f"   ⚠️ 발생한 에러: {error_log.splitlines()[-1]}") # 마지막 줄만 출력
            user_msg = f"""
            [긴급 수정 요청]
            작성해준 코드를 실행했더니 아래와 같은 에러가 발생했어.
            에러 원인을 분석하고, 코드를 수정해서 완벽하게 작동하도록 고쳐줘.
            
            [에러 로그]
            {error_log}
            
            [원래 요구사항]
            {task}
            """
        else:
            print(f"\n👨‍💻 [ChatGPT] 신규 코드를 작성합니다...")
            user_msg = f"요구사항: {task}"

        system_prompt = f"""
        너는 Python/Playwright 자동화 전문 개발자야.
        실제 실행 가능한 '완벽한 코드'를 작성해야 해.
        
        [필수 규칙]
        1. 코드 맨 윗줄 주석: "# Generated at: {current_time} (S2B_Agent v3.0)"
        2. Playwright 사용 시:
           - 'async/await' 필수.
           - Anti-Bot 회피 옵션(--disable-blink-features=AutomationControlled) 필수.
           - User-Agent 설정 필수.
           - Selector 대기(wait_for_selector) 사용 시 타임아웃 예외처리 필수.
        3. 코드는 마크다운(```python ... ```) 안에 작성.
        """

        try:
            response = gpt_client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_msg}]
            )
            code = response.choices[0].message.content
            # 마크다운 파싱
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            return code
        except Exception as e:
            print(f"❌ ChatGPT 통신 오류: {e}")
            return None

    # [2] 코드 실행 검증 (Local Execution)
    def execute_code(self, filename, input_val):
        print(f"🏃 [System] '{filename}' 실행 테스트 중... (최대 60초)")
        
        try:
            # subprocess로 파이썬 파일 실행 (입력값 파이프 전달)
            process = subprocess.Popen(
                [sys.executable, filename],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                env=os.environ.copy() # 현재 환경변수(.venv 등) 상속
            )
            
            # 테스트 URL 입력 및 실행 결과 대기
            stdout, stderr = process.communicate(input=f"{input_val}\n", timeout=60)
            
            if process.returncode == 0:
                print("   ✅ 실행 성공 (Exit Code 0)")
                # 성공했더라도 중요 에러 키워드가 stdout/stderr에 있는지 체크
                if "Error:" in stderr or "Traceback" in stderr:
                    return False, stderr
                return True, stdout
            else:
                print("   💥 실행 실패 (에러 발생)")
                return False, stderr

        except subprocess.TimeoutExpired:
            process.kill()
            return False, "Timeout: 프로그램이 60초 동안 응답하지 않아 강제 종료됨. (무한 루프 가능성)"
        except Exception as e:
            return False, str(e)

    # [3] S2B 규칙 검수 (Gemini)
    def ask_reviewer(self, code):
        print("🧐 [Gemini] 실행 검증 완료. S2B 가이드라인 준수 여부 확인 중...")
        prompt = f"""
        너는 S2B 등록 시스템 검수자야.
        아래 코드는 실행 테스트를 통과했어. 이제 'S2B 가이드라인' 위반 여부만 확인해.
        
        [가이드라인]
        {S2B_RULES}
        
        [체크리스트]
        1. 금지어(로켓배송, 최저가 등) 필터링 로직이 있는가?
        2. 이미지 저장 경로가 올바른가?
        
        문제 없으면 "PASS", 위반이 있으면 "FAIL: 이유"를 적어줘.
        
        [코드]
        {code[:20000]}
        """
        try:
            res = gemini_client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            return res.text.strip() if res.text else "PASS"
        except:
            return "PASS"

    # [메인]
    def run(self, task, filename):
        error_log = None
        
        # 최대 4번 수정 기회 (초안 1회 + 수정 3회)
        for attempt in range(4):
            # 1. 코딩 (초안 또는 에러 수정)
            code = self.ask_coder(task, error_log)
            if not code: return

            # 파일 저장
            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 2. 실행 테스트
            success, log = self.execute_code(filename, TEST_COUPANG_URL)
            
            if success:
                # 3. 성공 시 S2B 규칙 검사
                review = self.ask_reviewer(code)
                if "PASS" in review.upper():
                    print(f"\n🎉 [완료] 모든 테스트 통과! 파일 생성됨: {filename}")
                    print(f"   📄 실행 로그 일부:\n{log[:300]}...")
                    return
                else:
                    print(f"   🔄 실행은 되지만 S2B 규칙 위반. 수정 요청...")
                    error_log = f"실행은 성공했지만 S2B 가이드라인 위반:\n{review}"
            else:
                # 실패 시 에러 로그 확보
                print(f"   🔧 디버깅 필요. 재작업 지시...")
                error_log = log

        print(f"\n🚨 [실패] 4회 시도 후에도 해결되지 않음. 마지막 코드가 저장됨: {filename}")
        print(f"   마지막 에러:\n{error_log[:500]}...")

if __name__ == "__main__":
    team = AI_Dev_Team()
    
    # 작업 지시서
    task_description = """
    [목표: coupang_crawler.py 개발]
    쿠팡 상품 URL을 입력받아 상품명, 가격, 상세정보, 이미지를 수집하는 크롤러를 만들어줘.
    
    [핵심 요구사항]
    1. **Bot 탐지 회피**:
       - Playwright Launch 옵션: headless=False, args=['--disable-blink-features=AutomationControlled']
       - User-Agent: 리얼한 Chrome User-Agent 사용
       - navigator.webdriver 숨김 스크립트 적용
    2. **입력 처리**:
       - `input("URL 입력: ")`을 사용하여 URL을 받도록 작성 (테스트 시 자동 입력됨).
    3. **데이터 처리**:
       - 가격은 숫자만 추출 (예: "19,800원" -> 19800).
       - 상품명에서 '로켓배송', '최저가' 등 홍보성 문구 제거.
       - 이미지(메인/상세) 다운로드 -> `C:\\S2B_Agent\\images` 저장.
       - 결과는 `s2b_complete_data.json`에 저장.
    4. **오류 제어**:
       - Timeout 발생 시 즉시 종료하지 말고, 재시도하거나(최대 3회) 부드럽게 넘어가도록 처리 (try-except 필수).
       - **TargetClosedError** 방지를 위해 페이지 로딩 대기 시간(`wait_for_timeout`)을 넉넉히 줄 것.
    """
    
    team.run(task_description, "coupang_crawler.py")