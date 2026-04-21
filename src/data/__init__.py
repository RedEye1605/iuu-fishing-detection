"""Data acquisition and generation modules for IUU fishing detection."""

from src.data.gfw_client import GFWClient
from src.data.weather_client import generate_sample_marine_weather
from src.data.synthetic import generate_dataset
from src.data.bps_client import create_manual_data_template, save_sample_data
from src.data.viirs_setup import generate_sample_vbd_data
from src.data.mpa_setup import generate_sample_mpa_data

__all__ = [
    "GFWClient",
    "generate_sample_marine_weather",
    "generate_dataset",
    "create_manual_data_template",
    "save_sample_data",
    "generate_sample_vbd_data",
    "generate_sample_mpa_data",
]
