from archytas.tool_utils import tool


import requests
from typing import Literal, Optional, Tuple
from pathlib import Path
import json

import pdb

# --- CONSTANTS ---
BASE_URL = "https://data.ecmwf.int/forecasts"
Model = Literal["ifs"]
Resolution = Literal["0p25"]
Stream = Literal["oper", "enfo", "waef", "wave", "scda", "scwv", "mmsf"]
FileType = Literal["fc", "ef", "ep", "tf"]
FileFormat = Literal["grib2", "bufr"]
ForecastOffset = Literal["00", "06", "12", "18"]
VALID_MODELS = Model.__args__
VALID_RESOLUTIONS = Resolution.__args__
VALID_STREAMS = Stream.__args__
VALID_TYPES = FileType.__args__
VALID_FORMATS = FileFormat.__args__
VALID_HH = ForecastOffset.__args__

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

    # def download_full_product(
    #         self, 
    #         year: int,
    #         month: int,
    #         day: int, 
    #         hh: ForecastOffset,
    #         model: Model,
    #         resol: Resolution,
    #         stream: Stream,
    #         step: str,
    #         file_type: FileType,
    #         file_format: FileFormat,
    #         # save_path: Path
    #     ) -> None:
    #     date = f"{year:04d}{month:02d}{day:02d}"
    #     url = self.build_file_url(date, hh, model, resol, stream, step, file_type, file_format)
    #     save_path = Path(url).name
    #     self.download_file(url, save_path)

    @tool
    def download_forecast(
        self,
        year: int,
        month: int,
        day: int, 
        hh: str,
        stream: str,
        step_size: int,
        file_type: str,
        file_format: str,
        # save_path: None = None
    ) -> None:
        """
        Download forecast data from ECMWF.

        # Stream types:
        Stream | Meaning | Description | Typical Use
        oper | Operational high-res forecast | A deterministic, high-resolution single forecast run. Most common for short to medium range. | Get "the best guess" weather forecast.
        enfo | Ensemble atmospheric forecast | Multiple slightly different forecasts (~50 members) to capture uncertainty. | Risk analysis, probabilities (e.g., "30% chance of rain").
        waef | Ensemble ocean wave forecast | Ensemble forecasts, but for ocean waves instead of the atmosphere. | Probabilistic wave heights and wave energy.
        wave | Deterministic ocean wave forecast | High-res single run for ocean waves. | Exact wave height forecast.
        scda | Short cut-off high-res atmospheric forecast | High-res forecast delivered earlier but less complete (less observations assimilated). | Faster access, early morning decisions.
        scwv | Short cut-off ocean wave forecast | Same idea as scda, but for ocean wave forecasts. | Early warning about waves.
        mmsf | Multi-model seasonal forecast | Long-term (months ahead) multi-model forecasts, only ECMWF data exposed here. | Seasonal trends ("warmer than average summer?").

        # File types:
        Type | Meaning | Description | Usually paired with streams
        fc | Forecast | A single deterministic forecast field (e.g., wind speed, temperature, pressure). | oper, wave, scda, scwv, mmsf
        ef | Ensemble forecast | Single member of an ensemble. (Each member is a slightly perturbed model.) | enfo, waef
        ep | Ensemble probability | Probabilities derived from ensemble members. (e.g., "Probability temperature > 30°C is 20%.") | enfo, waef
        tf | Trajectory forecast | Tropical cyclone tracks in BUFR format. | oper, enfo

        Args:
            year (int): Year of the forecast.
            month (int): Month of the forecast.
            day (int): Day of the forecast.
            hh (str): Forecast start hour in the day, relative to UTC. Must be one of "00", "06", "12", or "18".
            stream (str): Stream type. Must be one of "oper", "enfo", "waef", "wave", "scda", "scwv", or "mmsf".
            step_size (int): Forecast step size in hours.
            file_type (str): Type of the file. Must be one of "fc", "ef", "ep", or "tf".
            file_format (str): Format of the file. Must be one of "grib2" or "bufr".
        """
        date = f"{year:04d}{month:02d}{day:02d}"
        step = f"{step_size}h"
        model = "ifs"
        resol = "0p25"
        url = self.build_file_url(date, hh, model, resol, stream, step, file_type, file_format)
        save_path = Path(url).name
        self.download_file(url, save_path)
        return f"Downloaded success. saved to {save_path}"



    # def download_single_param(self,
    #                            date: str,
    #                            hh: ForecastOffset,
    #                            model: Model,
    #                            resol: Resolution,
    #                            stream: Stream,
    #                            step: str,
    #                            file_type: str,
    #                            file_format: Literal['grib2'],
    #                            param: str,
    #                            output_path: Path
    #                            ) -> None:
    #     if file_format != "grib2":
    #         raise ValueError("Field-by-field download is only supported for grib2 format.")

    #     base_url = self.build_file_url(date, hh, model, resol, stream, step, file_type, file_format)
    #     index_url = base_url.replace(".grib2", ".index")

    #     self.download_field(index_url, base_url, param, output_path)


# --- Example Usage ---
ecmwf_client = ECMWFClient()
if __name__ == "__main__":
    ...
    # client.download_full_product(year=2025, month=4, day=28, hh="06", model="ifs", resol="0p25", stream="scda", step="24h", file_type="fc", file_format="grib2")#, save_path=Path("full.grib2"))
    # client.download_single_param(year=2025, month=4, day=28, hh="00", model="ifs", resol="0p25", stream="oper", step="24h", file_type="fc", file_format="grib2", param="2t", output_path=Path("2t.grib2"))
    # ecmwf_client.download_forecast(year=2025, month=4, day=28, hh="06", stream='scda', step_size=24, file_type='fc', file_format='grib2')