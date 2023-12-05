"""This module syncs measurement data from Withings to Garmin a/o TrainerRoad."""
import argparse
import time
import sys
import logging

from datetime import date, datetime

from withings import WithingsAccount
from garmin import sync_garmin
from utils import (
    generate_fitdata,
    prepare_syncdata,
)


def sync(withings, args):
    """Sync measurements from Withings to Garmin a/o TrainerRoad"""

    if not args.fromdate:
        startdate = withings.get_lastsync()
    else:
        startdate = int(time.mktime(args.fromdate.timetuple()))

    enddate = int(time.mktime(args.todate.timetuple())) + 86399
    logging.info(
        "Fetching measurements from %s to %s",
        time.strftime("%Y-%m-%d %H:%M", time.localtime(startdate)),
        time.strftime("%Y-%m-%d %H:%M", time.localtime(enddate)),
    )

    height = withings.get_height()
    groups = withings.get_measurements(startdate=startdate, enddate=enddate)

    # Only upload if there are measurement returned
    if groups is None or len(groups) == 0:
        logging.error("No measurements to upload for date or period specified")
        return

    _, _, syncdata = prepare_syncdata(height, groups, args)

    fit_data_weight, fit_data_blood_pressure = generate_fitdata(syncdata)

    if not args.no_upload:
        # Upload to Garmin Connect
        if args.garmin_username and (
            fit_data_weight is not None or fit_data_blood_pressure is not None
        ):
            logging.debug("attempting to upload fit file...")
            if fit_data_weight is not None:
                gar_wg_state = sync_garmin(fit_data_weight, args)
                if gar_wg_state:
                    logging.info(
                        "Fit file with weight information uploaded to Garmin Connect"
                    )
            if fit_data_blood_pressure is not None:
                gar_bp_state = sync_garmin(fit_data_blood_pressure, args)
                if gar_bp_state:
                    logging.info(
                        "Fit file with blood pressure information uploaded to Garmin Connect"
                    )
            if gar_wg_state or gar_bp_state:
                # Save this sync so we don't re-download the same data again (if no range has been specified)
                if not args.fromdate:
                    withings.set_lastsync()
        else:
            logging.info("No Garmin username - skipping sync")
    else:
        logging.info("Skipping upload")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "A tool for synchronisation of Withings "
            "(ex. Nokia Health Body) to Garmin Connect"
            " and Trainer Road or to provide a json string."
        )
    )

    def date_parser(date_string):
        return datetime.strptime(date_string, "%Y-%m-%d")

    parser.add_argument(
        "--garmin-username",
        "--gu",
        type=str,
        metavar="GARMIN_USERNAME",
        help="Username to log in to Garmin Connect.",
    )
    parser.add_argument(
        "--garmin-password",
        "--gp",
        type=str,
        metavar="GARMIN_PASSWORD",
        help="Password to log in to Garmin Connect.",
    )

    parser.add_argument(
        "--fromdate",
        "-f",
        type=date_parser,
        metavar="DATE",
        help="Date to start syncing from. Ex: 2023-12-20",
    )

    parser.add_argument(
        "--todate",
        "-t",
        type=date_parser,
        default=date.today(),
        metavar="DATE",
        help="Date for the last sync. Ex: 2023-12-30",
    )

    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Won't upload to Garmin Connect or TrainerRoad.",
    )

    parser.add_argument(
        "--features",
        nargs="+",
        default=[],
        metavar="BLOOD_PRESSURE",
        help="Enable Features like BLOOD_PRESSURE.",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Run verbosely."
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    logging.debug("Script invoked with the following arguments: %s", args)

    withings = WithingsAccount()
    sync(withings, args)
