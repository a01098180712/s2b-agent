import json
import os
import re
import asyncio
from playwright.async_api import async_playwright

async def fetch_product_data(url):
    # Connect to already running Chrome instance
    async with async_playwright() as p:
        print("Connecting to the running Chrome instance...")
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]  # Use existing context
        page = context.pages[0] if context.pages else await context.new_page()  # Use the current page or open new if needed

        # Attempt to navigate to the URL with retry on timeout
        print(f"Navigating to {url}...")
        retries = 3
        for attempt in range(retries):
            try:
                await page.goto(url, timeout=10000)
                print("Page loaded successfully.")
                break
            except Exception as e:
                print(f"Retry due to timeout (attempt {attempt + 1}): {e}")
        else:
            print("Failed to load the page after retries.")
            return None

        # Collect data from the page
        try:
            print("Collecting product data...")

            product_name_element = await page.query_selector('h2.product-title')
            if product_name_element:
                product_name = await product_name_element.inner_text()
                product_name = re.sub(r'[^\w\s]', '', product_name)  # Remove special characters
                print(f"Product Name: {product_name}")  # v4.3 Fix: Improved logging
            else:
                print("Product name element not found.")
                product_name = "N/A"

            price_element = await page.query_selector('.price .amount')
            if price_element:
                price_text = await price_element.inner_text()
                price = re.sub(r'[^\d]', '', price_text)  # Extract only numbers
                if not price:
                    print("Price not found in text, setting to '0'.")
                    price = "0"
                print(f"Price: {price}")  # v4.3 Fix: Improved logging
            else:
                print("Price element not found.")
                price = "0"

            origin_element = await page.query_selector('.origin-info')
            if origin_element:
                origin_or_manufacturer = await origin_element.inner_text()
                print(f"Origin/Manufacturer: {origin_or_manufacturer}")  # v4.3 Fix: Improved logging
            else:
                print("Origin/manufacturer element not found.")
                origin_or_manufacturer = "N/A"

            kc_cert_element = await page.query_selector('.kc-certification')
            if kc_cert_element:
                kc_certification_info = await kc_cert_element.inner_text()
                print(f"KC Certification Info: {kc_certification_info}")  # v4.3 Fix: Improved logging
            else:
                print("KC certification element not found.")
                kc_certification_info = "N/A"

            # Image download setup
            images_dir = "C:\\S2B_Agent\\images"
            os.makedirs(images_dir, exist_ok=True)

            main_image_element = await page.query_selector('.main-image img')
            if main_image_element:
                main_image_url = await main_image_element.get_attribute('src')
                print(f"Main Image URL: {main_image_url}")  # v4.3 Fix: Improved logging
            else:
                print("Main image element not found.")
                main_image_url = None

            detailed_image_elements = await page.query_selector_all('.detailed-images img')
            detailed_image_urls = []
            if detailed_image_elements:
                detailed_image_urls = [await img.get_attribute('src') for img in detailed_image_elements]
                print(f"Detailed Image URLs: {detailed_image_urls}")  # v4.3 Fix: Improved logging

            # Ensure valid image URLs
            image_urls = [main_image_url] if main_image_url else []
            image_urls.extend(detailed_image_urls)

            if not image_urls:
                print("No images found.")
            else:
                print(f"Downloading {len(image_urls)} images...")
                for idx, img_url in enumerate(image_urls):
                    if img_url:
                        image_path = os.path.join(images_dir, f'image_{idx}.jpg')
                        # Use a new page for each image download to ensure separate download context
                        async with context.new_page() as new_page:
                            async with new_page.expect_download() as download_info:
                                await new_page.goto(img_url)
                            download = await download_info.value
                            await download.save_as(image_path)
                print("Images downloaded.")

            product_data = {
                "product_name": product_name,
                "price": price,
                "origin_or_manufacturer": origin_or_manufacturer,
                "kc_certification_info": kc_certification_info,
                "images": image_urls
            }

            # Display and save
            print("Product Data Collected:")
            print(json.dumps(product_data, indent=4))
            with open('s2b_complete_data.json', 'w') as json_file:
                json.dump(product_data, json_file, indent=4)
            print("Product data saved to s2b_complete_data.json")

        except Exception as e:
            print(f"Error during data collection: {e}")

if __name__ == "__main__":
    url = input("Enter the product URL: ")
    asyncio.run(fetch_product_data(url))