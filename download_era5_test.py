import cdsapi

dataset = "reanalysis-era5-pressure-levels"

request = {
    "product_type": ["reanalysis"],
    "variable": [
        "geopotential",
        "temperature",
        "u_component_of_wind",
        "v_component_of_wind",
        "vertical_velocity",
    ],
    "year": ["2020"],
    "month": ["01"],
    "day": [
        "01", "02", "03", "04", "05", "06"
    ],
    "time": [
        "00:00",
        "06:00",
        "12:00",
        "18:00",
    ],
    "pressure_level": [
        "1000",
        "850",
        "700",
        "500",
        "300",
        "200",
        "100",
    ],
    "data_format": "netcdf",
    "download_format": "unarchived",
    "area": [
        -17.5,
        -60,
        -42.5,
        -30,
    ],
}

client = cdsapi.Client()
client.retrieve(dataset, request).download("era5_test.nc")

print("DONE: era5_test.nc")