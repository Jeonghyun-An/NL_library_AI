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

TOTAL_PAGES   = 15567
START_PAGE    = 1     # 중단됐을 때 여기서 재시작
PAGE_SIZE     = 100   # 30 → 100으로 늘려 페이지 수 1/3로 단축 (사이트 미지원 시 30으로 복원)
MAX_RETRIES   = 3
MAX_EMPTY_STREAK = 5
SAVE_INTERVAL = 50
SAVE_PATH     = "nl_cnts_result.csv"

base_url = driver.current_url.split("#")[0]

# 이어받기: 기존 저장 파일이 있으면 로드
try:
    existing = pd.read_csv(SAVE_PATH, encoding="utf-8-sig")
    results = existing.to_dict("records")
    print(f"기존 결과 로드: {len(results)}개")
except FileNotFoundError:
    results = []

def make_page_url(url, page_num):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["pageNum"] = [str(page_num)]
    params["pageSize"] = [str(PAGE_SIZE)]
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

for page_num in range(START_PAGE, TOTAL_PAGES + 1):
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
        df_tmp.to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")
        print(f"  [중간 저장] {len(df_tmp)}개  (다음 재시작: START_PAGE={page_num + 1})")


df = pd.DataFrame(results)
df = df.drop_duplicates(subset=["CNTS_ID"])

df.to_csv(SAVE_PATH, index=False, encoding="utf-8-sig")

print(f"\n저장 완료: {SAVE_PATH}")
print(f"총 개수: {len(df)}")
