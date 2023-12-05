import logging
from fit import FitEncoderWeight, FitEncoderBloodPressure


def generate_fitdata(syncdata):
    """Generate fit data from measured data"""
    logging.debug("Generating fit data...")

    weight_measurements = list(
        filter(lambda x: (x["type"] == "weight"), syncdata)
    )
    blood_pressure_measurements = list(
        filter(lambda x: (x["type"] == "blood_pressure"), syncdata)
    )

    fit_weight = None
    fit_blood_pressure = None

    if len(weight_measurements) > 0:
        fit_weight = FitEncoderWeight()
        fit_weight.write_file_info()
        fit_weight.write_file_creator()

        for record in weight_measurements:
            fit_weight.write_device_info(timestamp=record["date_time"])
            fit_weight.write_weight_scale(
                timestamp=record["date_time"],
                weight=record["weight"],
                percent_fat=record["fat_ratio"],
                percent_hydration=record["percent_hydration"],
                bone_mass=record["bone_mass"],
                muscle_mass=record["muscle_mass"],
                bmi=record["bmi"],
            )

        fit_weight.finish()
    else:
        logging.info("No weight data to sync for FIT file")

    if len(blood_pressure_measurements) > 0:
        fit_blood_pressure = FitEncoderBloodPressure()
        fit_blood_pressure.write_file_info()
        fit_blood_pressure.write_file_creator()

        for record in blood_pressure_measurements:
            fit_blood_pressure.write_device_info(timestamp=record["date_time"])
            fit_blood_pressure.write_blood_pressure(
                timestamp=record["date_time"],
                diastolic_blood_pressure=record["diastolic_blood_pressure"],
                systolic_blood_pressure=record["systolic_blood_pressure"],
                heart_rate=record["heart_pulse"],
            )

        fit_blood_pressure.finish()
    else:
        logging.info("No blood pressure data to sync for FIT file")

    logging.debug("Fit data generated...")
    return fit_weight, fit_blood_pressure


def prepare_syncdata(height, groups, args):
    """Prepare measurement data to be sent"""
    syncdata = []

    last_date_time = None
    last_weight = None

    sync_dict = {}

    for group in groups:
        # Get extra physical measurements
        dt = group.get_datetime()
        # create a default group_data
        group_data = {
            "date_time": group.get_datetime(),
            "type": "None",
            "raw_data": group.get_raw_data(),
        }

        if dt not in sync_dict:
            sync_dict[dt] = {}

        if group.get_weight():
            group_data = {
                "date_time": group.get_datetime(),
                "height": height,
                "weight": group.get_weight(),
                "fat_ratio": group.get_fat_ratio(),
                "muscle_mass": group.get_muscle_mass(),
                "hydration": group.get_hydration(),
                "percent_hydration": None,
                "bone_mass": group.get_bone_mass(),
                "pulse_wave_velocity": group.get_pulse_wave_velocity(),
                "heart_pulse": group.get_heart_pulse(),
                "bmi": None,
                "raw_data": group.get_raw_data(),
                "type": "weight",
            }
        elif group.get_diastolic_blood_pressure():
            group_data = {
                "date_time": group.get_datetime(),
                "diastolic_blood_pressure": group.get_diastolic_blood_pressure(),
                "systolic_blood_pressure": group.get_systolic_blood_pressure(),
                "heart_pulse": group.get_heart_pulse(),
                "raw_data": group.get_raw_data(),
                "type": "blood_pressure",
            }

        # execute the code below, if this is not a whitelisted entry like weight and blood pressure
        if "weight" not in group_data and not (
            "diastolic_blood_pressure" in group_data
            and "BLOOD_PRESSURE" in args.features
        ):
            collected_metrics = "weight data"
            if "BLOOD_PRESSURE" in args.features:
                collected_metrics += " or blood pressure"

            logging.info(
                "%s This Withings metric contains no %s.  Not syncing...",
                dt,
                collected_metrics,
            )
            groupdata_log_raw_data(group_data)
            # for now, remove the entry as we're handling only weight and feature enabled data
            del sync_dict[dt]
            continue

        if height and "weight" in group_data:
            group_data["bmi"] = round(
                group_data["weight"] / pow(group_data["height"], 2), 1
            )
        if "hydration" in group_data and group_data["hydration"]:
            group_data["percent_hydration"] = round(
                group_data["hydration"] * 100.0 / group_data["weight"], 2
            )

        logging.debug("%s Detected data: ", dt)
        groupdata_log_raw_data(group_data)
        if "weight" in group_data:
            logging.debug(
                "Record: %s, type=%s\n"
                "height=%s m, "
                "weight=%s kg, "
                "fat_ratio=%s %%, "
                "muscle_mass=%s kg, "
                "percent_hydration=%s %%, "
                "bone_mass=%s kg, "
                "bmi=%s",
                group_data["date_time"],
                group_data["type"],
                group_data["height"],
                group_data["weight"],
                group_data["fat_ratio"],
                group_data["muscle_mass"],
                group_data["percent_hydration"],
                group_data["bone_mass"],
                group_data["bmi"],
            )
        if "diastolic_blood_pressure" in group_data:
            logging.debug(
                "Record: %s, type=%s\n"
                "diastolic_blood_pressure=%s mmHg, "
                "systolic_blood_pressure=%s mmHg, "
                "heart_pulse=%s BPM, ",
                group_data["date_time"],
                group_data["type"],
                group_data["diastolic_blood_pressure"],
                group_data["systolic_blood_pressure"],
                group_data["heart_pulse"],
            )

        # join groups with same timestamp
        for k, v in group_data.items():
            sync_dict[dt][k] = v

    last_measurement_type = None

    for group_data in sync_dict.values():
        syncdata.append(group_data)
        logging.debug("Processed data: ")
        for k, v in group_data.items():
            logging.debug("%s=%s", k, v)
        if last_date_time is None or group_data["date_time"] > last_date_time:
            last_date_time = group_data["date_time"]
            last_measurement_type = group_data["type"]
            logging.debug(
                "last_dt: %s last_weight: %s", last_date_time, last_weight
            )

    if last_measurement_type is None:
        logging.error("Invalid or no data detected")

    return last_measurement_type, last_date_time, syncdata


def groupdata_log_raw_data(groupdata):
    for dataentry in groupdata["raw_data"]:
        logging.debug("%s", dataentry)
