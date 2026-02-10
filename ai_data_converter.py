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
FALLBACK_MODEL = "gemini-1.5-flash"

# ======================================================
# [모듈 1] 데이터 유틸리티 (RAG 검색 엔진 탑재)
# ======================================================
class DataUtils:
    def __init__(self):
        self.raw_categories = self._load_json(CATEGORY_FILE)
        self.enforcer_pattern = re.compile(r"[^가-힣a-zA-Z0-9\s\.\,\-\_\/\(\)\[\]]")
        # [핵심] 전체 카테고리 경로를 검색 가능한 형태로 평탄화(Flatten)
        self.flat_categories = self._flatten_categories()
        
    def _load_json(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _flatten_categories(self):
        """모든 카테고리 경로를 '텍스트'와 '코드' 매핑으로 변환"""
        flat_list = []
        cats = self.raw_categories
        
        if 'category1' in cats:
            for c1 in cats['category1']:
                c1_txt = c1['text']
                c1_val = c1['value']
                
                # 2차
                if 'category2' in cats and c1_val in cats['category2']:
                    for c2 in cats['category2'][c1_val]:
                        c2_txt = c2['text']
                        c2_val = c2['value']
                        
                        # 3차
                        key = f"{c1_val}_{c2_val}"
                        if 'category3' in cats and key in cats['category3']:
                            for c3 in cats['category3'][key]:
                                full_path = f"{c1_txt} > {c2_txt} > {c3['text']}"
                                flat_list.append({
                                    "path": full_path,
                                    "c1": c1_val, "c1_name": c1_txt,
                                    "c2": c2_val, "c2_name": c2_txt,
                                    "c3": c3['value'], "c3_name": c3['text']
                                })
                        else:
                            # 3차가 없는 경우 (2차까지만 존재)
                            full_path = f"{c1_txt} > {c2_txt}"
                            flat_list.append({
                                "path": full_path,
                                "c1": c1_val, "c1_name": c1_txt,
                                "c2": c2_val, "c2_name": c2_txt,
                                "c3": None, "c3_name": None
                            })
                else:
                    # 1차만 있는 경우
                    flat_list.append({
                        "path": c1_txt,
                        "c1": c1_val, "c1_name": c1_txt,
                        "c2": None, "c2_name": None,
                        "c3": None, "c3_name": None
                    })
        print(f"📂 [System] 전체 카테고리 경로 {len(flat_list)}개 인덱싱 완료.")
        return flat_list

    def search_relevant_categories(self, query, top_k=50):
        """
        [검색 엔진] 상품명+카테고리명(query)과 연관된 카테고리 Top-K 추출
        단순 텍스트 매칭 점수 기반
        """
        query_parts = set(query.replace(">", " ").split())
        scored_cats = []
        
        for item in self.flat_categories:
            score = 0
            path_str = item['path']
            
            # 검색어가 경로에 포함되면 점수 부여
            for q in query_parts:
                if len(q) > 1 and q in path_str: # 1글자 제외
                    score += 1
            
            # 정확도를 위해 2차, 3차 카테고리명 자체에 가중치
            if score > 0:
                scored_cats.append((score, item))
        
        # 점수 내림차순 정렬
        scored_cats.sort(key=lambda x: x[0], reverse=True)
        
        # 결과 반환 (없으면 상위 무작위 반환 방지를 위해 빈 리스트 또는 기본값 고려)
        results = [x[1] for x in scored_cats[:top_k]]
        
        # 만약 검색 결과가 너무 적으면, '기타'나 '전자제품' 등 기본 카테고리 일부 추가
        if len(results) < 5:
             defaults = [x for x in self.flat_categories if "기타" in x['path'] or "전자" in x['path']]
             results.extend(defaults[:10])
             
        return results

    def find_code_by_exact_path(self, path_str):
        """AI가 선택한 경로 텍스트로 코드를 찾음"""
        for item in self.flat_categories:
            # 공백/특수문자 무시하고 비교
            if item['path'].replace(" ", "") == path_str.replace(" ", ""):
                return item
        # 못 찾으면 유사도 검색
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

    def clean_model_name(self, text):
        if not text or text == "없음": return "없음"
        if "/" in text:
            parts = text.split("/")
            for part in reversed(parts):
                clean_part = part.strip()
                if re.search(r'[A-Z]', clean_part) and re.search(r'[0-9]', clean_part):
                    return clean_part
        match = re.search(r'[A-Za-z0-9-]{5,}', text)
        if match: return match.group(0)
        return text

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
# [모듈 3] 데이터 컨버터 (Dynamic RAG)
# ======================================================
class DataConverter:
    def __init__(self):
        self.utils = DataUtils()
        self.img_processor = ImageProcessor()

    def create_prompt(self, raw_item, candidate_list):
        # 검색된 후보 리스트를 텍스트로 변환
        candidates_text = "\n".join([f"- {c['path']}" for c in candidate_list])
        
        return f"""
        당신은 S2B 상품 등록 전문가입니다.
        입력 상품에 가장 적합한 카테고리 경로를 [후보 리스트] 중에서 단 하나만 선택하세요.

        ### [입력 상품]
        - 상품명: {raw_item.get('name')}
        - 가격: {raw_item.get('price')}
        - 원본 카테고리: {raw_item.get('category')}

        ### [카테고리 후보 리스트 (이 중에서 선택 필독)]
        {candidates_text}

        ### [지시사항]
        1. 위 후보 리스트 중 상품과 가장 일치하는 **전체 경로(텍스트)**를 그대로 출력하세요.
        2. 물품명과 규격도 정제하세요.

        ### [출력 포맷 (JSON Only)]
        {{
            "물품명": "정제된 상품명",
            "규격": "정제된 규격",
            "선택한_카테고리_경로": "위 리스트에 있는 경로 텍스트 그대로 복사"
        }}
        """

    def process(self):
        print(f"🚀 [Converter v9.0] 전체 카테고리 검색(RAG) 모드 시작...")
        
        try:
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except:
            print("❌ 원본 데이터가 없습니다.")
            return

        final_result = []

        for idx, item in enumerate(raw_data):
            print(f"\n🔹 [{idx+1}/{len(raw_data)}] 처리 중: {item.get('name')[:15]}...")
            
            # 1. [검색] 관련 카테고리 후보 추출 (상품명 + 원본카테고리 활용)
            query = f"{item.get('name')} {item.get('category')}"
            candidates = self.utils.search_relevant_categories(query, top_k=50)
            
            # 2. [AI] 후보 중 최적 선택
            try:
                response = client.models.generate_content(
                    model=PRIMARY_MODEL,
                    contents=self.create_prompt(item, candidates),
                    config=types.GenerateContentConfig(response_mime_type="application/json")
                )
                ai_data = json.loads(response.text)
                if isinstance(ai_data, list): ai_data = ai_data[0]
            except Exception as e:
                print(f"    ⚠️ AI 변환 오류: {e}")
                ai_data = {"물품명": item.get('name'), "규격": item.get('name'), "선택한_카테고리_경로": ""}

            # 3. [매핑] 선택된 경로 -> 코드 변환
            selected_path = ai_data.get('선택한_카테고리_경로', '')
            cat_info = self.utils.find_code_by_exact_path(selected_path)
            
            # 매핑 실패 시 후보 1순위 사용 (안전장치)
            if not cat_info and candidates:
                cat_info = candidates[0]
                print(f"    ⚠️ AI 선택 경로 매핑 실패. 검색 1순위로 대체: {cat_info['path']}")

            if not cat_info: # 진짜 아무것도 못 찾았을 때
                cat_info = {"c1": None, "c2": None, "c3": None, "path": "매핑실패"}

            # 데이터 정제
            raw_model = item.get('model', '없음')
            final_model = self.utils.clean_model_name(raw_model)
            
            raw_maker = item.get('maker', '')
            final_maker = raw_maker if raw_maker and "상세" not in raw_maker and "협력" not in raw_maker else "협력업체"

            raw_origin = item.get('origin', '')
            final_origin = raw_origin if raw_origin and "상세" not in raw_origin else "중국"

            raw_kc = item.get('kc', '')
            kc_info = self.utils.parse_kc_codes(raw_kc)

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
                "카테고리_전체경로": cat_info.get('path'), # 검증용
                
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
            print(f"    ✅ 매핑결과: {cat_info.get('path')}")

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, ensure_ascii=False, indent=4)
        print(f"\n✅ 전체 완료! '{OUTPUT_FILE}' 확인하세요.")

if __name__ == "__main__":
    converter = DataConverter()
    converter.process()