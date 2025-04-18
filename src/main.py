# === Standard Library Imports ===
import os
import re
import math
import json
import html
import asyncio
import httpx
from selectolax.parser import HTMLParser
from models import ProductData, Part, Assets

BASE_URL = "https://www.baldor.com"
MAX_product_codes = 15
MAX_PAGE_SIZE = 50

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


def fetch_categories_list(client):
    params = {
        "include": "results",
        "include": "filters",
        "include": "category",
        "language": "en-US",
        "pageSize": "10",
        "category": "199"
    }
    response = client.get(f'{BASE_URL}/api/products', headers=HEADERS, params=params)
    response.raise_for_status()
    return response.json()


def extract_category_data(category_list):
    items = category_list.get("category", {}).get("children", [])
    return {
        category["id"]: category["count"]
        for category in items if category.get("count", 0) > 0
    }


def paginate_item_listing(client, category_id, total_count, product_codes):
    total_pages = math.ceil(total_count / MAX_PAGE_SIZE)

    for page_index in range(1, total_pages + 1):
        if len(product_codes) >= MAX_product_codes:
            break

        page_size = min(MAX_PAGE_SIZE, MAX_product_codes - len(product_codes))
        params = {
            "include": "category",
            "include": "results",
            "language": "en-US",
            "pageSize": str(page_size),
            "pageIndex": str(page_index),
            "category": str(category_id)
        }

        response = client.get(f'{BASE_URL}/api/products', headers=HEADERS, params=params)
        response.raise_for_status()
        fetch_item_codes(response.json(), product_codes)


def fetch_item_codes(json_response, product_codes):
    product_list = json_response.get("results", {}).get("matches", [])

    for product in product_list:
        product_id = product.get("code")
        product_categories = product.get("categories", [])
        product_name = " / ".join(cat.get("text", "") for cat in product_categories)

        product_codes.append({
            "product_id": product_id,
            "name": product_name
        })

        if len(product_codes) >= MAX_product_codes:
            break


async def fetch_product_page(client, product, retries=3):
    code = product["product_id"]
    product_name = product["name"]
    url = f'{BASE_URL}/catalog/{code}'

    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            return {
                "html": response.text,
                "product_id": code,
                "name": product_name
            }
        except Exception as e:
            print(f"Attempt {attempt} failed for {code}: {e}")
            if attempt < retries:
                print("Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                print(f"Failed after {retries} attempts for {code}")
                return None


async def get_product_codes_html(product_codes):
    async with httpx.AsyncClient() as client:
        tasks = [fetch_product_page(client, product) for product in product_codes]
        return await asyncio.gather(*tasks)


def extract_specs(html):
    tree = HTMLParser(html)
    specs_div = tree.css_first('div[data-tab="specs"]')
    specs = {}

    if specs_div:
        labels = specs_div.css('span.label')
        values = specs_div.css('span.value')
        for label, value in zip(labels, values):
            specs[label.text(strip=True)] = value.text(strip=True)

    return specs


def extract_parts(html):
    tree = HTMLParser(html)
    parts = []
    parts_div = tree.css_first('div[data-tab="parts"]')
    if not parts_div:
        return parts

    rows = parts_div.css('table.data-table tbody tr')
    for row in rows:
        cells = row.css('td')
        if len(cells) >= 3:
            parts.append({
                "part_number": cells[0].text(strip=True),
                "description": cells[1].text(strip=True),
                "quantity": cells[2].text(strip=True)
            })
    return parts


def extract_dwg_file_data(html_text):
    unescaped = html.unescape(html_text)
    name_match = re.search(r'"value"\s*:\s*"([^"]+\.DWG)"', unescaped, re.IGNORECASE)
    url_match = re.search(r'"url"\s*:\s*"([^"]+\.DWG)"', unescaped, re.IGNORECASE)

    if name_match and url_match:
        return {
            "name": name_match.group(1),
            "url": url_match.group(1)
        }
    return None


def create_directory(product_id):
    dir_path = os.path.join(f'./output/assets/{product_id}')
    os.makedirs(dir_path, exist_ok=True)


async def async_download_with_retries(client, url, file_path, params=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            response = await client.get(url, headers=HEADERS, params=params, timeout=30)
            if response.status_code == 404:
                return None
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path

        except httpx.HTTPStatusError as e:
            print(f"HTTP error ({e.response.status_code}) on attempt {attempt} for {url}")
            if e.response.status_code == 404:
                return None
        except Exception as e:
            print(f"Attempt {attempt} failed for {url}: {e}")
        
        if attempt < retries:
            print("Retrying in 5 seconds...")
            await asyncio.sleep(5)
    return None


async def download_image(html, product_id, client):
    tree = HTMLParser(html)
    img_tag = tree.css_first("img.product-image")

    if not img_tag or not img_tag.attributes.get("data-src"):
        return None

    image_uri = img_tag.attributes["data-src"]
    url = f"{BASE_URL}{image_uri}"
    file_path = f"./output/assets/{product_id}/{product_id}.jpg"
    return await async_download_with_retries(client, url, file_path)


async def download_manual(product_id, client):
    url = f"{BASE_URL}/api/products/{product_id}/infopacket"
    file_path = f"./output/assets/{product_id}/{product_id}.pdf"
    return await async_download_with_retries(client, url, file_path)


async def download_cad_file(dwg_file, product_id, client):
    url = f"{BASE_URL}/api/products/download/"
    params = {
        "value": dwg_file['name'],
        "url": dwg_file['url']
    }
    file_path = f"./output/assets/{product_id}/{product_id}.dwg"
    return await async_download_with_retries(client, url, file_path, params=params)


async def get_assets(html, product_id, client):
    create_directory(product_id)
    img_path = await download_image(html, product_id, client)
    manual_path = await download_manual(product_id, client)
    dwg_data = extract_dwg_file_data(html)
    cad_path = await download_cad_file(dwg_data, product_id, client) if dwg_data else None

    return {
        "manual": manual_path,
        "cad": cad_path,
        "image": img_path
    }


async def parse_product_page(product_info, client):
    html = product_info["html"]
    product_id = product_info["product_id"]
    product_name = product_info["name"]
    specs = extract_specs(html)
    parts = extract_parts(html)
    assets = await get_assets(html, product_id, client)

    tree = HTMLParser(html)
    description_node = tree.css_first("div.product-description")
    product_description = description_node.text(strip=True) if description_node else None

    return ProductData(
        product_id=product_id,
        name=product_name,
        description=product_description,
        specs=specs,
        bom=[Part(**part) for part in parts],
        assets=Assets(**assets)
    )


def save_product_to_file(product_obj, output_dir="./output"):
    product_id = product_obj.product_id
    product_dict = product_obj.model_dump()

    with open(f'{output_dir}/{product_id}.json', "w", encoding="utf-8") as f:
        json.dump(product_dict, f, ensure_ascii=False, indent=2)


def main():
    product_codes = []

    with httpx.Client() as client:
        category_list = fetch_categories_list(client)
        category_data = extract_category_data(category_list)

        for category_id, category_item_count in reversed(list(category_data.items())):
            print(f"Fetching codes for category ID {category_id} with {category_item_count} items...")
            paginate_item_listing(client, category_id, category_item_count, product_codes)
            if len(product_codes) >= MAX_product_codes:
                break

    print(f"\nCollected {len(product_codes)} product codes. Starting async scraping...\n")

    html_pages = asyncio.run(get_product_codes_html(product_codes))

    async def process_all_products():
        async with httpx.AsyncClient() as client:
            tasks = [
                parse_product_page(product_info, client)
                for product_info in html_pages if product_info
            ]
            return await asyncio.gather(*tasks)

    products = asyncio.run(process_all_products())

    for product in products:
        if product:
            save_product_to_file(product)

    total_results = sum(category_data.values())
    print(f'Scraped {len(products)} products out of {total_results} results ({(len(products)/total_results)*100:.2f}%).')

if __name__ == "__main__":
    main()
