"""Capture full-page screenshots of every Streamlit dashboard page (fixed login)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

OUT = Path(r"c:\Users\mohamad\OneDrive\Desktop\AI_NDR_Page_Guide_Screenshots")
BASE = "http://127.0.0.1:8501"

PAGES = [
    ("02_live_monitoring", "/Live_Monitoring"),
    ("03_ai_detection", "/AI_Detection"),
    ("04_threat_simulation", "/Threat_Simulation"),
    ("05_threat_intelligence", "/Threat_Intelligence"),
    ("06_alerts", "/Alerts"),
    ("07_blocked_ips", "/Blocked_IPs"),
    ("08_ai_models", "/AI_Models"),
    ("09_reports", "/Reports"),
    ("10_settings", "/Settings"),
    ("11_soc_ops", "/SOC_Ops"),
    ("12_incidents", "/Incidents"),
    ("13_assets", "/Assets"),
    ("14_hunting", "/Hunting"),
    ("15_response", "/Response"),
    ("16_copilot", "/Copilot"),
]

TABS = [
    ("/Reports", "Detection Report", "09b_reports_detection"),
    ("/Reports", "Incident Reports", "09c_reports_incidents"),
    ("/Reports", "Export", "09d_reports_export"),
    ("/Reports", "Compliance", "09e_reports_compliance"),
    ("/Reports", "Live Evidence", "09f_reports_live_evidence"),
    ("/Settings", "General", "10b_settings_general"),
    ("/Settings", "Telegram", "10c_settings_telegram"),
    ("/Settings", "AI Config", "10d_settings_ai"),
    ("/Settings", "NDR / Response", "10e_settings_ndr"),
    ("/Settings", "Clear Data", "10f_settings_clear"),
    ("/Settings", "Company", "10g_settings_company"),
    ("/SOC_Ops", "MITRE ATT&CK", "11b_soc_mitre"),
    ("/SOC_Ops", "SOAR Playbooks", "11c_soc_soar"),
    ("/SOC_Ops", "Online Learning", "11d_soc_online"),
    ("/SOC_Ops", "Server Health", "11e_soc_health"),
    ("/SOC_Ops", "ML Registry", "11f_soc_ml"),
    ("/Assets", "Inventory", "13b_assets_inventory"),
    ("/Assets", "Topology", "13c_assets_topology"),
    ("/Assets", "Host profile", "13d_assets_host"),
    ("/Assets", "Identity / UEBA", "13e_assets_ueba"),
    ("/Hunting", "Hunt", "14b_hunting_hunt"),
    ("/Hunting", "Forensics PCAP", "14c_hunting_pcap"),
    ("/Hunting", "Protocol / DNS / TLS", "14d_hunting_protocol"),
    ("/Response", "IOC", "15b_response_ioc"),
    ("/Response", "Allow / Block", "15c_response_allow"),
    ("/Response", "Approvals", "15d_response_approvals"),
    ("/Response", "Webhooks", "15e_response_webhooks"),
    ("/Response", "Sensors", "15f_response_sensors"),
]


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,1200")
    opts.add_argument("--force-device-scale-factor=1")
    opts.add_argument("--hide-scrollbars")
    opts.add_argument("--disable-gpu")
    return webdriver.Chrome(options=opts)


def wait_app(driver, timeout=60):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script(
            "return !!document.querySelector('[data-testid=\"stApp\"]')"
        )
    )
    time.sleep(1.2)


def wait_not_login(driver, timeout=40):
    WebDriverWait(driver, timeout).until(
        lambda d: "Sign In" not in d.page_source or "Total Flows" in d.page_source
        or "Logout" in d.page_source
        or "ONLINE" in d.page_source
    )


def full_screenshot(driver, path: Path) -> None:
    total_h = driver.execute_script(
        """
        const app = document.querySelector('[data-testid="stAppViewContainer"]')
          || document.querySelector('[data-testid="stApp"]')
          || document.body;
        return Math.max(
          app.scrollHeight || 0,
          document.body.scrollHeight || 0,
          document.documentElement.scrollHeight || 0,
          1200
        );
        """
    )
    driver.set_window_size(1600, min(int(total_h) + 100, 14000))
    time.sleep(0.8)
    driver.save_screenshot(str(path))
    print(f"  saved {path.name} ({path.stat().st_size // 1024} KB) login?={'Sign In' in driver.page_source and 'Logout' not in driver.page_source}")


def login(driver) -> None:
    driver.get(BASE + "/")
    wait_app(driver)
    time.sleep(2)
    if "Logout" in driver.page_source or "Total Flows" in driver.page_source:
        print("Already authenticated.")
        return
    inputs = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='stTextInput'] input")
    if len(inputs) < 2:
        raise RuntimeError("Login inputs not found")
    inputs[0].click()
    inputs[0].send_keys(Keys.CONTROL, "a")
    inputs[0].send_keys("admin")
    inputs[1].click()
    inputs[1].send_keys(Keys.CONTROL, "a")
    inputs[1].send_keys("admin123")
    time.sleep(0.4)
    submit = driver.find_elements(By.CSS_SELECTOR, "button[data-testid='baseButton-primaryFormSubmit']")
    if not submit:
        submit = [b for b in driver.find_elements(By.CSS_SELECTOR, "button") if "Sign In" in (b.text or "")]
    submit[0].click()
    wait_not_login(driver)
    time.sleep(2)
    print("Login OK. Total Flows?", "Total Flows" in driver.page_source)


def open_page(driver, route: str) -> None:
    driver.get(BASE + route)
    wait_app(driver)
    # Streamlit multipage may re-show login if session lost
    if "Sign In" in driver.page_source and "Logout" not in driver.page_source:
        print("  session lost — re-login")
        login(driver)
        driver.get(BASE + route)
        wait_app(driver)
    time.sleep(1.5)


def click_tab(driver, tab_text: str) -> bool:
    # Prefer role=tab
    for sel in [
        "button[role='tab']",
        "button[data-baseweb='tab']",
        "[data-testid='stTabs'] button",
    ]:
        for t in driver.find_elements(By.CSS_SELECTOR, sel):
            label = (t.text or "").strip().replace("\n", " ")
            if label == tab_text or tab_text.lower() in label.lower():
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", t)
                time.sleep(0.2)
                driver.execute_script("arguments[0].click();", t)
                time.sleep(1.5)
                return True
    # XPath contains
    xpath = f"//button[contains(., '{tab_text}')]"
    els = driver.find_elements(By.XPATH, xpath)
    for el in els:
        try:
            driver.execute_script("arguments[0].click();", el)
            time.sleep(1.5)
            return True
        except Exception:
            continue
    return False


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    driver = make_driver()
    try:
        print("Login page…")
        driver.get(BASE + "/")
        wait_app(driver)
        time.sleep(1)
        full_screenshot(driver, OUT / "00_login.png")

        login(driver)

        print("Home…")
        open_page(driver, "/")
        full_screenshot(driver, OUT / "01_home.png")

        for name, route in PAGES:
            print(f"{name}…")
            open_page(driver, route)
            full_screenshot(driver, OUT / f"{name}.png")

        for route, tab, fname in TABS:
            print(f"{fname} ({tab})…")
            open_page(driver, route)
            ok = click_tab(driver, tab)
            if not ok:
                print(f"  WARN tab missing: {tab}")
            full_screenshot(driver, OUT / f"{fname}.png")

        print("DONE", len(list(OUT.glob('*.png'))), "pngs")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
