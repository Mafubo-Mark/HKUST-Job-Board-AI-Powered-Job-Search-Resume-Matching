"""Run the HKUST scraper, then match the exported jobs to your resume.

Keep main.py, hkust_job_scraper.py, job_matcher.py, and resume.pdf together.
Install: python3 -m pip install selenium pypdf openai
Run: python3 main.py
Outputs: hkust_jobs.json, hkust_jobs_to_ai.json, and result.json in this folder.
"""

import hkust_job_scraper as scraper  # Browser login, filters, and JSON export.
import job_matcher as matcher  # Resume extraction, DeepSeek scoring, and ranking.


def main():
    # Stage 1: export into the exact file the matcher will read.
    driver = scraper.create_driver()
    try:
        scraper.login_to_hkust(driver)
        scraper.filter_jobs(driver)
        jobs = scraper.export_jobs_to_json(driver, matcher.INPUT_JSON)
    finally:
        # Release Chrome before scoring; also close it on scraping errors or Ctrl+C.
        driver.quit()

    # Stage 2: empty exports clear old outputs without reading a resume or asking for a key.
    results = matcher.main()
    print(f"Finished: {len(jobs)} jobs exported; {len(results)} AI responses saved.")
    return results


if __name__ == "__main__":
    # Report errors without starting a second stage after a failed scrape.
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. Saved progress is retained.")
        raise SystemExit(130)
    except Exception as error:
        print(f"Program error: {type(error).__name__}: {error}")
        raise SystemExit(1)
