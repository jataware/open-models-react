## Open data

A subset of ECMWF real-time forecast data from the IFS and AIFS models are made available to the public free of charge.

* The existing 0.4-degree data has been deprecated as of 25th February 2025. 

## About our forecasts

### Ensemble forecasts looking from days to seasons ahead

Our forecasts span a range of timescales: medium range (up to 15 days ahead); extended range (up to 46 days ahead) and long range (up to one year ahead).

We run ensembles (or groups) of forecasts across all these timescales, which help to determine how the weather is likely to evolve and the chances, for example, of hazardous weather or extremes.

### Our Integrated Forecasting System (IFS)

All our operational forecasts are produced with the ECMWF Integrated Forecasting System (IFS), which has a global numerical model of the Earth system at its heart.

Datasets include real-time forecasts, re-forecasts, analyses and reanalyses.


## How to access real-time open data

### File format

The files are in GRIB edition 2 format, except for trajectories which are in BUFR edition 4 format. We recommend using ecCodes version 2.38.0 or newer to manipulate the GRIB and BUFR files. 

### File-naming convention

The files are provided with the following naming convention (when accessing through HTTP):

```
[ROOT]/[yyyymmdd]/[HH]z/[model]/[resol]/[stream]/[yyyymmdd][HH]0000-[step][U]-[stream]-[type].[format]
```

where: 

- [ROOT]  is the top-level URL of one of the sites hosting the data. See the above for possible values. 
- [yyyymmdd] is the reference date of the forecasts (base date).
- [HH] is the reference time of the forecasts. Values are 00, 06 , 12  and 18. 
- [model] is the production model (IFS or AIFS).  Note: Only use the IFS model. 
- [resol]  is the horizontal resolution of the data. Only options available: 0p25
- [stream] is the forecasting system that produces the data.  Values are:
    - oper - high-resolution forecast, atmospheric fields 
    - enfo - ensemble forecast, atmospheric fields (not applicable for AIFS model)
    - waef - ensemble forecast, ocean wave fields, (not applicable for AIFS model)
    - wave - wave model, (not applicable for AIFS model)
    - scda  - short cut-off high-resolution forecast, atmospheric fields (also known as "high-frequency products") (not applicable for AIFS model)
    - scwv  - short cut-off high-resolution forecast, ocean wave fields (also known as "high-frequency products") (not applicable for AIFS model) and 
    - mmsf  - multi-model seasonal forecasts fields from the ECMWF model only (not applicable for AIFS model).  
- [step] is the forecast time step expressed in units U  
- [U] is the unit used for the time step. Values are h for hours and m for month. The latter is only valid for seasonal forecasts (mmsf). 
- [type] is once of fc (forecast), ef (ensemble forecast), ep (ensemble probabilities) or tf (trajectory forecast for tropical cyclone tracks). 
- [format] is grib2 for all fields, and bufr for the trajectories. 

The valid combinations of the above are:

```
format=bufr, type=tf 
   HH=00/12 
  	  stream=enfo/oper, step=240h 
   HH=06/18 
      stream=enfo, step=144h 
      stream=scda, step=90h 
format=grib2 
   HH=00/12 
      stream=enfo/waef 
        type=ef, step=0h to 144h by 3h, 144h to 360h by 6h 
        type=ep, step=240h/360h 
      stream=oper, wave 
        type=fc, step=0h to 144h by 3h, 144h to 240h by 6h 
   HH=06/18 
      stream=enfo/waef 
        type=ef, step=0h to 144h by 3h 
      stream= scda /scwv 
        type=fc, step=0h to 90h by 3h 
   HH=00 
   	  stream=mmsf, type=fc, u=m, step=1m to 7m 
```

### Index files

Each GRIB file is associated with a corresponding index file, accessible by substituting the '.grib2' extension with '.index' in the URL. Index files are text files where each line is a JSON record (JSON details here). Each record represents a GRIB field in the corresponding GRIB file, described using the MARS query language, for example:

```
{{"domain": "g", "date": "20240301", "time": "1200", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "6", "levelist": "1000", "levtype": "pl", "param": "q", "_offset": 3857250, "_length": 609046}}
```

In addition, the keys `_offset` and `_length` represent the byte offset and length of the corresponding field. This allows the download of a single field using the HTTP Byte-Range request.

### Differences between MARS language and file naming convention  
There are some minor differences between the normal MARS request language and the open data file naming. 

These are summarised in the table for information. 

| MARS |  |  | File names |  |  |
|------|------|------|------|------|------|
| Stream | Type | Step | Stream | Type | Step |
| oper/wave | fc | nnn | oper/wave | fc | nnn |
| enfo/waef | cf | nnn | enfo/waef | ef | nnn |
| enfo/waef | pf | nnn | enfo/waef | ef | nnn |
| enfo/waef | em | nnn | enfo/waef | ep | 240 if nnn <= 240 else 360 |
| enfo/waef | es | nnn | enfo/waef | ep | 240 if nnn <= 240 else 360 |
| enfo/waef | ep | nnn | enfo/waef | ep | 240 if nnn <= 240 else 360 |
| msmm | fcmean/em | nnn | mmsf | fc | nnn |


### Examples of accessing files through HTTP (download files)

#### Examples of how to access real-time open data with wget or curl

In the following examples, if shown [ROOT], replace with:
https://data.ecmwf.int/forecasts

Although all of the examples provided here use wget, curl (or python requests) can similarly be used to download the products.

##### Examples using wget for products based on the Atmospheric Model high-resolution (HRES) forecasts

###### HRES direct model output

> Products at time=00 or time=12

For direct model output from the Atmospheric model high-resolution (HRES) forecast time 00 and 12 UTC, stream=oper and type=fc should be used. 

The steps available are 0h to 144h by 3h and 150h to 240h by 6h. The file format is grib2.

The example shows how to download the file containing all of the parameters available at step=24h from the 00UTC HRES forecast run on 25 January 2022:

```
wget https://data.ecmwf.int/forecasts/20240301/00z/ifs/0p25/oper/20240301060000-24h-oper-fc.grib2
```

> Products at time=06 or time=18

For direct model output from the Atmospheric model high-resolution (HRES) forecast time 06 and 18 UTC, stream=scda and type=fc should be used. 

The steps available are 0h to 90h by 3h only.  The file format is grib2.

The example shows how to download the file containing all of the parameters available at step=24h from the 06 UTC HRES forecast run on 25 January 2022:

```
wget https://data.ecmwf.int/forecasts/20240301/06z/ifs/0p25/scda/20240301060000-24h-scda-fc.grib2
```

##### Download a single field with wget

The example above downloads a single file containing all of the parameters for that dataset at the specific forecast step or steps.

It is also possible to download of a single field using the HTTP Byte-Range request feature.

>  Example: download temperature at 2m at step=24h from the 00 UTC HRES forecast

To download only the 2m temperature at step=24h from the 00 UTC HRES forecast on 25 January 2022, first download the associated index file by substituting the '.grib2' extension with '.index' in the URL:

```
wget https://data.ecmwf.int/forecasts/20240301/00z/ifs/0p25/oper/20240301000000-24h-oper-fc.index
```

Inspect the index file and look for the entry for 2m temperature ('param' : '2t')

```
...
{{"domain": "g", "date": "20240301", "time": "0000", "expver": "0001", "class": "od", "type": "fc", "stream": "oper", "step": "24", "levtype": "sfc", "param": "2t", "_offset": 17459800, "_length": 609046}}
...
```

Use the values of `_offset`  and `_length` keys for this record  to construct the start_bytes and end_bytes:

```
start_bytes = _offset = 17459800
end_bytes = _offset + _length - 1 = 17459800 + 609046 - 1 = 18068845
```

Warning: The "_offset" and "_length" values of a specific field will change from forecast run to forecast run.  It is necessary to redo this computation for each download.

Use the start_bytes and end_bytes values calculated to pass the range of bytes to be downloaded to wget, this time for the .grib2 file:

```
wget https://data.ecmwf.int/forecasts/20240301/00z/ifs/0p25/oper/20240301000000-24h-oper-fc.grib2 --header="Range: bytes=17459800-18068845"
```

Alternatively, curl can be used:

```
curl --range  17459800-18068845 https://data.ecmwf.int/forecasts/20240301/00z/ifs/0p25/oper/20240301000000-24h-oper-fc.grib2 --output 2t.grib2
```

Red Warning: Multipart byte ranges of the form:
```
wget ... --header="Range: bytes=17459800-18068845, 18168021-1819654"
```
are not supported by all servers.
