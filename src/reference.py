#!/usr/bin/env python3
import requests
import sys
import os

# --- User Configuration ---
# <<<--- EDIT THESE VALUES --->>>
FORECAST_DATE = "20250422"  # Format: YYYYMMDD
FORECAST_TIME = "06"       # Use "06" or "18" for short-scale (scda)
FORECAST_STEP = "24"       # Hours, 0 to 90, step of 3 (e.g., 0, 3, 6,... 87, 90)
OUTPUT_DIR = "."          # Directory to save the file ('.' means current directory)
# <<<--- END OF USER CONFIGURATION --->>>

# --- Constants (Based on documentation for 'scda' stream) ---
ROOT_URL = "https://data.ecmwf.int/forecasts"
MODEL = "ifs"
RESOLUTION = "0p25"
STREAM = "scda" # Short cut-off HRES atmospheric fields
TYPE = "fc"     # Forecast type for scda
FORMAT = "grib2"
UNIT = "h"

# --- Basic Input Sanity Check (minimal) ---
if FORECAST_TIME not in ["06", "18"]:
    print(f"Error: FORECAST_TIME must be '06' or '18' for stream '{STREAM}'. Please edit the script.", file=sys.stderr)
    sys.exit(1)
try:
    step_int = int(FORECAST_STEP)
    if not (0 <= step_int <= 90 and step_int % 3 == 0):
        raise ValueError("Step out of range or not divisible by 3")
except ValueError:
    print(f"Error: FORECAST_STEP ('{FORECAST_STEP}') must be an integer between 0 and 90 (inclusive) and divisible by 3. Please edit the script.", file=sys.stderr)
    sys.exit(1)

# --- Construct URL and Filename ---
# Filename format: [yyyymmdd][HH]0000-[step][U]-[stream]-[type].[format]
filename = f"{FORECAST_DATE}{FORECAST_TIME}0000-{FORECAST_STEP}{UNIT}-{STREAM}-{TYPE}.{FORMAT}"
# Full path format: [ROOT]/[yyyymmdd]/[HH]z/[model]/[resol]/[stream]/filename
relative_path = f"{FORECAST_DATE}/{FORECAST_TIME}z/{MODEL}/{RESOLUTION}/{STREAM}/{filename}"
full_url = f"{ROOT_URL}/{relative_path}"

# Simple derived output filename
output_filename = f"{FORECAST_DATE}_{FORECAST_TIME}z_{FORECAST_STEP}h_{STREAM}_{TYPE}.{FORMAT}"
output_path = os.path.join(OUTPUT_DIR, output_filename)

# --- Download ---
print(f"Attempting to download:")
print(f"  URL: {full_url}")
print(f"  Saving to: {output_path}")

try:
    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Use stream=True for potentially large files
    with requests.get(full_url, stream=True, timeout=60) as r: # Added timeout
        r.raise_for_status()  # Check for HTTP errors like 404 Not Found

        with open(output_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): # Process in chunks
                f.write(chunk)

    print(f"Download successful: {output_path}")

except requests.exceptions.HTTPError as e:
    print(f"\nHTTP Error: {e}", file=sys.stderr)
    if e.response.status_code == 404:
        print(" >> File not found. Check date/time/step or if data is available.", file=sys.stderr)
    elif e.response.status_code >= 500:
        print(" >> Server error. Please try again later.", file=sys.stderr)
    # Clean up empty file potentially created by 'open' before error
    if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
        try:
            os.remove(output_path)
            print(f"Removed empty file artifact: {output_path}")
        except OSError: pass
    sys.exit(1) # Exit on HTTP error
except requests.exceptions.RequestException as e:
    print(f"\nDownload Error: {e}", file=sys.stderr)
    sys.exit(1)
except OSError as e:
    print(f"\nFile System Error (writing to {output_path}): {e}", file=sys.stderr)
    sys.exit(1)