"""This module handles the Garmin connectivity."""
import logging
import garth
import io

log = logging.getLogger("garmin")


class GarminConnect:
    """Main GarminConnect class"""

    def __init__(self) -> None:
        self.client = garth.Client()

    def login(self, email, password):
        try:
            self.client.login(email, password)
        except Exception as ex:
            raise ConnectionError(
                "Authentication failure: {}. Did you enter correct credentials?".format(
                    ex
                )
            )

    def upload_file(self, ffile):
        """upload fit file to Garmin connect"""
        # Convert the fitfile to a in-memory file for upload
        fit_file = io.BytesIO(ffile.getvalue())
        fit_file.name = "withings.fit"
        self.client.upload(fit_file)
        return True


def sync_garmin(fit_file, args):
    """Sync generated fit file to Garmin Connect"""
    garmin = GarminConnect()
    garmin.login(args.garmin_username, args.garmin_password)
    return garmin.upload_file(fit_file)
