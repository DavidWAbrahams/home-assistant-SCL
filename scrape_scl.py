import configparser
import csv
import glob
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import paho.mqtt.client as mqtt

config = configparser.ConfigParser()
config.read("config.ini")

TEMP_DIR = config["DEFAULT"]["temp_dir"]
SCL_USER_NAME = config["DEFAULT"]["scl_user_name"]
SCL_PASSWORD = config["DEFAULT"]["scl_password"]
MQTT_USER_NAME = config["DEFAULT"]["mqtt_user_name"]
MQTT_PASSWORD = config["DEFAULT"]["mqtt_password"]
MQTT_ADDRESS = config["DEFAULT"]["mqtt_address"]
POLLING = config.getboolean("DEFAULT", "polling")
POLLING_PERIOD_MINUTES = config.getint("DEFAULT", "polling_period_minutes")


file_path_template = os.path.join(TEMP_DIR, '\DailyUsage*.csv')


while(True):
  try:
    yesterday = (date.today() - timedelta(days=1))

    for f in glob.glob(file_path_template):
        os.remove(f)

    options = Options()
    options.add_experimental_option("prefs", {
      "download.default_directory": TEMP_DIR
    })
    driver = webdriver.Chrome(options=options)

    driver.get("https://myutilities.seattle.gov/eportal/")
    driver.set_window_size(1734, 1392)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.XPATH, "//button[text()=\"Log Into Your Profile\"]"))).click()
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "userName"))).send_keys(SCL_USER_NAME)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.NAME, "password"))).send_keys(SCL_PASSWORD)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn-lg"))).click()
    time.sleep(20)
    WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.LINK_TEXT, "View Usage"))).click()
    time.sleep(15)

    select = Select(driver.find_element(By.CSS_SELECTOR, ".form-control"))
    meter_ids = [s.text for s in select.options if s.text.isnumeric()]
    for meter_id in meter_ids:
      select = Select(driver.find_element(By.CSS_SELECTOR, ".form-control"))
      select.select_by_value(meter_id)
      time.sleep(4)
      driver.find_element(By.XPATH, "//button[text()=\"Daily\"]").click()
      time.sleep(10)
      WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".export-link"))).click()
      time.sleep(10)
      start_date = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder=\'Start Date\']")))
      start_date.clear()
      start_date.send_keys(yesterday.strftime("%m-%d-%Y"))
      end_date = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[placeholder=\'End Date\']")))
      end_date.clear()
      end_date.send_keys(yesterday.strftime("%m-%d-%Y"))
      driver.find_element(By.XPATH, "//button[text()=\"Update\"]").click()
      time.sleep(10)
      WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".export-link"))).click()
      time.sleep(10)

    driver.quit()

    # send to MQTT
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER_NAME, password=MQTT_PASSWORD)
    client.connect(MQTT_ADDRESS)

    latest_readings = {}
    latest_dates = {}
    for filename in glob.glob(file_path_template):
      with open(filename, 'r', newline='') as csvfile:
        next(csvfile) # skip the non-csv download date line 
        next(csvfile) # skip the empty line
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
          if row:
            row["Day"] == yesterday.strftime("%b %d")
            meter_id = row["Meter ID"]
            reading_date = datetime.strptime(row["Day"], "%b %d")
            reading = float(row["Consumption (kWh)"])
            if meter_id not in latest_readings or (reading_date > latest_dates[meter_id] and reading > 0):
              latest_readings[meter_id] = reading
              latest_dates[meter_id] = reading_date

    print(latest_readings)
    for meter_id in meter_ids:        
      config_payload = {
        "name": f"Seattle City Light meter {meter_id}",
        "state_topic": f"homeassistant/sensor/SCL{meter_id}/state",
        "state_class": "total_increasing",
        "unit_of_measurement": "kWh",
        "device_class": "energy",
        "value_template": "{{ value }}",
        "unique_id": f"scl_meter_{meter_id}",
        "device": {
          "identifiers": [
             "seattlecitylightscrapesensor"
          ],
          "name": "Seattle City Light",
          "model": "None",
          "manufacturer": "None"
        },
        "icon": "mdi:home-lightning-bolt-outline",
        "platform": "mqtt"
      }
      print(client.publish(topic=f"homeassistant/sensor/SCL{meter_id}/config",
                     payload=json.dumps(config_payload),
                     retain=True,
                     qos=0))
      time.sleep(1)
      print(client.publish(topic=f"homeassistant/sensor/SCL{meter_id}/state",
                     payload=json.dumps(latest_readings[str(meter_id)]),
                     retain=False,
                     qos=0).rc)
    client.disconnect()	 # gracefully disconnect
  except Exception as e:
    print("Error: ", e)
  if POLLING:
    time.sleep(60*60)
  else:
    break