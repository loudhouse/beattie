# Privacy policy

Effective date: October 22, 2026  
Bot name: Beattie (Wexlercord Bot)  
Source code: https://github.com/loudhouse/beattie  
Support: https://discord.gg/YJKgCeMDy  

This policy explains what data Beattie reads, stores in PostgreSQL, holds in memory, and sends to external services.

## Data read in real time

Beattie uses Discord Gateway Intents, including the Message Content Intent (`Intents.all()`), to process messages as they arrive.

If automatic crossposting (`crosspost auto`) is turned on in a server, channel, or DM, the bot checks incoming messages for `"http"` to spot supported media links. Messages without a supported link or a valid command prefix are ignored.

During commands and crossposts, the bot also checks user IDs, channel IDs, server IDs, role permissions (`manage_guild` and `manage_messages`), channel NSFW flags, and the server's file upload size limit (`filesize_limit`). None of this real-time data is written to disk unless a command saves a setting or message record listed below.

## Data stored in PostgreSQL

Beattie does not log chat history or store user profiles. It writes to seven PostgreSQL tables:

- `guild`: stores the server `id`, disabled cog names (`cog_blacklist`), custom command `prefix`, and `reminder_channel` ID.
- `crosspost`: stores crosspost settings per server (`guild_id`, or `0` for DMs) and channel or category (`channel_id`). The saved fields are `auto` (boolean), `max_pages` (integer), `text` (`long`, `short`, or `none`), and `language` (two-letter ISO code).
- `crosspostblacklist`: stores `guild_id` and `site` for websites that a server administrator has blocked from crossposting.
- `crosspostmessage`: stores `sent_message` (the bot's reply ID), `invoking_message` (the user's message ID), and `invoking_user` (the user's Discord ID). The bot keeps this mapping so it can delete its crosspost if you delete your original message or react to the bot's post with `❌`.
- `reminder` and `recurring`: store `id`, `bot_id`, `guild_id`, `channel_id`, `message_id`, `user_id`, the scheduled `time`, your reminder `topic`, and, for repeating reminders, the `rrule` string in `recurring`.
- `timezone`: stores your `user_id` and IANA `timezone` string (such as `Europe/London`) when you set one with the `timezone` command.

## Temporary memory, files, and logs

Downloaded media, post text, and metadata from crossposted links are cached in RAM (`queue_cache`, capped at 1 GB) so the bot does not have to download the same post twice. Cache entries are dropped when memory fills up, when the bot restarts, or when an administrator runs `crosspost evict`.

The bot also keeps three smaller caches in RAM:
- Recent `crosspostmessage` mappings stay in memory for 24 hours (`MESSAGE_CACHE_TTL`).
- The `chan` command keeps the last 500 command message IDs in memory so deleting your command also deletes the bot's reply.
- The `gelbooru`, `rule34`, and `e621` commands cache search results per channel until the list runs out or the bot restarts.

If a file needs format conversion through `ffmpeg` or ImageMagick (such as MP4 to GIF, m3u8 to MP4, WebP or AVIF to PNG, or Pixiv Ugoira zip extraction), the bot writes temporary files to system storage (`NamedTemporaryFile` or `TemporaryDirectory`) and deletes them as soon as the upload finishes.

Runtime warnings and unhandled command errors are written to daily log files (`discordYYYYMMDDHHMM.log`). Every 24 hours, older logs are compressed with `lzma` (`.xz`) and appended to `logs.tar`. When a command fails with an unhandled error, the log records the server name, channel name, command name, failing URL, and Python traceback.

## External requests

Beattie does not sell or share user data. When you run a command or post a supported URL, the bot queries the relevant site or API to fetch the result:

- Crosspost handlers fetch posts from Bluesky, Twitter/X (via fxtwitter and vxtwitter), Pixiv, Tumblr (via Tumbex), Inkbunny, FurAffinity mirrors (`xfuraffinity.net` and `fxraffinity.net`), Danbooru, Gelbooru, e621, Rule34, Derpibooru, ExHentai/E-Hentai, Fanbox, HentaiEra and its mirrors, Hiccears, Hitomi, Imgur, Itaku, Lofter, Mastodon/Misskey/PeerTube instances, Mousepad, nhentai, Paheal, Pillowfort, Poipiku, TikTok (via tnktok), Y-Gallery, YouTube Community, and 4chan (live boards and archives). Some requests are routed through Smartproxy or FlareSolverr.
- When translation is enabled, post text is sent to LibreTranslate or DeepL.
- Utility commands query SauceNAO (`saucenao`), Wolfram|Alpha (`wolfram`), Scryfall (`scry`), Jisho (`jisho`), Urban Dictionary (`urbandictionary`), and xkcd (`xkcd`, plus DuckDuckGo HTML search when searching xkcd by text).

These requests send only the URL, search term, or post text being processed. Discord user IDs, usernames, and server details are never sent to these services.

## Deleting your data

You can remove your stored data directly from Discord:

- To delete a crosspost and its `crosspostmessage` database row, delete your original message or react to the bot's crosspost with `❌`.
- One-time reminders are deleted from `reminder` as soon as they fire. To remove a pending or recurring reminder, run `remind list` and then `remind delete <ID>`.
- Run `timezone unset` to delete your row from the `timezone` table.
- Server administrators can run `crosspost clear` to delete `crosspost` rows for a specific channel, category, or the entire server.
- If you have left a server or want any remaining database records for your user ID or server ID deleted manually, join https://discord.gg/YJKgCeMDy and ask the bot owner. If the Discord invite has expired, please create a Github issue and be careful not to include any personal information, as Github issues are public.