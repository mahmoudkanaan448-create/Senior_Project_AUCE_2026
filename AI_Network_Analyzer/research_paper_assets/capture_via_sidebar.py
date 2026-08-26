"""Capture pages by clicking sidebar links inside one Streamlit session."""
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

NAV = [
    ("01_home", "Home"),
    ("02_live_monitoring", "Live Monitoring"),
    ("03_ai_detection", "AI Detection"),
    ("04_threat_simulation", "Threat Simulation"),
    ("05_threat_intelligence", "Threat Intelligence"),
    ("06_alerts", "Alerts"),
    ("07_blocked_ips", "Blocked IPs"),
    ("08_ai_models", "AI Models"),
    ("09_reports", "Reports"),
    ("10_settings", "Settings"),
    ("11_soc_ops", "SOC Ops"),
    ("12_incidents", "Incidents"),
    ("13_assets", "Assets"),
    ("14_hunting", "Hunting"),
    ("15_response", "Response"),
    ("16_copilot", "Copilot"),
]

TABS = {
    "09_reports": [
        ("Detection Report", "09b_reports_detection"),
        ("Incident Reports", "09c_reports_incidents"),
        ("Export", "09d_reports_export"),
        ("Compliance", "09e_reports_compliance"),
        ("Live Evidence", "09f_reports_live_evidence"),
    ],
    "10_settings": [
        ("General", "10b_settings_general"),
        ("Telegram", "10c_settings_telegram"),
        ("AI Config", "10d_settings_ai"),
        ("NDR / Response", "10e_settings_ndr"),
        ("Clear Data", "10f_settings_clear"),
        ("Company", "10g_settings_company"),
    ],
    "11_soc_ops": [
        ("MITRE ATT&CK", "11b_soc_mitre"),
        ("SOAR Playbooks", "11c_soc_soar"),
        ("Online Learning", "11d_soc_online"),
        ("Server Health", "11e_soc_health"),
        ("ML Registry", "11f_soc_ml"),
    ],
    "13_assets": [
        ("Inventory", "13b_assets_inventory"),
        ("Topology", "13c_assets_topology"),
        ("Host profile", "13d_assets_host"),
        ("Identity / UEBA", "13e_assets_ueba"),
    ],
    "14_hunting": [
        ("Hunt", "14b_hunting_hunt"),
        ("Forensics PCAP", "14c_hunting_pcap"),
        ("Protocol / DNS / TLS", "14d_hunting_protocol"),
    ],
    "15_response": [
        ("IOC", "15b_response_ioc"),
        ("Allow / Block", "15c_response_allow"),
        ("Approvals", "15d_response_approvals"),
        ("Webhooks", "15e_response_webhooks"),
        ("Sensors", "15f_response_sensors"),
    ],
}


def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1600,2200")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--force-device-scale-factor=1")
    return webdriver.Chrome(options=opts)


def wait_app(d, t=60):
    WebDriverWait(d, t).until(lambda x: x.execute_script("return !!document.querySelector('[data-testid=\"stApp\"]')"))
    time.sleep(1)


def is_logged_in(d) -> bool:
    src = d.page_source
    return ("Logout" in src) or ("Total Flows" in src and "Sign In" not in src) or ("ONLINE" in src and "Secure Login" not in src)


def login(d):
    d.get(BASE + "/")
    wait_app(d)
    time.sleep(2)
    if is_logged_in(d):
        print("already in")
        return
    inputs = d.find_elements(By.CSS_SELECTOR, "div[data-testid='stTextInput'] input")
    inputs[0].click(); inputs[0].send_keys(Keys.CONTROL, "a"); inputs[0].send_keys("admin")
    inputs[1].click(); inputs[1].send_keys(Keys.CONTROL, "a"); inputs[1].send_keys("admin123")
    time.sleep(0.3)
    d.find_element(By.CSS_SELECTOR, "button[data-testid='baseButton-primaryFormSubmit']").click()
    WebDriverWait(d, 40).until(lambda x: is_logged_in(x))
    time.sleep(2.5)
    print("logged in", is_logged_in(d))


def shot(d, path: Path):
    # expand height carefully without full navigation
    h = d.execute_script(
        "const m=document.querySelector('[data-testid=\"stMain\"]')||document.body;"
        "return Math.max(m.scrollHeight||0, document.body.scrollHeight||0, 1600);"
    )
    d.set_window_size(1600, min(int(h) + 120, 12000))
    time.sleep(0.7)
    # scroll main to top
    d.execute_script("window.scrollTo(0,0); const m=document.querySelector('[data-testid=\"stMain\"]'); if(m) m.scrollTop=0;")
    time.sleep(0.3)
    d.save_screenshot(str(path))
    ok = is_logged_in(d)
    print(f"  {path.name}: {path.stat().st_size//1024}KB logged_in={ok}")


def click_nav(d, label: str) -> bool:
    # Streamlit sidebar nav links
    links = d.find_elements(By.CSS_SELECTOR, "[data-testid='stSidebarNav'] a, [data-testid='stSidebarNavLink']")
    for a in links:
        txt = (a.text or "").strip()
        if txt == label or label in txt:
            d.execute_script("arguments[0].click();", a)
            time.sleep(2.5)
            wait_app(d)
            return True
    # fallback xpath
    for a in d.find_elements(By.XPATH, f"//*[contains(@data-testid,'Sidebar')]//a[contains(., '{label}')]"):
        d.execute_script("arguments[0].click();", a)
        time.sleep(2.5)
        wait_app(d)
        return True
    return False


def click_tab(d, tab_text: str) -> bool:
    for t in d.find_elements(By.CSS_SELECTOR, "button[role='tab'], button[data-baseweb='tab']"):
        if tab_text.lower() in (t.text or "").lower():
            d.execute_script("arguments[0].click();", t)
            time.sleep(1.8)
            return True
    return False


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    d = make_driver()
    try:
        d.get(BASE + "/")
        wait_app(d)
        time.sleep(1.5)
        shot(d, OUT / "00_login.png")

        login(d)
        time.sleep(1)
        shot(d, OUT / "01_home.png")

        for key, label in NAV:
            if key == "01_home":
                continue
            print("NAV", label)
            if not click_nav(d, label):
                print("  FAIL nav", label)
                continue
            if not is_logged_in(d):
                print("  lost session; re-login")
                login(d)
                click_nav(d, label)
            shot(d, OUT / f"{key}.png")
            for tab, fname in TABS.get(key, []):
                print("  TAB", tab)
                if click_tab(d, tab):
                    shot(d, OUT / f"{fname}.png")
                else:
                    print("  WARN no tab", tab)
        print("DONE")
    finally:
        d.quit()


if __name__ == "__main__":
    main()
