import cdsapi

dataset = "reanalysis-era5-single-levels"

request = {
    "product_type": ["reanalysis"],
    "variable": [
        "top_net_solar_radiation",
        "top_net_thermal_radiation",
        "total_precipitation",
    ],
    "year": ["2020"],
    "month": ["01"],
    "day": ["01", "02", "03", "04", "05", "06"],
    "time": [f"{hour:02d}:00" for hour in range(24)],
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
client.retrieve(dataset, request).download("era5_surface_test.nc")

print("DONE: era5_surface_test.nc")
