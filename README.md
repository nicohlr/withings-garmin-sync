# Withings-Garmin Sync

This project is inspired by [withings-sync](https://github.com/jaroslawhartman/withings-sync). It provides a Python script that is scheduled to run via a GitHub Actions workflow. The Github action script fetches data from Withings and uploads it to Garmin Connect every day at midnight.

## Setup & Usage

To use this script, you'll need to set up a few things:

Create a withings client app from [here](https://account.withings.com/partner/add_oauth2) and set the following environment variables with your app details:

    - WITHINGS_CALLBACK_URL
    - WITHINGS_CLIENT_ID
    - WITHINGS_CONSUMER_SECRET

Then, use the `get_first_connexion_credentials` function from the `src/withings.py` file to get the needed credentials. Set these credentials to the following environment variables:

    - WITHINGS_ACCESS_TOKEN
    - WITHINGS_AUTH_CODE
    - WITHINGS_REFRESH_TOKEN

You can now run the script `src/sync.py` to fetch you withings data and send them to Garmin Connect. Use a github action linked to your repo to automate the process (see `.github/workflows/sync-wt-gc.yml` for an example).
