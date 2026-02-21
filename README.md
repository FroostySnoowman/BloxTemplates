# BloxTemplates

## Setting Up
0. Create a new application on [Discord Developer Portal](https://discord.com/developers/applications), name it whatever you want, and agree to the terms of service.
1. Go to "Bot" and "Reset Token". Paste that token in the `config.yml` `TOKEN` section.
2. Enable "Presence Intent", "Server Members Intent", "Message Content Intent", in "Bot".
3. Edit profile picture, banner, and name in "Bot" to your desired liking.
4. Go to "Installation" and change the "Install Link" dropdown to "None".
5. Go to "OAuth2" and select "bot" and "applications.commands" under the "Scopes" section. Scroll down and select "Administrator" under the "Bot Permissions" section. Scroll down and copy the Generated URL. Paste this in your browser and add the bot to all your desired server(s).

## Configuration
0. Rename the `example-config.yml` file to `config.yml`.
1. Configure all desired content in the `config.yml` file.

## Running The Bot
0. Install Python 3.10+.
1. Run `pip3 install -r requirements.txt` to install required packages.
2. Run `python3 main.py` to run the bot.