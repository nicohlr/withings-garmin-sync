# Withings-Garmin Sync

This project is inspired by [withings-sync](https://github.com/jaroslawhartman/withings-sync). It provides a Python script that is scheduled to run via a GitHub Actions workflow. The script fetches data from Withings and uploads it to Garmin Connect every day at midnight.

## Features

- **Automated Data Sync:** The script automatically fetches your health data from Withings and uploads it to your Garmin Connect account.
- **Scheduled Execution:** The script is set to run every day at midnight, ensuring your Garmin Connect data is always up-to-date with your latest Withings data.
- **GitHub Actions Integration:** The script execution is managed by a GitHub Actions workflow, making it easy to maintain and monitor.

## Setup

To use this script, you'll need to set up a few things:

1. **GitHub Secrets:** The script requires access to your Withings and Garmin Connect accounts. You'll need to set up the necessary access tokens and account details as secrets in your GitHub repository.
2. **Python Environment:** The script is written in Python and requires a Python environment to run. The GitHub Actions workflow takes care of setting up this environment for you.

## Usage

Once everything is set up, the script will run automatically every day at midnight. You can check the GitHub Actions tab in your repository to see the status of the script execution.