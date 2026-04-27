import re
import time
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

options = Options()
options.debugger_address = "127.0.0.1:9222"

driver = webdriver.Chrome(options=options)

results = []

TOTAL_PAGES = 15567
MAX_RETRIES = 3       # 페이지당 재시도 횟수
MAX_EMPTY_STREAK = 5  # 연속 빈 페이지 N회면 종료
SAVE_INTERVAL = 50    # N페이지마다 중간 저장

base_url = driver.current_url.split("#")[0]

def make_page_url(url, page_num):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["pageNum"] = [str(page_num)]
    new_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=new_query))

def fetch_imgs(page_num):
    """페이지 로드 후 CNTS 이미지 반환. 실패 시 MAX_RETRIES 재시도."""
    url = make_page_url(base_url, page_num)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            driver.get(url)
            WebDriverWait(driver, 12).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='CNTS-']"))
            )
            imgs = driver.find_elements(By.CSS_SELECTOR, "img[src*='CNTS-']")
            if imgs:
                return imgs
        except:
            pass
        print(f"  [재시도 {attempt}/{MAX_RETRIES}]")
        time.sleep(2)
    return []

empty_streak = 0

for page_num in range(1, TOTAL_PAGES + 1):
    print(f"\n[PAGE] {page_num}/{TOTAL_PAGES}  (누적: {len(results)}개)")

    imgs = fetch_imgs(page_num)

    if not imgs:
        empty_streak += 1
        print(f"  빈 페이지 (연속 {empty_streak}/{MAX_EMPTY_STREAK})")
        if empty_streak >= MAX_EMPTY_STREAK:
            print("연속 빈 페이지 한도 초과 → 종료")
            break
        continue

    empty_streak = 0

    for img in imgs:
        try:
            src = img.get_attribute("src") or ""
            m = re.search(r'CNTS-\d+', src)
            if not m:
                continue
            cnts_id = m.group(0)

            try:
                li = img.find_element(By.XPATH, "./ancestor::li[1]")
                title = li.find_element(By.TAG_NAME, "a").text.strip()
                try:
                    info = li.find_element(By.CSS_SELECTOR, ".info").text
                    author = info.split("/")[0].strip()
                except:
                    author = ""
            except:
                title = ""
                author = ""

            results.append({"CNTS_ID": cnts_id, "TITLE": title, "AUTHOR": author})

        except Exception as e:
            print(f"  에러: {e}")

    if page_num % SAVE_INTERVAL == 0:
        df_tmp = pd.DataFrame(results).drop_duplicates(subset=["CNTS_ID"])
        df_tmp.to_csv("nl_cnts_result.csv", index=False, encoding="utf-8-sig")
        print(f"  [중간 저장] {len(df_tmp)}개")


df = pd.DataFrame(results)
df = df.drop_duplicates(subset=["CNTS_ID"])

save_path = "nl_cnts_result.csv"
df.to_csv(save_path, index=False, encoding="utf-8-sig")

print(f"\n저장 완료: {save_path}")
print(f"총 개수: {len(df)}")
