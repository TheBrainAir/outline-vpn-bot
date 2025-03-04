# Outline VPN Telegram Bot

A Simple Telegram bot for selling and managing Outline VPN subscriptions using Telegram's payment system.

## Features

- 🔐 Automated VPN key generation and management via Outline Server API
- 💳 Subscription management with different durations (1, 3, 6, 12 months)
- 💲 Integrated payment system using Telegram Stars
- 🔄 Automatic subscription expiration handling
- 📊 Admin panel with user statistics
- 🔔 Subscription expiration reminders

## Prerequisites

- Python 3.8 or higher
- A server to host your Outline VPN server
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- A Telegram payment provider token (for Telegram Stars)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/thebrainair/outline-vpn-bot.git
   cd outline-vpn-bot
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Setting Up Outline VPN Server

1. Install Outline Server by following the [official guide](https://getoutline.org/get-started/#step-1):
   - For Linux: `bash -c "$(wget -qO- https://raw.githubusercontent.com/Jigsaw-Code/outline-server/master/src/server_manager/install_scripts/install_server.sh)"`
   - For other platforms, download from [getoutline.org](https://getoutline.org/get-started/)

2. After installation, you'll receive:
   - A management API URL (needed for the bot configuration)
   - Credentials for the Outline Manager

3. Save your management API URL for later configuration.

## Bot Configuration

1. Create a bot via [@BotFather](https://t.me/BotFather) and obtain your bot token.

2. Enable payments for your bot in BotFather and get a payment provider token.

3. Configure environment variables (create a `.env` file in the project root):
   ```
   TG_API_KEY=your_telegram_bot_token
   OUTLINE_API_URL=your_outline_api_url
   PROVIDER_TOKEN=(donttouch)
   ADMIN_IDS=your_telegram_user_id,another_admin_id
   ```

   Alternatively, you can edit these values directly in the script:
   ```python
   API_TOKEN = "your_tg_api_key"
   OUTLINE_API_URL = "your_api_link_outline"
   PROVIDER_TOKEN = "your_payment_provider_token"
   ADMIN_IDS = [your_telegram_user_id]
   ```

## Running the Bot

Start the bot with:
```bash
python bot.py
```

For production deployment, it's recommended to use a process manager like systemd or PM2 to keep the bot running.

### Systemd Service (Recommended for Linux servers)

1. Create a systemd service file:
   ```bash
   sudo nano /etc/systemd/system/vpn-bot.service
   ```

2. Add the following configuration:
   ```
   [Unit]
   Description=Telegram VPN Bot
   After=network.target

   [Service]
   User=your_username
   WorkingDirectory=/path/to/outline-vpn-bot
   ExecStart=/usr/bin/python3 /path/to/outline-vpn-bot/bot.py
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl enable vpn-bot
   sudo systemctl start vpn-bot
   ```

4. Check service status:
   ```bash
   sudo systemctl status vpn-bot
   ```

## Usage

### Customer Flow

1. Users start the bot with `/start` command
2. They select payment duration (1, 3, 6, or 12 months)
3. After successful payment, users can get their VPN key from the "Get VPN" button
4. VPN keys are automatically revoked when subscriptions expire

### Admin Commands

- `/admin` - Access the admin panel
  - View general statistics (total users, active subscriptions)
  - View detailed user list
  - Monitor subscription statuses

## Database

The bot uses SQLite to store user data. The database file (`vpn_users.db`) is created automatically on first run.

## Customization

You can customize the subscription prices by modifying the `price_mapping` dictionary in the code:

```python
price_mapping = {
    1: 150,   # 1 month for 150 stars
    3: 405,   # 3 months for 405 stars
    6: 765,   # 6 months for 765 stars
    12: 1440  # 12 months for 1440 stars
}
```

## Security Considerations

- The bot stores VPN keys in the database. Ensure the database file permissions are restricted.
- Consider using HTTPS for your Outline API if your server supports it.
- Regularly backup your database file.

---
Created by [thebrainair](https://github.com/thebrainair)
