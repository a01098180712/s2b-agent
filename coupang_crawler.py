import asyncio
import json
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
import os
import re
from urllib.parse import urlparse

# 로깅 설정
logging.basicConfig(level=logging.INFO)

# 데이터 저장 경로 설정
DATA_FILE = 's2b_complete_data.json'

# 금지어 목록 설정
FORBIDDEN_WORDS = ['빠른', '친환경', '사은품증정', '최저가', '국내산', '최고급', '시리즈']

# 금지어를 제거하는 함수
def clean_text(text):
    for word in FORBIDDEN_WORDS:
        text = re.sub(word, '', text)
    return text

# URL에서 파일명을 추출하는 유틸리티 함수
def extract_filename_from_url(url):
    return os.path.basename(urlparse(url).path)

# JSON 파일에 저장되는 데이터를 중복 없이 추가
def save_data_to_json(data, filename=DATA_FILE):
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump([], f)

    with open(filename, 'r+', encoding='utf-8') as f:
        existing_data = json.load(f)
        updated_data = [*existing_data, *[d for d in data if d not in existing_data]]
        f.seek(0)
        json.dump(updated_data, f, ensure_ascii=False, indent=2)

# 쿠팡 정보를 크롤링하는 함수
async def scrape_coupang(url):
    async with async_playwright() as p:
        # Playwright 브라우저 실행 설정
        browser = await p.chromium.launch(args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--no-sandbox"
        ], headless=False)
        
        # 브라우저 컨텍스트 생성
        context = await browser.new_context(
            java_script_enabled=True,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        )
        
        # 초기 스크립트 추가를 통한 봇 탐지 회피
        await context.add_init_script('''Object.defineProperty(navigator, 'webdriver', {get: () => undefined})''')
        
        page = await context.new_page()
        for attempt in range(3):
            try:
                # 페이지 로드
                logging.info(f"Attempting to scrape {url}... Attempt {attempt + 1}")
                await page.goto(url, timeout=30000)
                
                # 선택자 대기
                await page.wait_for_selector('div.product-title', state='attached', timeout=10000)
                
                # 웹 페이지로부터 데이터 추출
                title = await page.text_content('h1.product-title')
                title_cleaned = clean_text(title)
                logging.info(f"Scraped title: {title_cleaned}")
                
                # 크롤링한 데이터를 변수에 저장 (예시)
                product_data = [{'title': title_cleaned}]
                
                # 중복 없이 JSON 저장
                save_data_to_json(product_data)
                break
            except PlaywrightTimeoutError:
                logging.warning(f"Timeout error on attempt {attempt + 1}")
            except Exception as e:
                logging.error(f"Error on attempt {attempt + 1}: {str(e)}")
        else:
            logging.error(f"Failed to scrape {url} after 3 attempts.")
        
        await browser.close()

async def main():
    while True:
        url = input("Enter the Coupang product URL (or 'exit' to quit): ")
        if url.lower() == 'exit':
            break
        if urlparse(url).scheme in ["http", "https"]:
            await scrape_coupang(url)
        else:
            logging.error("Invalid URL. Please enter a valid Coupang product URL.")

# 비동기 함수 실행
if __name__ == "__main__":
    asyncio.run(main())