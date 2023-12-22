# Withings-Garmin Sync

This project is inspired by [withings-sync](https://github.com/jaroslawhartman/withings-sync). It provides a Python script that is scheduled to run via a GitHub Actions workflow. The Github action script fetches data from Withings and uploads it to Garmin Connect every day at midnight.

## Setup

To use this script, you'll need to set up a few environment variables needed to connect the two services.

### Withings Setup

1. Create a Withings application [here](https://account.withings.com/partner/add_oauth2) and set the following environment variables with your app details:

    - `WITHINGS_CALLBACK_URL`
    - `WITHINGS_CLIENT_ID`
    - `WITHINGS_CONSUMER_SECRET`

> [!NOTE]
> You can create an empty GitHub Pages static site using your repo and use it as the callback URL for your Withings application.

2. Use the `get_first_connexion_credentials` function from the `src/withings.py` file to get the needed credentials. Set these credentials to the following environment variables:

    - `WITHINGS_ACCESS_TOKEN`
    - `WITHINGS_AUTH_CODE`
    - `WITHINGS_REFRESH_TOKEN`

### Garmin Connect Setup

Set up these two environment variables with your Garmin Connect credentials:

- `GARMIN_USERNAME`
- `GARMIN_PASSWORD`

## Usage

Once you've set up the environment variables, you can run the `src/sync.py` script to fetch your Withings data and send it to Garmin Connect. 

To automate the process, you can use a GitHub Action linked to your repo. See `.github/workflows/sync-wt-gc.yml` for an example.