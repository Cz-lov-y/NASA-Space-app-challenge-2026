import time
import os
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = "/Users/yuetang/.gemini/antigravity/brain/e7a15003-b7a4-4e08-97b3-103a87c5001e"
os.makedirs(ARTIFACT_DIR, exist_ok=True)

def test_milestone1():
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
        time.sleep(2) # Allow Three.js textures and R3F canvas to initialize

        title = page.title()
        print(f"Page Title: {title}")

        # 1. Capture initial state screenshot
        initial_img = os.path.join(ARTIFACT_DIR, "initial_state.png")
        page.screenshot(path=initial_img)
        print(f"Initial state screenshot saved to: {initial_img}")

        # 2. Test Introduction Modal
        print("Testing Introduction Modal...")
        page.click("button:has-text('Introduction')")
        time.sleep(1)
        modal_img = os.path.join(ARTIFACT_DIR, "intro_modal_state.png")
        page.screenshot(path=modal_img)
        print(f"Intro modal screenshot saved to: {modal_img}")

        # Close modal
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # 3. Test Instructions Modal
        print("Testing Instructions Modal...")
        page.click("button:has-text('Instructions')")
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # 4. Test Methodology Modal
        print("Testing Methodology Modal...")
        page.click("button:has-text('Methodology')")
        time.sleep(0.5)
        page.keyboard.press("Escape")
        time.sleep(0.5)

        # 5. Test Globe Click / Coordinate Selection
        print("Clicking on Earth globe to inspect coordinates...")
        # Canvas is full screen; center of screen has the Earth
        canvas = page.locator("canvas")
        box = canvas.bounding_box()
        # Click slightly above center of Earth
        click_x = box["x"] + box["width"] * 0.48
        click_y = box["y"] + box["height"] * 0.46
        page.mouse.click(click_x, click_y)
        time.sleep(1.5) # Wait for smooth leftward shift and sliding panel animation

        # Capture selected point screenshot
        selected_img = os.path.join(ARTIFACT_DIR, "location_selected_state.png")
        page.screenshot(path=selected_img)
        print(f"Location selected screenshot saved to: {selected_img}")

        # 6. Test Preset Dropdown: Select Demo Region
        print("Selecting 'Synthetic Demo Region' from Target Hotspots...")
        # Click dropdown button to open
        page.locator("header .relative button").first.click()
        time.sleep(0.5)
        page.click("button:has-text('Synthetic Demo Region')")
        time.sleep(1.5)

        # Capture Demo Region selected screenshot
        demo_img = os.path.join(ARTIFACT_DIR, "demo_region_state.png")
        page.screenshot(path=demo_img)
        print(f"Demo region screenshot saved to: {demo_img}")

        # 7. Test Deselect & Return to Center
        print("Clicking 'Center Globe' to reset view...")
        page.click("button:has-text('Center Globe')")
        time.sleep(1.5) # Wait for slide out and center animation

        centered_img = os.path.join(ARTIFACT_DIR, "return_centered_state.png")
        page.screenshot(path=centered_img)
        print(f"Return centered screenshot saved to: {centered_img}")

        print("Console errors/warnings:", console_errors)

        browser.close()
        print("Milestone 1 browser test completed successfully!")

if __name__ == "__main__":
    test_milestone1()
