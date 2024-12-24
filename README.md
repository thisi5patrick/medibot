# Unofficial Medicover Appointment Automation

## Overview
This project automates the process of securing a doctor's appointment at Medicover.
It is inspired by:
* medihunter: https://github.com/medihunter/medihunter
* luxmed-bot: https://github.com/dyrkin/luxmed-bot

This project has been a standalone fork from the `medihunter` repo.

The project provides:
- **CLI Tool**: For setting up and managing appointment monitoring.
- **Telegram Bot**: A user-friendly interface to interact with the appointment management system.

## Requirements
- **Python**: Version 3.12 or newer.
- `poetry`

## Installation

1. **Clone the repository**:
```shell
git clone git@github.com:thisi5patrick/medibot.git
cd medibot
```

Install the dependencies with poetry
```shell
poetry install
```

## Usage

### 1. Command Line Interface (CLI)

The CLI lets users create appointment monitoring sessions and view future appointments through their Medicover account.
#### Available Commands
* `new_monitoring`: Create a new monitoring session to look for available appointments.
  * Usage: `python src/app.py new-monitoring [options]`
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


* `future_appointments`: View your future appointments.
  * Usage: `python src/app.py future-appointments [options]`
  * Options:
    * `--username`: Your Medicover username. (required)
    * `--password`: Your Medicover password. (required)

**Note**: If `required` options are not provided, the script will ask for it in an interactive mode.
**Note 2**: You can install the package with `pip install -e .` which will let you to interact with the CLI via `medibot <command>` instead of `python src/app.py`

#### Notifications

##### Telegram
The CLI provides a way to send notifications to telegram when the monitoring has found an available appointment date.

In order for this to work, you must set up a Bot in telegram by your own.

More info can be found in [the documentation](https://core.telegram.org/bots).

After setting up, you must gather these variables.
```shell
NOTIFIERS_TELEGRAM_CHAT_ID=<your chat id>
NOTIFIERS_TELEGRAM_BOT_TOKEN=<your bot token>
```

You can find these data by following [this guide](https://docs.tracardi.com/qa/how_can_i_get_telegram_bot/).

Place these variables into `.env` file or by exporting them like
```shell
export NOTIFIERS_TELEGRAM_CHAT_ID=<your chat id>
export NOTIFIERS_TELEGRAM_BOT_TOKEN=<your bot token>
```

### 2. Telegram Bot

The Telegram bot provides an easy-to-use interface to interact with the system. 
It offers the following commands (once logged in):

* `/start`: Start the bot.
* `/login`: Authenticate with your Medicover account.
* `/new_monitoring`: Set up appointment monitoring.
* `/active_monitorings`: View and manage active appointment monitorings.
* `/future_appointments`: Display the list of upcoming appointments.
* `/settings`: Modify bot settings (e.g., language).
* `/help`: Access the help page.

In order to set up and run your own telegram bot, you must provide the following env variable:
```shell
TELEGRAM_BOT_TOKEN=
```

Place these variables into `.env` file or by exporting them like
```shell
export TELEGRAM_BOT_TOKEN=<your telegram bot token>
```

Now you can run the bot on your machine with:
```shell
make run-telegram
```

## Docker

The project provides Docker configurations to simplify the process of running both the CLI tool and the Telegram Bot. 
Below are the steps to build and run the application using Docker.

To simplify building and running the Docker containers a `Makefile` is provided with
the necessary commands.

### Building & Running Docker Images

#### Telegram

In order to build and run the image, use the command:

```shell
make docker-telegram
```

This will build the proper images and automatically start the Telegram bot.

#### CLI

This make command only builds the image:
```shell
make build-docker-cli
```

In order to run the image use:
```shell
docker run -it --rm cli-bot <your-options>
```

##### Example usage:
1. Create a New Monitoring Session:
```shell
docker run -it --rm cli-bot new-monitoring
```
```shell
docker run -it --rm cli-bot new-monitoring
    --username=<your-username>
    --password=<your-password>
    etc.
```

2. View Future Appointments:
```shell
docker run -it --rm cli-bot future-appointments
```
