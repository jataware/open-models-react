from archytas.tool_utils import tool


import requests
from typing import Literal, Optional, Tuple
from pathlib import Path
import json

# --- CONSTANTS ---
BASE_URL = "https://data.ecmwf.int/forecasts"
VALID_MODELS = ["ifs"]
VALID_RESOLUTIONS = ["0p25"]
VALID_STREAMS = ["oper", "enfo", "waef", "wave", "scda", "scwv", "mmsf"]
VALID_TYPES = ["fc", "ef", "ep", "tf"]
VALID_FORMATS = ["grib2", "bufr"]
VALID_HH = ["00", "06", "12", "18"]

class ECMWFClient:
    def __init__(self, root_url: str = BASE_URL) -> None:
        self.root_url = root_url

    def _validate_args(self, model: str, resol: str, stream: str, file_type: str, file_format: str, hh: str) -> None:
        if model not in VALID_MODELS:
            raise ValueError(f"Invalid model '{model}'. Only allowed: {VALID_MODELS}")
        if resol not in VALID_RESOLUTIONS:
            raise ValueError(f"Invalid resolution '{resol}'. Only allowed: {VALID_RESOLUTIONS}")
        if stream not in VALID_STREAMS:
            raise ValueError(f"Invalid stream '{stream}'. Only allowed: {VALID_STREAMS}")
        if file_type not in VALID_TYPES:
            raise ValueError(f"Invalid type '{file_type}'. Only allowed: {VALID_TYPES}")
        if file_format not in VALID_FORMATS:
            raise ValueError(f"Invalid format '{file_format}'. Only allowed: {VALID_FORMATS}")
        if hh not in VALID_HH:
            raise ValueError(f"Invalid forecast hour '{hh}'. Only allowed: {VALID_HH}")

    def build_file_url(self, date: str, hh: str, model: str, resol: str, stream: str, step: str, file_type: str, file_format: str) -> str:
        self._validate_args(model, resol, stream, file_type, file_format, hh)
        filename = f"{date}{hh}0000-{step}-{stream}-{file_type}.{file_format}"
        url = f"{self.root_url}/{date}/{hh}z/{model}/{resol}/{stream}/{filename}"
        return url

    def download_file(self, url: str, save_path: Path) -> None:
        response = requests.get(url, stream=True)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download file. Status code: {response.status_code}\nURL: {url}")
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    def download_field(self, index_url: str, grib_url: str, param: str, output_path: Path) -> None:
        # Step 1: Download and parse index
        response = requests.get(index_url)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to download index file. Status code: {response.status_code}\nURL: {index_url}")
        lines = response.text.strip().splitlines()
        fields = [json.loads(line) for line in lines]

        # Step 2: Find the matching field
        matching = [field for field in fields if field.get("param") == param]
        if not matching:
            raise ValueError(f"Parameter '{param}' not found in index file.")
        field = matching[0]

        start_byte = field["_offset"]
        end_byte = start_byte + field["_length"] - 1

        # Step 3: Download the byte range
        headers = {"Range": f"bytes={start_byte}-{end_byte}"}
        field_response = requests.get(grib_url, headers=headers)
        if field_response.status_code not in (200, 206):
            raise RuntimeError(f"Failed to download field. Status code: {field_response.status_code}\nURL: {grib_url}")
        with open(output_path, 'wb') as f:
            f.write(field_response.content)

    def download_full_product(self, 
                               date: str, 
                               hh: Literal['00', '06', '12', '18'],
                               model: Literal['ifs'],
                               resol: Literal['0p25'],
                               stream: str,
                               step: str,
                               file_type: str,
                               file_format: Literal['grib2', 'bufr'],
                               save_path: Path
                               ) -> None:
        url = self.build_file_url(date, hh, model, resol, stream, step, file_type, file_format)
        self.download_file(url, save_path)

    def download_single_param(self,
                               date: str,
                               hh: Literal['00', '06', '12', '18'],
                               model: Literal['ifs'],
                               resol: Literal['0p25'],
                               stream: str,
                               step: str,
                               file_type: str,
                               file_format: Literal['grib2'],
                               param: str,
                               output_path: Path
                               ) -> None:
        if file_format != "grib2":
            raise ValueError("Field-by-field download is only supported for grib2 format.")

        base_url = self.build_file_url(date, hh, model, resol, stream, step, file_type, file_format)
        index_url = base_url.replace(".grib2", ".index")

        self.download_field(index_url, base_url, param, output_path)


# --- Example Usage ---
# client = ECMWFClient()
# client.download_full_product(date="20240301", hh="00", model="ifs", resol="0p25", stream="oper", step="24h", file_type="fc", file_format="grib2", save_path=Path("/tmp/full.grib2"))
# client.download_single_param(date="20240301", hh="00", model="ifs", resol="0p25", stream="oper", step="24h", file_type="fc", file_format="grib2", param="2t", output_path=Path("/tmp/2t.grib2"))
