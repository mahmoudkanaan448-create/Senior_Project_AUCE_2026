"""Debug Streamlit login."""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--window-size=1400,1000")
d = webdriver.Chrome(options=opts)
d.get("http://127.0.0.1:8501/")
time.sleep(5)
print("TITLE:", d.title)
print("URL:", d.current_url)
for i, el in enumerate(d.find_elements(By.CSS_SELECTOR, "input")):
    print(i, el.get_attribute("type"), el.get_attribute("aria-label"), el.is_displayed())
for i, b in enumerate(d.find_elements(By.CSS_SELECTOR, "button")):
    print("BTN", i, repr(b.text), b.get_attribute("data-testid"))
inputs = d.find_elements(By.CSS_SELECTOR, "div[data-testid='stTextInput'] input")
print("stTextInput count", len(inputs))
if len(inputs) >= 2:
    inputs[0].click()
    inputs[0].send_keys(Keys.CONTROL, "a")
    inputs[0].send_keys("admin")
    inputs[1].click()
    inputs[1].send_keys(Keys.CONTROL, "a")
    inputs[1].send_keys("admin123")
    time.sleep(0.5)
    submits = d.find_elements(
        By.CSS_SELECTOR,
        "button[data-testid='baseButton-primaryFormSubmit'], button[kind='primaryFormSubmit']",
    )
    print("submits", len(submits))
    if submits:
        submits[0].click()
    else:
        for b in d.find_elements(By.CSS_SELECTOR, "button"):
            if "Sign" in (b.text or ""):
                b.click()
                break
    time.sleep(6)
    print("AFTER URL", d.current_url)
    print("Sign In still?", "Sign In" in d.page_source)
    print("Total Flows?", "Total Flows" in d.page_source)
    print("Home header?", "SOC Dashboard" in d.page_source or "Overview" in d.page_source)
    d.save_screenshot(r"c:\Users\mohamad\OneDrive\Desktop\AI_NDR_Page_Guide_Screenshots\_login_test.png")
d.quit()
print("done")
