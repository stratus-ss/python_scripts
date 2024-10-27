from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import requests
import json
from m3u8_to_mp4 import M3U8_Playlist
import argparse
import yaml

parser = argparse.ArgumentParser()

parser.add_argument(
    "--yaml", type=str, help="Path to YAML configuration file", required=True
)
args = parser.parse_args()

with open(args.yaml, "r") as yaml_file:
    config_dict = yaml.safe_load(yaml_file)


login_url = config_dict["base-url"] + "/login"
course_id = config_dict["course-url"].split("/")[-1]
api_course_url = config_dict["api-url"] + "/courses/my/" + course_id


need_token = config_dict["refresh-token"]
if need_token:
    # Create a new ChromeOptions object
    chrome_options = Options()

    # Add argument to enable headless mode
    chrome_options.add_argument("--headless")

    # Set up Chrome WebDriver
    driver = webdriver.Chrome(options=chrome_options)

    driver.get(login_url)

    username_input = driver.find_element(By.NAME, "email")
    password_input = driver.find_element(By.NAME, "password")

    username_input.send_keys(config_dict["username"])
    password_input.send_keys(config_dict["password"])

    # Wait for the login button to be clickable
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in')]"))
    )

    # Click the login button
    login_button.click()

    # Wait for the page to load after clicking the button
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    cookies = driver.get_cookies()

    print("Cookies after login:")
    for cookie in cookies:
        print(f"{cookie['name']}: {cookie['value']}")

    time.sleep(2)
    driver.get(config_dict["course-url"])

    time.sleep(2)

    js_token = driver.execute_script(
        """
        var token = localStorage.getItem('token');
        return token;
        """
    )
    config_dict["token"] = js_token
    with open(args.yaml, "w") as config_file:
        yaml.dump(config_dict, config_file)
else:
    js_token = config_dict["token"]

add_course_title = config_dict["add-course-title-to-video"]
headers = {"Authorization": f"Bearer {js_token}"}
# course_api_response is a dict that contains all of the "Section" data
# A section, is basically like a course chapter with videos revolving around a specific theme
course_api_response = json.loads(requests.get(api_course_url, headers=headers).text)
title = ""
for course_chapter in course_api_response["data"]["sections"]:
    for lecture in course_chapter["lectures"]:
        video_order = str(lecture["order"]).zfill(2)
        if add_course_title:
            title = course_api_response["data"]["title"] + "-"
        title = title + (
            "Chapter_"
            + str(course_chapter["order"])
            + "-"
            + course_chapter["title"]
            + "-"
            + video_order
            + "_"
            + lecture["title"]
            + ".mp4"
        )
        title = title.replace(" ", "_")
        highest_quality_video = requests.get(
            lecture["video"]["playListUrl"]
        ).text.split()[-1]
        video_base_url = "/".join(lecture["video"]["playListUrl"].split("/")[:-1])
        video_m3u8 = video_base_url + "/" + highest_quality_video
        video_m3u8 = M3U8_Playlist(f"URL:{video_m3u8}")
        video_m3u8.append_to_segments(
            video_base_url + "/" + highest_quality_video.split("/")[0] + "/"
        )
        video_m3u8.to_mp4(title, delete_after=True, run_async=True)
print()
