import os
import json
import time
import re
import requests
import difflib
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
from io import BytesIO

# ======================================================
# [설정] 환경 변수 및 상수
# ======================================================
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

INPUT_FILE = 's2b_results.json'
OUTPUT_FILE = 's2b_bot_input.json'
CATEGORY_FILE = 's2b_categories.json'
IMAGE_DIR = 'processed_images'

MAIN_IMG_SIZE = (262, 262)
DETAIL_IMG_WIDTH = 680

if not API_KEY:
    print("❌ 오류: .env 파일에 GEMINI_API_KEY가 없습니다.")
    exit()

client = genai.Client(api_key=API_KEY)
PRIMARY_MODEL = "gemini-2.0-flash" 

# ======================================================
# [모듈 1] 데이터 유틸리티
# ======================================================
class DataUtils:
    def __init__(self):
        self.raw_categories = self._load_json(CATEGORY_FILE)
        self.enforcer_pattern = re.compile(r"[^가-힣a-zA-Z0-9\s\.\,\-\_\/\(\)\[\]]")
        self.flat_categories = self._flatten_categories()
        
    def _load_json(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _flatten_categories(self):
        flat_list = []
        cats = self.raw_categories
        if 'category1' in cats:
            for c1 in cats['category1']:
                c1_txt = c1['text']; c1_val = c1['value']
                if 'category2' in cats and c1_val in cats['category2']:
                    for c2 in cats['category2'][c1_val]:
                        c2_txt = c2['text']; c2_val = c2['value']
                        key = f"{c1_val}_{c2_val}"
                        if 'category3' in cats and key in cats['category3']:
                            for c3 in cats['category3'][key]:
                                full_path = f"{c1_txt} > {c2_txt} > {c3['text']}"
                                flat_list.append({"path": full_path, "c1": c1_val, "c2": c2_val, "c3": c3['value']})
                        else:
                            full_path = f"{c1_txt} > {c2_txt}"
                            flat_list.append({"path": full_path, "c1": c1_val, "c2": c2_val, "c3": None})
                else:
                    flat_list.append({"path": c1_txt, "c1": c1_val, "c2": None, "c3": None})
        return flat_list

    def search_relevant_categories(self, query, top_k=50):
        query_parts = set(query.replace(">", " ").split())
        scored_cats = []
        for item in self.flat_categories:
            score = 0
            for q in query_parts:
                if len(q) > 1 and q in item['path']: score += 1
            if score > 0: scored_cats.append((score, item))
        scored_cats.sort(key=lambda x: x[0], reverse=True)
        results = [x[1] for x in scored_cats[:top_k]]
        if len(results) < 5:
             defaults = [x for x in self.flat_categories if "기타" in x['path'] or "전자" in x['path']]
             results.extend(defaults[:10])
        return results

    def find_code_by_exact_path(self, path_str):
        for item in self.flat_categories:
            if item['path'].replace(" ", "") == path_str.replace(" ", ""): return item
        matches = difflib.get_close_matches(path_str, [x['path'] for x in self.flat_categories], n=1, cutoff=0.6)
        if matches:
            for item in self.flat_categories:
                if item['path'] == matches[0]: return item
        return None

    def clean_text_strict(self, text):
        if not text: return ""
        for bad in ["최저가", "로켓", "쿠팡", "배송", "증정", "할인", "특가", "1위"]:
            text = text.replace(bad, "")
        text = self.enforcer_pattern.sub(" ", text)
        return re.sub(r'\s+', ' ', text).strip()

    def extract_model_from_title(self, title):
        """[수정됨] 제목에서 모델명 패턴 정밀 추출"""
        if not title: return "없음"
        
        # 1. 괄호 안 패턴 (예: (15U560)) 우선 확인
        match_paren = re.search(r'\(([A-Za-z0-9-]{4,})\)', title)
        if match_paren:
            candidate = match_paren.group(1)
            # 숫자가 포함되어 있고 한글이 없으면 모델명으로 간주
            if re.search(r'\d', candidate) and not re.search(r'[가-힣]', candidate): 
                return candidate

        # 2. 토큰 단위 탐색 (순방향 탐색)
        # "LG 울트라PC 15U560 ..." -> "15U560"을 찾음
        tokens = title.split()
        for token in tokens:
            # 한글이 포함된 토큰은 스펙일 확률이 높음 (예: "15.6인치", "6세대", "윈도우10") -> 제외
            if re.search(r'[가-힣]', token):
                continue
                
            # 특수문자 제거 (하이픈, 점 제외)
            clean_token = re.sub(r'[^a-zA-Z0-9-]', '', token)
            
            # 조건 1: 길이가 4자 이상일 것 (i5, PC 등 제외)
            if len(clean_token) < 4: continue
            
            # 조건 2: 제외 단어 리스트
            if clean_token.lower() in ['2024', '2025', 'best', 'sale', 'new', 'notebook', 'laptop']: continue
            
            # 조건 3: 영문 + 숫자 혼합 (가장 강력한 모델명 특징) -> 예: 15U560
            if re.search(r'[A-Za-z]', clean_token) and re.search(r'[0-9]', clean_token):
                return clean_token
                
            # 조건 4: 하이픈이 포함된 긴 숫자 코드 -> 예: SIF-1214
            if '-' in clean_token and len(clean_token) > 5:
                return clean_token

        return "없음"

    def parse_kc_codes(self, kc_string):
        result = {"KC_어린이_번호": "", "KC_전기_번호": "", "KC_생활_번호": "", "KC_방송_번호": ""}
        if not kc_string or "상세" in kc_string: return result
        codes = re.split(r'[,/|]', kc_string)
        for code in codes:
            code = code.strip().upper()
            if not code: continue
            if any(x in code for x in ["MSIP", "R-R", "KCC"]): result["KC_방송_번호"] = code
            elif re.match(r'^[A-Z]{2}\d{5}-\d{4,5}[A-Z]?$', code) or "HU" in code or "SU" in code: result["KC_전기_번호"] = code
            elif code.startswith("CB") or code.startswith("B"): result["KC_어린이_번호"] = code
            else:
                if not result["KC_생활_번호"]: result["KC_생활_번호"] = code
        return result

# ======================================================
# [모듈 2] 이미지 프로세서
# ======================================================
class ImageProcessor:
    def __init__(self):
        if not os.path.exists(IMAGE_DIR): os.makedirs(IMAGE_DIR)

    def download_image(self, url):
        if not url or 'http' not in url: return None
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200: return BytesIO(response.content)
        except: pass
        return None

    def process_main_image(self, url, idx):
        img_data = self.download_image(url)
        if not img_data: return ""
        try:
            img = Image.open(img_data).convert("RGB")
            img = img.resize(MAIN_IMG_SIZE, Image.LANCZOS)
            filename = f"main_{int(time.time())}_{idx}.jpg"
            filepath = os.path.join(IMAGE_DIR, filename)
            img.save(filepath, format='JPEG', quality=90)
            return filepath
        except: return ""

    def process_detail_image(self, url_list, idx):
        if not url_list: return ""
        if isinstance(url_list, str): url_list = [url_list]
        images = []
        for url in url_list:
            img_data = self.download_image(url)
            if img_data:
                try:
                    img = Image.open(img_data).convert("RGB")
                    if img.width > DETAIL_IMG_WIDTH:
                        w_percent = (DETAIL_IMG_WIDTH / float(img.width))
                        h_size = int((float(img.height) * float(w_percent)))
                        img = img.resize((DETAIL_IMG_WIDTH, h_size), Image.LANCZOS)
                    images.append(img)
                except: continue
        
        if not images: return ""
        total_height = sum(img.height for img in images)
        if total_height > 20000: total_height = 20000
        merged_img = Image.new('RGB', (DETAIL_IMG_WIDTH, total_height), (255, 255, 255))
        y_offset = 0
        for img in images:
            if y_offset + img.height > total_height: break
            merged_img.paste(img, (0, y_offset))
            y_offset += img.height
        filename = f"detail_{int(time.time())}_{idx}.jpg"
        filepath = os.path.join(IMAGE_DIR, filename)
        merged_img.save(filepath, format='JPEG', quality=80)
        return filepath

# ======================================================
# [모듈 3] 데이터 컨버터 (메인)
# ======================================================
class DataConverter:
    def __init__(self):
        self.utils = DataUtils()
        self.img_processor = ImageProcessor()

    def create_prompt(self, raw_item, candidate_list):
        candidates_text = "\n".join([f"- {c['path']}" for c in candidate_list])
        return f"""
        당신은 S2B 상품 등록 전문가입니다.
        1. [카테고리 후보 리스트] 중 가장 적합한 경로 하나를 선택하세요.
        2. 상품명을 정제하세요.
        3. 모델명을 상품명이나 입력된 정보에서 반드시 추출하세요. (없으면 상품명에서 유추)

        ### [입력 상품]
        - 상품명: {raw_item.get('name')}
        - 입력된 모델명: {raw_item.get('model')}
        - 가격: {raw_item.get('price')}
        - 원본 카테고리: {raw_item.get('category')}

        ### [카테고리 후보 리스트]
        {candidates_text}

        ### [출력 포맷 (JSON Only)]
        {{
            "물품명": "정제된 상품명 (모델명 제외)",
            "규격": "정제된 규격",
            "추출된_모델명": "추출한 모델명",
            "선택한_카테고리_경로": "위 리스트의 경로 복사"
        }}
        """

    def process(self):
        print(f"🚀 [Converter v9.4] 모델명 추출 로직 수정 완료...")
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f: raw_data = json.load(f)
        except:
            print("❌ 원본 데이터가 없습니다."); return

        final_result = []

        for idx, item in enumerate(raw_data):
            print(f"\n🔹 [{idx+1}/{len(raw_data)}] 처리 중: {item.get('name')[:15]}...")
            
            query = f"{item.get('name')} {item.get('category')}"
            candidates = self.utils.search_relevant_categories(query, top_k=50)
            
            try:
                response = client.models.generate_content(
                    model=PRIMARY_MODEL,
                    contents=self.create_prompt(item, candidates),
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                ai_data = json.loads(response.text)
                if isinstance(ai_data, list): ai_data = ai_data[0]
            except:
                ai_data = {"물품명": item.get('name'), "규격": item.get('name'), "추출된_모델명": "없음", "선택한_카테고리_경로": ""}

            selected_path = ai_data.get('선택한_카테고리_경로', '')
            cat_info = self.utils.find_code_by_exact_path(selected_path)
            if not cat_info and candidates: cat_info = candidates[0]
            if not cat_info: cat_info = {"c1": None, "c2": None, "c3": None, "path": "매핑실패"}

            # [모델명 결정 로직 - 우선순위 조정]
            ai_model = ai_data.get('추출된_모델명', '없음')
            manual_model = self.utils.extract_model_from_title(item.get('name'))
            raw_model = item.get('model', '없음')

            final_model = "없음"
            # 1순위: 파이썬 정규식 추출 (가장 정확함)
            if manual_model != "없음": 
                final_model = manual_model
            # 2순위: AI 추출값
            elif ai_model != "없음" and len(ai_model) > 3: 
                final_model = ai_model
            # 3순위: 원본 데이터
            elif raw_model != "없음": 
                final_model = raw_model.replace("상세설명참조", "").strip()
            
            if not final_model or len(final_model) < 2: final_model = "없음"
            
            print(f"    🏷️ 모델명 확정: {final_model}")

            raw_maker = item.get('maker', '')
            final_maker = raw_maker if raw_maker and "상세" not in raw_maker else "협력업체"
            final_origin = item.get('origin', '중국') if item.get('origin') else "중국"

            kc_info = self.utils.parse_kc_codes(item.get('kc', ''))

            clean_name = self.utils.clean_text_strict(ai_data.get('물품명', item.get('name')))
            clean_spec = self.utils.clean_text_strict(ai_data.get('규격', ''))
            if not clean_spec or clean_spec == clean_name: clean_spec = item.get('name')

            main_img = self.img_processor.process_main_image(item.get('image'), idx)
            detail_img = self.img_processor.process_detail_image(item.get('detail_images', [item.get('image')]), idx)

            final_item = {
                "물품명": clean_name,
                "규격": clean_spec,
                "카테고리1": cat_info.get('c1'),
                "카테고리2": cat_info.get('c2'),
                "카테고리3": cat_info.get('c3'),
                "카테고리_전체경로": cat_info.get('path'),
                "제시금액": int(item.get('price', 0)),
                "모델명": final_model, 
                "제조사명": final_maker,
                "원산지": final_origin,
                "기본이미지1": main_img,
                "상세이미지": detail_img,
                "G2B분류번호": "",
                "KC_어린이_번호": kc_info["KC_어린이_번호"],
                "KC_전기_번호": kc_info["KC_전기_번호"],
                "KC_생활_번호": kc_info["KC_생활_번호"],
                "KC_방송_번호": kc_info["KC_방송_번호"]
            }
            final_result.append(final_item)

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=4)
        print(f"\n✅ 전체 완료! '{OUTPUT_FILE}' 확인하세요.")

if __name__ == "__main__":
    converter = DataConverter()
    converter.process()