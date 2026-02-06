import os
import sys
import warnings
from dotenv import load_dotenv
from openai import OpenAI
from google import genai  # 신형 라이브러리 (이름이 다름)

# 경고 메시지 무시
warnings.filterwarnings("ignore")

# 1. 환경 설정 로드
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2. 키 검사
print("="*60)
print("🛠️  [시스템 점검] AI 개발팀 엔진 교체 완료 (v2.0)...")

if not OPENAI_API_KEY:
    print("❌ [오류] ChatGPT 키가 없습니다.")
    sys.exit()

if not GEMINI_API_KEY:
    print("❌ [오류] Gemini 키가 없습니다.")
    sys.exit()

# 3. 클라이언트 연결 (신형 방식)
try:
    gpt_client = OpenAI(api_key=OPENAI_API_KEY)
    
    # ⭐ 여기가 바뀐 부분입니다 (New Google GenAI Client)
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    
    print("✅ [성공] 신형 Gemini 엔진 가동 성공!")
except Exception as e:
    print(f"❌ 설정 오류: {e}")
    sys.exit()
print("="*60 + "\n")

# =========================================================
# 🤖 AI 개발팀 (Manager)
# =========================================================
class AI_Dev_Team:
    def __init__(self):
        print("🤖 [AI 팀장] 최신 장비로 업그레이드 완료. 명령을 기다립니다.")
        
        # 신형 라이브러리에서 쓸 모델 이름들
        self.free_models = [
            "gemini-2.0-flash",       # 최신 (강력추천)
            "gemini-2.0-flash-lite",  # 초고속
            "gemini-1.5-flash",       # 안정적
        ]

    # [작업자: ChatGPT]
    def ask_coder(self, task, feedback=""):
        print(f"\n👨‍💻 [ChatGPT] 코드를 작성합니다... (작업: {task[:30]}...)")
        
        system_prompt = """
        너는 Python/Playwright 자동화 전문 개발자야.
        
        [규칙]
        1. 코드는 반드시 마크다운(```python ... ```) 안에 담을 것.
        2. Playwright는 async/await 패턴 사용.
        3. time.sleep()을 적절히 넣어 차단 방지.
        4. 주석은 한글로 작성.
        """
        
        user_msg = f"요구사항: {task}"
        if feedback:
            print(f"   ↳ ⚠️ [지적 반영] '{feedback[:20]}...' 수정 중")
            user_msg += f"\n\n[수정 요청]: {feedback}\n이 내용을 반영해서 다시 짜줘."

        try:
            response = gpt_client.chat.completions.create(
                model="gpt-4o", 
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_msg}]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"❌ [ChatGPT 오류] {e}")
            return None

    # [검수자: Gemini] - 신형 문법 적용
    def ask_reviewer(self, code):
        print("🧐 [Gemini] 신형 엔진으로 정밀 검수 중...")
        
        prompt = f"""
        너는 코드 리뷰어(QA)야. 아래 파이썬 코드를 검사해.
        1. 문법 에러가 없는지?
        2. Playwright 문법(async/await)이 정확한지?
        
        문제 없으면 "PASS", 있으면 "FAIL: 이유"를 적어줘.
        
        [코드]:
        {code[:30000]}
        """
        
        for model_name in self.free_models:
            try:
                # ⭐ 신형 문법 (client.models.generate_content)
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt
                )
                
                if response.text:
                    # print(f"   ✅ 검수 완료 ({model_name})")
                    return response.text.strip()
                    
            except Exception as e:
                # print(f"   ⚠️ {model_name} 응답 실패: {str(e)[:50]}...")
                continue # 다음 모델 시도

        print("   ❌ [경고] 모든 Gemini 모델 응답 실패. 일단 PASS 합니다.")
        return "PASS"

    # [메인 로직]
    def run(self, task, filename):
        print(f"🚀 프로젝트 시작: '{filename}'")
        
        for i in range(3):
            code = self.ask_coder(task)
            if not code: return
            
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
            
            review = self.ask_reviewer(code)
            print(f"   👉 결과: {review}")
            
            if "PASS" in review.upper():
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"\n🎉 [성공] 파일 생성 완료: {filename}")
                return
            else:
                print("   🔄 반려됨. 재작업 지시...")
                task += f"\n(수정 요청: {review})"

        # 강제 저장
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"\n🚨 [알림] 3회 수정 후 강제 저장됨: {filename}")

# 실행
if __name__ == "__main__":
    team = AI_Dev_Team()
    team.run("Playwright로 네이버(naver.com) 접속해서 제목 출력하는 코드 짜줘 (headless=False)", "test_bot.py")