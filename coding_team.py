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

# [필수] 테스트용 쿠팡 URL (사용자 지정)
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
# 🤖 AI 개발팀 (Manager) v4.2 - Strategic & Safe
# =========================================================
class AI_Dev_Team:
    def __init__(self):
        print("="*60)
        print("🤖 [AI 팀장 v4.2] 전략 수정: 데이터 명세화 & 프로필 인젝션")
        self.review_model = "gemini-2.5-pro"
        print(f"   - 검수 모델: {self.review_model}")
        print("   - 안전 장치: 재시도 3회 제한, 보안 차단 시 즉시 중단")
        print("="*60 + "\n")

    # [1] 코드 작성 (ChatGPT)
    def ask_coder(self, task, error_log=None, reviewer_feedback=None):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # [안전장치] 보안 차단(403, Access Denied) 감지 시 전략 변경 유도
        if error_log and ("Access Denied" in error_log or "403" in error_log):
            print("🚨 [Critical] 봇 탐지됨. 일반적인 수정으로는 불가능합니다.")
            task += "\n\n[긴급 추가 지침] 단순 코드 수정 금지! 브라우저 실행 시 '사용자 프로필(User Data Dir)'을 로드하는 방식으로 코드를 전면 수정하세요."

        system_prompt = f"""
        너는 Python/Playwright 크롤링 전문가야.
        
        [핵심 원칙]
        1. 코드 상단 주석: "# Generated at: {current_time} (v4.2)"
        2. **데이터 명세 준수**: S2B 등록에 필요한 필드(상품명, 가격, 이미지, 제조사, 원산지, KC인증)를 반드시 수집해야 함.
        3. **실행 보장**: 문법 오류 절대 금지.
        4. **비용 절감**: 불필요한 재시도를 줄이고, 확실한 선택자(Selector)를 사용.
        """
        
        # 메시지 구성
        messages = [{"role": "system", "content": system_prompt}]
        
        if error_log:
            messages.append({"role": "user", "content": f"이전 실행 에러:\n{error_log}\n\n위 에러를 해결하도록 코드를 수정해."})
        elif reviewer_feedback:
            messages.append({"role": "user", "content": f"검수자(Gemini) 피드백:\n{reviewer_feedback}\n\n위 지적사항을 반영해."})
        else:
            messages.append({"role": "user", "content": f"작업 지시서:\n{task}"})

        try:
            response = gpt_client.chat.completions.create(
                model="gpt-4o", messages=messages
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

    # [2] 실행 검증 (Local Execution)
    def execute_code(self, filename):
        print(f"🏃 [System] '{filename}' 실행 테스트... (URL 주입)")
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
            # URL 자동 입력
            stdout, stderr = process.communicate(input=f"{TEST_COUPANG_URL}\n", timeout=60)
            
            if process.returncode == 0:
                # 내부 에러 체크
                if "Error" in stdout or "Exception" in stdout:
                     return False, stdout
                print("   ✅ [실행 성공]")
                return True, stdout
            else:
                print("   💥 [실행 실패]")
                return False, stderr
        except Exception as e:
            return False, str(e)

    # [3] 검수 (Gemini)
    def ask_reviewer(self, code):
        print(f"🧐 [Gemini] 데이터 무결성 및 S2B 규정 검수 ({self.review_model})...")
        
        system_instruction = """
        당신은 'S2B 데이터 검수관'입니다.
        코드가 아래 [필수 수집 항목]을 정확히 크롤링하는지 확인하세요.

        [필수 수집 항목]
        1. 상품명 (특수문자 정제 로직 포함 여부)
        2. 가격 (숫자 변환 여부)
        3. 이미지 (메인/상세 이미지 다운로드 및 절대경로 저장)
        4. 원산지/제조사 (없으면 '상세설명 참조' 처리 여부)
        5. KC인증 (정보 수집 로직 존재 여부)

        [판정 기준]
        - 위 항목 중 하나라도 누락되면 즉시 "FAIL"과 함께 누락된 항목을 지적하세요.
        - 봇 탐지 회피(Stealth) 로직이 빈약하면 "FAIL"을 주고 'User Data Dir' 사용을 권장하세요.
        """
        
        try:
            res = gemini_client.models.generate_content(
                model=self.review_model, 
                contents=f"코드 검수 요청:\n{code[:30000]}",
                config=GenerateContentConfig(system_instruction=system_instruction)
            )
            return res.text.strip() if res.text else "PASS"
        except Exception as e:
            return f"FAIL: API Error - {str(e)}"

    # [메인]
    def run(self, task, filename):
        error_log = None
        feedback = None
        
        # [비용 절감] 시도 횟수 3회로 축소
        for attempt in range(3):
            print(f"\n🔄 [Cycle {attempt+1}/3] 작업 진행 중...")
            
            code = self.ask_coder(task, error_log, feedback)
            if not code: return

            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            
            success, log = self.execute_code(filename)
            
            if success:
                review = self.ask_reviewer(code)
                if "PASS" in review.upper() and "FAIL" not in review.upper():
                    print(f"\n🎉 [완료] 테스트 통과! 파일: {filename}")
                    print(f"   📄 로그 요약:\n{log[:200]}...")
                    return
                else:
                    print(f"   🚫 [반려] 검수관 지적사항 발생.")
                    feedback = review
                    error_log = None
            else:
                print(f"   💥 [실행 오류] 수정 필요.")
                error_log = log
                feedback = None
                
                # [안전장치] 봇 탐지 에러가 반복되면 조기 종료
                if "TargetClosedError" in log or "403" in log:
                    print("   ⚠️ [경고] 봇 탐지됨. 무리한 재시도 대신 종료합니다.")
                    break

        print(f"\n🚨 [종료] 3회 시도 후 미해결. (마지막 파일 저장됨: {filename})")

if __name__ == "__main__":
    team = AI_Dev_Team()
    
    # [데이터 명세 & 전략이 포함된 작업 지시서]
    task_description = """
    [목표: coupang_crawler.py 개발 - S2B 데이터 확보 및 생존 전략]
    
    1. **수집 데이터 명세 (S2B 필수)**:
       - `product_name`: 상품명 (S2B 금지어 '로켓, 최저가, 추천' 제거 필수)
       - `price`: 판매가 (숫자형변환, 0원이면 수집 제외)
       - `origin`: 원산지 (상세정보 표에서 추출, 실패 시 '상세설명 참조')
       - `maker`: 제조사 (상세정보 표에서 추출)
       - `kc_info`: KC인증번호 (텍스트 추출, 없으면 '대상아님')
       - `images`: 메인/상세 이미지 -> `C:\\S2B_Agent\\images`에 다운로드 (절대경로 List)
       
    2. **생존 전략 (Anti-Bot Level 2)**:
       - 단순 Stealth로는 부족함. **Chrome 사용자 프로필(User Data Dir)**을 로드하는 방식을 적용할 것.
       - Playwright 실행 시 `launch_persistent_context`를 사용하거나 `user_data_dir` 인자를 사용하여,
         현재 사용자의 로그인 정보(쿠키)를 그대로 유지한 채 브라우저를 열도록 작성하라.
         (경로 예시: `./user_data` 폴더 자동 생성 및 사용)
         
    3. **실행 로직**:
       - `input("URL: ")`로 입력받아 크롤링 수행.
       - 결과는 `s2b_complete_data.json`에 저장.
       - 에러 발생 시(Timeout 등) 3회 재시도 `try-except` 필수.
    """
    
    team.run(task_description, "coupang_crawler.py")