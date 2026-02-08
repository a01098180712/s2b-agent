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
# 🤖 AI 개발팀 (Manager) v4.3 - History & Debugging
# =========================================================
class AI_Dev_Team:
    def __init__(self):
        print("="*60)
        print("🤖 [AI 팀장 v4.3] 디버깅 강화 및 실패 이력 학습 모드")
        self.review_model = "gemini-2.5-pro"
        print(f"   - 검수 모델: {self.review_model}")
        print("   - 기능: 에러 상세 출력, 이전 시도 교훈 반영")
        print("="*60 + "\n")

    # [1] 코드 작성 (ChatGPT) - 히스토리 반영
    def ask_coder(self, task, attempt_history):
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 이전 실패 내역 정리
        history_text = ""
        if attempt_history:
            print(f"\n🔍 [ChatGPT] 이전 {len(attempt_history)}번의 실패 원인을 분석하여 코드를 수정합니다.")
            history_text = "\n[이전 시도 실패 내역 (반드시 참고하여 같은 실수 반복 금지)]\n"
            for i, h in enumerate(attempt_history):
                history_text += f"--- {i+1}차 시도 실패 원인 ---\n{h['reason']}\n-------------------------\n"

        system_prompt = f"""
        너는 Python/Playwright 크롤링 전문가야. (S2B 데이터 수집 전용)
        
        [핵심 전략]
        1. **User Data Dir 필수**: 쿠팡 봇 탐지를 피하기 위해 브라우저 실행 시 반드시 사용자의 프로필 경로(user_data_dir)를 사용해야 해.
        2. **실행 보장**: 문법 오류나 없는 선택자(Selector) 사용 금지.
        3. **데이터 명세 준수**: 상품명, 가격, 이미지, 원산지, KC인증 정보를 꼭 수집할 것.
        4. **코드 상단 주석**: "# Generated at: {current_time} (v4.3)"
        """
        
        user_msg = f"""
        [작업 지시서]
        {task}

        {history_text}
        
        위 실패 내역을 분석하고, 완벽하게 작동하는 코드를 다시 작성해줘.
        오직 파이썬 코드 블록만 출력해.
        """

        try:
            response = gpt_client.chat.completions.create(
                model="gpt-4o", 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ]
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
            stdout, stderr = process.communicate(input=f"{TEST_COUPANG_URL}\n", timeout=60)
            
            if process.returncode == 0:
                if "Error" in stdout or "Exception" in stdout:
                     return False, stdout # 실행은 됐으나 내부에러
                print("   ✅ [실행 성공]")
                return True, stdout
            else:
                return False, stderr # 파이썬 에러 (Traceback)
        except Exception as e:
            return False, str(e)

    # [3] 검수 (Gemini)
    def ask_reviewer(self, code, execution_log):
        print(f"🧐 [Gemini] 데이터 품질 및 규정 정밀 검수 ({self.review_model})...")
        
        system_instruction = """
        당신은 'S2B 데이터 검수관'입니다.
        크롤링된 결과가 S2B 등록 규정에 맞는지 확인하세요.

        [필수 점검 항목]
        1. **실제 데이터 수집 여부**: 실행 로그에 '상품명', '가격', '이미지 경로'가 찍혀 있는지 확인하세요.
        2. **S2B 규정**: 상품명에 '로켓배송', '최저가' 같은 금지어가 포함되어 있으면 FAIL입니다.
        3. **이미지**: 로컬 경로(C:\\...)로 다운로드되었는지 확인하세요.

        [결과 출력]
        - 통과 시: "PASS"
        - 실패 시: "FAIL: [구체적인 이유]"
        """
        
        prompt = f"""
        [코드]
        {code[:20000]}

        [실행 결과 로그 (데이터 확인용)]
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
        attempt_history = [] # 실패 기록 저장소
        
        for attempt in range(3):
            print(f"\n🔄 [Cycle {attempt+1}/3] 개발 및 수정 진행 중...")
            
            # 1. 코딩 (이전 실패 기록 전달)
            code = self.ask_coder(task, attempt_history)
            if not code: return

            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)
            
            # 2. 실행
            success, log = self.execute_code(filename)
            
            if success:
                # 3. 성공 시 -> 데이터 검수
                review = self.ask_reviewer(code, log)
                if "PASS" in review.upper() and "FAIL" not in review.upper():
                    print(f"\n🎉 [최종 승인] 모든 테스트 통과! 파일: {filename}")
                    print(f"   📄 최종 로그 요약:\n{log[:300]}...")
                    return
                else:
                    print(f"   🚫 [반려] Gemini 검수 실패.")
                    print(f"   📝 [검수 피드백]: {review}")
                    # 실패 기록 저장
                    attempt_history.append({"reason": f"실행은 성공했으나 데이터 검수 실패:\n{review}"})
            else:
                print(f"   💥 [실행 오류] 파이썬 런타임 에러.")
                print(f"   📝 [에러 로그]:\n{log[:500]}...") # 에러 내용 출력
                # 실패 기록 저장
                attempt_history.append({"reason": f"파이썬 실행 중 에러 발생:\n{log}"})

                # 치명적 오류 시 조기 중단
                if "TargetClosedError" in log:
                     print("   ⚠️ 봇 탐지됨(TargetClosed). 재시도해도 실패할 확률이 높습니다.")

        print(f"\n🚨 [종료] 3회 시도 후 미해결. (마지막 파일 저장됨: {filename})")
        print("💡 [제안] 에러 로그를 확인하고, task_description을 더 구체적으로 수정해보세요.")

if __name__ == "__main__":
    team = AI_Dev_Team()
    
    task_description = """
    [목표: coupang_crawler.py - S2B 데이터 확보]
    
    1. **브라우저 설정 (중요)**:
       - `playwright.chromium.launch_persistent_context`를 사용하여 사용자의 쿠키/세션을 유지할 것.
       - `user_data_dir` 경로는 현재 폴더 내의 `./user_data` 폴더를 지정.
       - `headless=False`, `args`에 봇 탐지 회피 옵션 추가.
       
    2. **데이터 수집 (S2B 필수)**:
       - 상품명 (특수문자 제거), 가격 (숫자만), 원산지/제조사 (없으면 '상세설명 참조')
       - 이미지: 메인 1장, 상세 1장 이상 다운로드 -> `C:\\S2B_Agent\\images` 저장.
       - KC인증: 'KC인증' 텍스트가 포함된 요소 찾아서 텍스트 추출.
       
    3. **출력 및 저장**:
       - 수집된 데이터를 `print()`로 콘솔에 출력 (검수용).
       - 최종 결과는 `s2b_complete_data.json`에 저장.
    """
    
    team.run(task_description, "coupang_crawler.py")