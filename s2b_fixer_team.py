import os
import sys
import subprocess
import warnings
import time
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

# [타겟 파일]
TARGET_FILE = "test_s2b_extractor.py"

# [전략 정의] 중복 시도를 막기 위한 단계별 지침
STRATEGIES = {
    1: """
    [전략 1: JS 강제 클릭 (Force Click)]
    - 물리적인 `click()` 대신 자바스크립트 `element.evaluate("el => el.click()")`를 사용하세요.
    - 또는 `dispatchEvent(new Event('click'))`을 사용하여 이벤트를 강제로 발생시키세요.
    - 가장 기본적인 우회 방법입니다.
    """,
    2: """
    [전략 2: 속성 추출 및 직접 실행 (Attribute Parsing)]
    - 클릭(Click) 메서드를 절대 사용하지 마세요.
    - `a` 태그의 `href` 또는 `onclick` 속성값을 텍스트로 가져오세요.
    - 가져온 코드가 `javascript:`로 시작하면 `page.evaluate()`로 그 코드를 직접 실행하세요.
    - 클릭 이벤트를 감지하는 보안을 완벽히 우회할 수 있습니다.
    """,
    3: """
    [전략 3: 키보드 네비게이션 (Keyboard Interaction)]
    - 마우스 이벤트를 사용하지 마세요.
    - `element.focus()`로 링크에 포커스를 맞추세요.
    - 그 다음 `page.keyboard.press("Enter")`를 입력하여 실행하세요.
    - 사람이 키보드로 조작하는 것처럼 보여 보안을 뚫을 수 있습니다.
    """
}

class S2B_Fixer_Team:
    def __init__(self):
        print("="*70)
        print("👮 [AI 전략팀 v3.0] 3-Strike No-Repeat Strategy")
        print(f"   - 타겟: {TARGET_FILE}")
        print("   - 제한: 최대 3회 시도 (실패 시 즉시 중단)")
        print("="*70 + "\n")
        
        self.gpt_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.coder_model = "gpt-4o"
        self.advisor_model = "gemini-2.0-flash"

    def ask_coder(self, attempt_num, existing_code, advisor_feedback):
        strategy_guide = STRATEGIES.get(attempt_num, "자유롭게 시도하세요.")
        print(f"   ✍️ [ChatGPT] {attempt_num}단계 전략 적용 중...")
        
        system_prompt = f"""
        당신은 Playwright 웹 자동화 전문가입니다.
        S2B 사이트 팝업 열기 문제를 해결하기 위해 **단계별 전략**을 수행 중입니다.
        
        [현재 단계: 시도 {attempt_num}/3]
        {strategy_guide}
        
        [이전 실패 분석 (Gemini)]
        "{advisor_feedback}"
        
        [필수 구현 지침]
        1. `test_s2b_extractor.py` 전체 코드를 작성하세요.
        2. 기존의 **CDP 연결(`connect_over_cdp`)** 구조는 반드시 유지하세요 (로그인 세션 유지).
        3. 팝업 차단 해제 옵션(`--disable-popup-blocking`)을 포함하세요.
        4. 성공 판단을 위해 **G2B/KC 번호 추출 로직**을 반드시 포함하세요.
        """
        
        user_msg = f"""
        [현재 코드]
        ```python
        {existing_code}
        ```
        
        위 코드를 **[전략 {attempt_num}]**에 맞춰 전면 수정해줘.
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
            print(f"❌ ChatGPT 오류: {e}")
            return None

    def execute_code(self, filename):
        print(f"🏃 [System] 코드 실행 중...")
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
            stdout, stderr = process.communicate(timeout=60) # 60초 제한 (빠른 실패 유도)
            return process.returncode == 0, stdout + "\n" + stderr
        except subprocess.TimeoutExpired:
            process.kill()
            return False, "TIMEOUT: 실행 시간 초과 (60초)"
        except Exception as e:
            return False, str(e)

    def ask_advisor(self, log):
        print(f"🧐 [Gemini] 로그 정밀 분석 중...")
        
        prompt = f"""
        [목표] S2B 팝업 열기 및 G2B/KC 번호 추출
        
        [실행 로그]
        {log}
        
        [판단 요청]
        로그를 보고 성공 여부를 판단하세요.
        1. 성공: "PASS" (식별번호 추출됨)
        2. 실패: "FAIL: [원인]" (팝업 안열림, 에러 등)
        """
        
        try:
            res = self.gemini_client.models.generate_content(
                model=self.advisor_model, 
                contents=prompt
            )
            return res.text.strip() if res.text else "FAIL: 응답 없음"
        except:
            return "FAIL: 분석 오류"

    def run(self):
        advisor_feedback = "초기 상태입니다. 1단계 전략부터 시작하세요."
        
        if os.path.exists(TARGET_FILE):
            with open(TARGET_FILE, "r", encoding="utf-8") as f: existing_code = f.read()
        else:
            print("❌ 타겟 파일 없음")
            return

        # 딱 3번만 수행
        for attempt in range(1, 4):
            print(f"\n🔄 [Round {attempt}/3] 전략 실행: {STRATEGIES[attempt].splitlines()[1].strip()}")
            
            # 1. 코드 수정
            code = self.ask_coder(attempt, existing_code, advisor_feedback)
            if not code: break
            
            with open(TARGET_FILE, "w", encoding="utf-8") as f: f.write(code)
            
            # 2. 실행
            _, log = self.execute_code(TARGET_FILE)
            print(f"   📝 로그: {log[-300:].replace(chr(10), ' ')}...")
            
            # 3. 분석
            review = self.ask_advisor(log)
            
            if "PASS" in review.upper() and "FAIL" not in review.upper():
                print(f"\n🎉 [성공] {attempt}번째 시도만에 뚫었습니다!")
                print(f"   📂 성공 코드: {TARGET_FILE}")
                return
            else:
                print(f"   🚫 [실패] {review}")
                advisor_feedback = review
                existing_code = code # 실패한 코드 베이스로 수정하지 않고, 원본을 유지할지 고민되지만, 문맥 유지를 위해 넘김

        print(f"\n🚨 [종료] 3회 시도 모두 실패했습니다. 더 이상 진행하지 않습니다.")
        print("   👉 수동으로 로그를 확인하고 전략을 다시 수립하세요.")

if __name__ == "__main__":
    team = S2B_Fixer_Team()
    team.run()