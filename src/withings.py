"""This module takes care of the communication with Withings."""
import os
import time
import base64
import logging
import requests
import nacl.encoding
import nacl.utils

from nacl.public import PrivateKey, PublicKey, Box
from datetime import date, datetime

log = logging.getLogger("withings")

AUTHORIZE_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
GETMEAS_URL = "https://wbsapi.withings.net/measure?action=getmeas"


class WithingsOAuth2:
    """This class takes care of the Withings OAuth2 authentication"""

    app_config = user_config = None

    def __init__(self):
        try:
            self.app_config = {
                "callback_url": os.environ["WITHINGS_CALLBACK_URL"],
                "client_id": os.environ["WITHINGS_CLIENT_ID"],
                "consumer_secret": os.environ["WITHINGS_CONSUMER_SECRET"],
            }
            self.user_config = {
                "access_token": os.environ["WITHINGS_ACCESS_TOKEN"],
                "authentification_code": os.environ["WITHINGS_AUTH_CODE"],
                "refresh_token": os.environ["WITHINGS_REFRESH_TOKEN"],
            }
            self.gh_token = os.environ["GH_TOKEN"]
            self.gh_repository = os.environ["GH_REPOSITORY"]
        except KeyError:
            raise AttributeError("Some ENVIRONMENT variables are not found.")

        self.refresh_accesstoken()
        self.update_github_secret(
            secret_name="WITHINGS_ACCESS_TOKEN",
            secret_value=self.user_config["access_token"],
            github_repository=self.gh_repository,
            github_token=self.gh_token
        )
        self.update_github_secret(
            secret_name="WITHINGS_REFRESH_TOKEN",
            secret_value=self.user_config["refresh_token"],
            github_repository=self.gh_repository,
            github_token=self.gh_token
        )

    def refresh_accesstoken(self):
        """refresh Withings access token"""
        log.info("Refresh Access Token")

        params = {
            "action": "requesttoken",
            "grant_type": "refresh_token",
            "client_id": self.app_config["client_id"],
            "client_secret": self.app_config["consumer_secret"],
            "refresh_token": self.user_config["refresh_token"],
        }

        req = requests.post(TOKEN_URL, params)
        resp = req.json()
        if resp.get("status") != 0:
            raise AttributeError(
                "Withings login failed, please check your credentials."
            )
        body = resp.get("body")

        self.user_config["access_token"] = body.get("access_token")
        self.user_config["refresh_token"] = body.get("refresh_token")

    def encrypt_secret(self, public_key: str, secret_value: str) -> str:
        """Encrypt the secret with the provided public key using sodium lib"""
        public_key_bytes = base64.b64decode(public_key)
        public_key = PublicKey(public_key_bytes)

        private_key = PrivateKey.generate()
        sealed_box = Box(private_key, public_key)

        encrypted = sealed_box.encrypt(
            secret_value.encode(), encoder=nacl.encoding.Base64Encoder
        )
        return encrypted.decode("utf-8")

    def get_public_key(self, github_token, github_repository):
        """Get the public key for the repository's secrets."""
        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github+json",
        }
        response = requests.get(
            f"https://api.github.com/repos/{github_repository}/actions/secrets/public-key",
            headers=headers,
        )
        response.raise_for_status()
        return response.json()["key"], response.json()["key_id"]

    def update_github_secret(
        self, secret_name, secret_value, github_token, github_repository
    ):
        public_key, key_id = self.get_public_key(
            github_token, github_repository
        )
        encrypted_value = self.encrypt_secret(public_key, secret_value)

        headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        data = {
            "encrypted_value": encrypted_value,
            "key_id": key_id,
        }

        url = f"https://api.github.com/repos/{github_repository}/actions/secrets/{secret_name}"

        try:
            logging.info(f"Updating secret: {secret_name} for repository: {github_repository}")
            response = requests.put(url, headers=headers, json=data)
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
            logging.info(f"Successfully updated secret: {secret_name}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to update secret: {secret_name}. Error: {e}")
            raise e  # Re-raise the exception after logging


class WithingsAccount:
    """This class gets measurements from Withings"""

    def __init__(self):
        self.withings = WithingsOAuth2()

    def get_lastsync(self):
        """get last sync timestamp"""
        if not self.withings.user_config.get("last_sync"):
            return int(time.mktime(date.today().timetuple()))
        return self.withings.user_config["last_sync"]

    def set_lastsync(self):
        """set last sync timestamp"""
        self.withings.user_config["last_sync"] = int(time.time())
        log.info("Saving Last Sync")
        self.withings.update_config()

    def get_measurements(self, startdate, enddate):
        """get Withings measurements"""
        log.info("Get Measurements")

        params = {
            "access_token": self.withings.user_config["access_token"],
            "category": 1,
            "startdate": startdate,
            "enddate": enddate,
        }

        req = requests.post(GETMEAS_URL, params)

        measurements = req.json()

        if measurements.get("status") == 0:
            log.debug("Measurements received")
            return [
                WithingsMeasureGroup(g)
                for g in measurements.get("body").get("measuregrps")
            ]
        return None

    def get_height(self):
        """get height from Withings"""
        height = None
        height_timestamp = None
        height_group = None

        log.debug("Get Height")

        params = {
            "access_token": self.withings.user_config["access_token"],
            "meastype": WithingsMeasure.TYPE_HEIGHT,
            "category": 1,
        }

        req = requests.post(GETMEAS_URL, params)

        measurements = req.json()

        if measurements.get("status") == 0:
            log.debug("Height received")

            # there could be multiple height records. use the latest one
            for record in measurements.get("body").get("measuregrps"):
                height_group = WithingsMeasureGroup(record)
                if height is not None:
                    if height_timestamp is not None:
                        if height_group.get_datetime() > height_timestamp:
                            height = height_group.get_height()
                else:
                    height = height_group.get_height()
                    height_timestamp = height_group.get_datetime()

        return height


class WithingsMeasureGroup:
    """This class takes care of the group measurement functions"""

    def __init__(self, measuregrp):
        self._raw_data = measuregrp
        self.grpid = measuregrp.get("grpid")
        self.attrib = measuregrp.get("attrib")
        self.date = measuregrp.get("date")
        self.category = measuregrp.get("category")
        self.measures = [WithingsMeasure(m) for m in measuregrp["measures"]]

    def __iter__(self):
        for measure in self.measures:
            yield measure

    def __len__(self):
        return len(self.measures)

    def get_datetime(self):
        """convenient function to get date & time"""
        return datetime.fromtimestamp(self.date)

    def get_raw_data(self):
        """convenient function to get raw data"""
        return self.measures

    def get_weight(self):
        """convenient function to get weight"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_WEIGHT:
                return round(measure.get_value(), 2)
        return None

    def get_height(self):
        """convenient function to get height"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_HEIGHT:
                return round(measure.get_value(), 2)
        return None

    def get_fat_free_mass(self):
        """convenient function to get fat free mass"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_FAT_FREE_MASS:
                return round(measure.get_value(), 2)
        return None

    def get_fat_ratio(self):
        """convenient function to get fat ratio"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_FAT_RATIO:
                return round(measure.get_value(), 2)
        return None

    def get_fat_mass_weight(self):
        """convenient function to get fat mass weight"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_FAT_MASS_WEIGHT:
                return round(measure.get_value(), 2)
        return None

    def get_diastolic_blood_pressure(self):
        """convenient function to get diastolic blood pressure"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_DIASTOLIC_BLOOD_PRESSURE:
                return round(measure.get_value(), 2)
        return None

    def get_systolic_blood_pressure(self):
        """convenient function to get systolic blood pressure"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_SYSTOLIC_BLOOD_PRESSURE:
                return round(measure.get_value(), 2)
        return None

    def get_heart_pulse(self):
        """convenient function to get heart pulse"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_HEART_PULSE:
                return round(measure.get_value(), 2)
        return None

    def get_temperature(self):
        """convenient function to get temperature"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_TEMPERATURE:
                return round(measure.get_value(), 2)
        return None

    def get_sp02(self):
        """convenient function to get sp02"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_SP02:
                return round(measure.get_value(), 2)
        return None

    def get_body_temperature(self):
        """convenient function to get body temperature"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_BODY_TEMPERATURE:
                return round(measure.get_value(), 2)
        return None

    def get_skin_temperature(self):
        """convenient function to get skin temperature"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_SKIN_TEMPERATURE:
                return round(measure.get_value(), 2)
        return None

    def get_muscle_mass(self):
        """convenient function to get muscle mass"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_MUSCLE_MASS:
                return round(measure.get_value(), 2)
        return None

    def get_hydration(self):
        """convenient function to get hydration"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_HYDRATION:
                return round(measure.get_value(), 2)
        return None

    def get_bone_mass(self):
        """convenient function to get bone mass"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_BONE_MASS:
                return round(measure.get_value(), 2)
        return None

    def get_pulse_wave_velocity(self):
        """convenient function to get pulse wave velocity"""
        for measure in self.measures:
            if measure.type == WithingsMeasure.TYPE_PULSE_WAVE_VELOCITY:
                return round(measure.get_value(), 2)
        return None


class WithingsMeasure:
    """This class takes care of the individual measurements"""

    TYPE_WEIGHT = 1
    TYPE_HEIGHT = 4
    TYPE_FAT_FREE_MASS = 5
    TYPE_FAT_RATIO = 6
    TYPE_FAT_MASS_WEIGHT = 8
    TYPE_DIASTOLIC_BLOOD_PRESSURE = 9
    TYPE_SYSTOLIC_BLOOD_PRESSURE = 10
    TYPE_HEART_PULSE = 11
    TYPE_TEMPERATURE = 12
    TYPE_SP02 = 54
    TYPE_BODY_TEMPERATURE = 71
    TYPE_SKIN_TEMPERATURE = 73
    TYPE_MUSCLE_MASS = 76
    TYPE_HYDRATION = 77
    TYPE_BONE_MASS = 88
    TYPE_PULSE_WAVE_VELOCITY = 91
    TYPE_VO2MAX = 123
    TYPE_QRS_INTERVAL = 135
    TYPE_PR_INTERVAL = 136
    TYPE_QT_INTERVAL = 137
    TYPE_CORRECTED_QT_INTERVAL = 138
    TYPE_ATRIAL_FIBRILLATION_PPG = 139
    TYPE_FAT_MASS_SEGMENTS = 174
    TYPE_EXTRACELLULAR_WATER = 168
    TYPE_INTRACELLULAR_WATER = 169
    TYPE_VISCERAL_FAT = 170
    TYPE_MUSCLE_MASS_SEGMENTS = 175
    TYPE_VASCULAR_AGE = 155
    TYPE_ATRIAL_FIBRILLATION = 130
    TYPE_NERVE_HEALTH_LEFT_FOOT = 158
    TYPE_NERVE_HEALTH_RIGHT_FOOT = 159
    TYPE_NERVE_HEALTH_FEET = 167
    TYPE_ELECTRODERMAL_ACTIVITY_FEET = 196
    TYPE_ELECTRODERMAL_ACTIVITY_LEFT_FOOT = 197
    TYPE_ELECTRODERMAL_ACTIVITY_RIGHT_FOOT = 198

    withings_table = {
        TYPE_WEIGHT: ["Weight", "kg"],
        TYPE_HEIGHT: ["Height", "meter"],
        TYPE_FAT_FREE_MASS: ["Fat Free Mass", "kg"],
        TYPE_FAT_RATIO: ["Fat Ratio", "%"],
        TYPE_FAT_MASS_WEIGHT: ["Fat Mass Weight", "kg"],
        TYPE_DIASTOLIC_BLOOD_PRESSURE: ["Diastolic Blood Pressure", "mmHg"],
        TYPE_SYSTOLIC_BLOOD_PRESSURE: ["Systolic Blood Pressure", "mmHg"],
        TYPE_HEART_PULSE: ["Heart Pulse", "bpm"],
        TYPE_TEMPERATURE: ["Temperature", "celsius"],
        TYPE_SP02: ["SP02", "%"],
        TYPE_BODY_TEMPERATURE: ["Body Temperature", "celsius"],
        TYPE_SKIN_TEMPERATURE: ["Skin Temperature", "celsius"],
        TYPE_MUSCLE_MASS: ["Muscle Mass", "kg"],
        TYPE_HYDRATION: ["Hydration", "kg"],
        TYPE_BONE_MASS: ["Bone Mass", "kg"],
        TYPE_PULSE_WAVE_VELOCITY: ["Pulse Wave Velocity", "m/s"],
        TYPE_VO2MAX: ["VO2 max", "ml/min/kg"],
        TYPE_QRS_INTERVAL: ["QRS interval duration based on ECG signal", "ms"],
        TYPE_PR_INTERVAL: ["PR interval duration based on ECG signal", "ms"],
        TYPE_QT_INTERVAL: ["QT interval duration based on ECG signal", "ms"],
        TYPE_CORRECTED_QT_INTERVAL: [
            "Corrected QT interval duration based on ECG signal",
            "ms",
        ],
        TYPE_ATRIAL_FIBRILLATION_PPG: [
            "Atrial fibrillation result from PPG",
            "ms",
        ],
        TYPE_FAT_MASS_SEGMENTS: ["Fat Mass for segments in mass unit", "kg"],
        TYPE_EXTRACELLULAR_WATER: ["Extracellular Water", "kg"],
        TYPE_INTRACELLULAR_WATER: ["Intracellular Water", "kg"],
        TYPE_VISCERAL_FAT: ["Extracellular Water", "kg"],
        TYPE_MUSCLE_MASS_SEGMENTS: [
            "Muscle Mass for segments in mass unit",
            "kg",
        ],
        TYPE_VASCULAR_AGE: ["Vascular age", "years"],
        TYPE_ATRIAL_FIBRILLATION: ["Atrial fibrillation result", "ms"],
        TYPE_NERVE_HEALTH_LEFT_FOOT: ["Nerve Health Score left foot", ""],
        TYPE_NERVE_HEALTH_RIGHT_FOOT: ["Nerve Health Score right foot", ""],
        TYPE_NERVE_HEALTH_FEET: ["Nerve Health Score feet", ""],
        TYPE_ELECTRODERMAL_ACTIVITY_FEET: ["Electrodermal activity feet", ""],
        TYPE_ELECTRODERMAL_ACTIVITY_LEFT_FOOT: [
            "Electrodermal activity left foot",
            "",
        ],
        TYPE_ELECTRODERMAL_ACTIVITY_RIGHT_FOOT: [
            "Electrodermal activity right foot",
            "",
        ],
    }

    def __init__(self, measure):
        self._raw_data = measure
        self.value = measure.get("value")
        self.type = measure.get("type")
        self.unit = measure.get("unit")
        self.type_s = self.withings_table.get(self.type, ["unknown", ""])[0]
        self.unit_s = self.withings_table.get(self.type, ["unknown", ""])[1]

    def __str__(self):
        return f"{self.type_s}: {self.get_value()} {self.unit_s}"

    def json_dict(self):
        return {
            f"{self.type_s.replace(' ','_')}": {
                "Value": round(self.get_value(), 2),
                "Unit": f"{self.unit_s}",
            }
        }

    def get_value(self):
        """get value"""
        return self.value * pow(10, self.unit)
