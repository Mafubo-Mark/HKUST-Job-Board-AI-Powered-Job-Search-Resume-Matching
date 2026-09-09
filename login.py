import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


TARGET_URL = "https://career.hkust.edu.hk/web/job.php?keywords="


def create_driver():
    options = Options()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)

    return driver


def final_job_board_loaded(driver):
    """
    Only when the final job list #job-list appears,
    the following process is considered completed:
    Login -> checkbox -> Agree 1 -> Agree 2
    """

    try:
        job_lists = driver.find_elements(
            By.CSS_SELECTOR,
            "#job-list"
        )

        return (
            len(job_lists) > 0
            and job_lists[0].is_displayed()
        )

    except Exception:
        return False


def login_to_hkust(driver):
    print("Opening the HKUST Career website...")

    driver.get(TARGET_URL)

    print()
    print("Please complete the following steps in the browser:")
    print()
    print("1. Log in to HKUST")
    print("2. Tick the checkbox")
    print("3. Click the first Agree button")
    print("4. Enter the Job Board Declaration page")
    print("5. Click the second Agree button")
    print()
    print("The program is waiting for the actual Job Board to load...")

    WebDriverWait(
        driver,
        300,
        poll_frequency=1
    ).until(
        final_job_board_loaded
    )

    print()
    print("=" * 70)
    print("Successfully entered the actual Job Board")
    print("=" * 70)

    print()
    print("Current URL:")
    print(driver.current_url)

    time.sleep(1)

    return True