## Unofficial Medicover application

This is a python script for automating the process of getting a doctor's appointment at Medicover.

It is based on
* medihunter: https://github.com/medihunter/medihunter
* luxmed-bot: https://github.com/dyrkin/luxmed-bot

## Installation

Install the dependencies with poetry
```bash
pip install poetry
poetry install
```

## Usage

### CLI

####  Available Commands

`new_monitoring`

* Usage: `python app.py new_monitoring [options]`
* Description: Creates a new monitoring session.
* Options:
  * `--username`: Your Medicover username. (required)
  * `--password`: Your Medicover password. (required)
  * `--location_id`: The ID of the location. (required)
  * `--specialization_id`: The ID of the specialization. (required)
  * `--clinic_id`: The ID of the clinic. (required)
  * `--doctor_id`: The ID of the doctor. (required)
  * `--date_start`: The start date of the monitoring session. (optional, default: `current date`)
  * `--time_start`: The start time of the monitoring session. (optional, default: `07:00`)
  * `--date_end`: The end date of the monitoring session. (optional, default: `current date + 30 days`)
  * `--time_end`: The end time of the monitoring session. (optional, default: `23:00`)

**Note**: If `required` options are not provided, the script will ask for it in an interactive mode.

### Telegram bot

TODO add telegram bot description

## Environment variables

## License



