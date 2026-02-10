from google import genai

# ==========================================
# 1. 여기에 발급받은 Gemini API Key를 입력하세요
API_KEY = "AIzaSyB_tIBEd8oFlLVco-pHiKU4yhtsbvsqtCs"
# ==========================================

def check_my_quota():
    print("🔍 [Gemini API] 사용 한도(Quota) 및 할당량 확인 중...\n")
    
    try:
        client = genai.Client(api_key=API_KEY)
        
        # 현재 내 API 키가 사용할 수 있는 모델 리스트와 설정값 가져오기
        # 주로 사용하시는 gemini-1.5-pro와 gemini-1.5-flash 정보를 타겟팅합니다.
        target_models = ['models/gemini-1.5-pro', 'models/gemini-1.5-flash']
        
        print(f"{'모델명':<25} | {'분당 요청수(RPM)':<15} | {'분당 토큰수(TPM)':<15}")
        print("-" * 60)

        for model in client.models.list():
            if model.name in target_models:
                # 각 모델의 할당량 정보 출력
                # 기본적으로 무료 티어(Free)와 유료 티어(Pay-as-you-go)에 따라 수치가 다릅니다.
                print(f"{model.name:<25} | {model.base_model_id:<15} | {model.supported_generation_methods}")
                
        print("\n💡 참고: 상세한 일일 누적 사용량과 잔여량은")
        print("   https://aistudio.google.com/app/plan 에서 실시간 그래프로 확인하는 것이 가장 정확합니다.")

    except Exception as e:
        print(f"❌ 정보 확인 실패: {str(e)}")

if __name__ == "__main__":
    check_my_quota()