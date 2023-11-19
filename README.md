# home-assistant-SCL
Home Assistant helper to import Seattle City Light power useage

This will sign into your Seattle City Light web portal and scrape the latest power useage for each of your power meters, sending it to Home Assistant through MQTT.

## Known limitations
I haven't found an API for this, so the script will literally open a browser window and scrape your Seattle City Light account. If someone knows a more efficient way to fetch this data, I beg them to contribute.
This uses a webdriver, so it is unlikely to run correctly on the Home Assistant OS device. I run it on a separate windows machine.

The data on SCL's site is a day behind. But Home Assistant assumes all sensor readings are from the current moment. This means there's usually an off-by-one error where yesterday's actual power usage is attributed to today in HA. Posting historical data to HA is complicated and beyond my abilities. Feel free to contribute fixes for this.

My personal account has 2 power meters. I haven't debugged this on normal accounts with just 1 meter. Hopefully it still works.

## Prereqs
Home Assistant with MQTT configured

run `pip install -r requirements.txt`

## Use
Create an account at https://myutilities.seattle.gov/eportal/

Fill out `config.ini` using the name and password to your SCL account above, and your MQTT server details, and a good temp directory. For non-windows users, you'll want to replace c:/temp.

If you'd prefer to do your own scheduling, set polling=false. Otherwise the script will loop at intervals.

On any machine in your home network, Run `python scrape_scl.py`

If the sensors don't automatically appear in HA (they didn't for me...) then add them to your config.yaml like so:

```
mqtt:
  sensor:
    - name: "SCL<YOUR METER NUMBER HERE>"
      state_topic: "homeassistant/sensor/SCL<YOUR METER NUMBER HERE>/state"
```

## Desired improvements
Non-browser-based scraping. Maybe someone can figure out how to authenticate and get the results from an HTTP endpoint directly.
(If this isn't possible, at least replace the dumb sleeps in the script with smarter polling)

Attribute data to the correct day in HA, not just the current.

Debug MQTT auto-discovery

Create an actual HA addon or integration, rather than a script.
