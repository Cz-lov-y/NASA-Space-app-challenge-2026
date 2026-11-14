import time
import os
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = "/Users/yuetang/.gemini/antigravity/brain/e7a15003-b7a4-4e08-97b3-103a87c5001e"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def test_milestone2():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=True,
            args=["--use-gl=angle", "--use-angle=metal", "--enable-webgl"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)

        print("Navigating to http://localhost:3000/ ...")
        page.goto("http://localhost:3000/")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        # 1. Select Demo Region from Hotspots dropdown
        print("Selecting 'Synthetic Demo Region' from Target Hotspots...")
        page.locator("header .relative button").first.click()
        time.sleep(0.5)
        page.click("button:has-text('Synthetic Demo Region')")
        time.sleep(2) # Wait for Earth shift, panel sliding, and ECharts rendering

        # 2. Capture Timeseries Chart screenshot (Milestone 2 dual-axis view)
        ts_img = os.path.join(ARTIFACT_DIR, "milestone2_timeseries_chart.png")
        page.screenshot(path=ts_img)
        print(f"Timeseries chart screenshot saved to: {ts_img}")

        # 3. Test Indicator Toggle: Enable Temperature and Precipitation
        print("Toggling Temperature and Precipitation indicators...")
        page.click("button:has-text('Surface Temp')")
        time.sleep(0.5)
        page.click("button:has-text('Precipitation')")
        time.sleep(1)

        multi_img = os.path.join(ARTIFACT_DIR, "milestone2_multi_indicator_chart.png")
        page.screenshot(path=multi_img)
        print(f"Multi-indicator chart screenshot saved to: {multi_img}")

        # 4. Switch to Standardized Z-Score view
        print("Switching to Standardized Z-Score view...")
        page.click("button:has-text('Standardized Z-Score')")
        time.sleep(1)

        zscore_img = os.path.join(ARTIFACT_DIR, "milestone2_zscore_chart.png")
        page.screenshot(path=zscore_img)
        print(f"Z-Score chart screenshot saved to: {zscore_img}")

        # 5. Switch to Scientific Audit tab
        print("Switching to Scientific Audit tab...")
        page.click("button:has-text('Scientific Audit')")
        time.sleep(1)

        audit_img = os.path.join(ARTIFACT_DIR, "milestone2_scientific_audit.png")
        page.screenshot(path=audit_img)
        print(f"Scientific audit tab screenshot saved to: {audit_img}")

        # 6. Test Deselect & Return to Center
        print("Clicking 'Center Globe' to reset view...")
        page.click("button:has-text('Center Globe')")
        time.sleep(1.5)

        # 7. Test Arbitrary Coordinate Selection on Globe
        print("Clicking on arbitrary coordinate on Earth globe...")
        canvas = page.locator("canvas")
        box = canvas.bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.45, box["y"] + box["height"] * 0.48)
        time.sleep(1.5)

        arbitrary_img = os.path.join(ARTIFACT_DIR, "milestone2_arbitrary_point.png")
        page.screenshot(path=arbitrary_img)
        print(f"Arbitrary point screenshot saved to: {arbitrary_img}")

        # Close panel again
        page.keyboard.press("Escape")
        time.sleep(1)

        print("Console errors/warnings:", console_errors)
        browser.close()
        print("Milestone 2 automated browser verification completed successfully!")

if __name__ == "__main__":
    test_milestone2()
