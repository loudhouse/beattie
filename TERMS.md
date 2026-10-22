# Terms of service

Effective date: October 22, 2026  
Bot name: Beattie (Wexlercord Bot)  
Source code: https://github.com/loudhouse/beattie  
Support: https://discord.gg/zG849bNYqU  

These terms govern your use of Beattie on Discord. By adding Beattie to a Discord server, running a command, or posting a link in a channel where automatic crossposting is turned on, you agree to these terms, our [Privacy policy](PRIVACY.md), and Discord's Terms of Service and Community Guidelines.

## Age requirements

You must meet the minimum age required by Discord in your country (at least 13 years old, or the minimum age of digital consent in your jurisdiction) to use Beattie.

Anyone using the adult search commands (`gelbooru`, `rule34`, `e621`) or crossposting adult media from third-party websites must be at least 18 years old, or the age of legal majority in their jurisdiction if higher.

## How the bot works and intermediary status

Beattie is an automated utility tool. When you run a command or post a supported link, the bot fetches the requested material from the source website or API and posts it to the Discord channel where you made the request.

The bot operator does not select, review, edit, or endorse the third-party content that users fetch. Under United States law (47 U.S.C. § 230 and 17 U.S.C. § 512), European Union law (Articles 4 and 5 of the Digital Services Act), and United Kingdom law (the Electronic Commerce Regulations 2002 and the Online Safety Act 2023), Beattie operates as a passive technical conduit and temporary cache for user-directed requests.

The user who posts a link or runs a command (`invoking_user`) is the publisher of that request and is responsible for the content they bring into a Discord server or direct message.

## Third-party services and terms of service

Beattie proxies requests to and fetches material from third-party websites, mirrors, and APIs, including social networks, art platforms, imageboards, 4chan archives, translation providers (LibreTranslate and DeepL), and lookup tools (SauceNAO, Wolfram|Alpha, Scryfall, Jisho, Urban Dictionary, and xkcd).

Each of those external services has its own terms of service, acceptable use policies, and age restrictions. The bot operator is not affiliated with those third-party services and is not responsible for their terms of service, privacy policies, availability, or content, or for whether your requests through the bot comply with their rules. Review the terms of service of any third-party website or API before using Beattie to fetch or proxy content from it, as you are responsible for following those terms where applicable.

## Adult (NSFW) content rules

Beattie can fetch adult material from third-party art platforms, imageboards, social networks, and archives.

The booru search commands (`gelbooru`, `rule34`, and `e621`) check that the channel has Discord's native age-restricted (NSFW) setting enabled before returning results.

Automatic link crossposting (`crosspost auto`) and manual link commands (`post` and `chan`) process URLs in the channel where you run them. Users and server administrators are responsible for keeping adult links and adult crossposts inside age-restricted (NSFW) Discord channels. Server administrators can restrict where the bot posts by changing Discord channel permissions, disabling modules with `disable`, turning off automatic crossposting with `crosspost auto false`, or blocking specific sites with `crosspost blacklist`.

## Prohibited content and conduct

You may not use Beattie to fetch or post content that violates Discord's Community Guidelines or applicable law in the United States, the United Kingdom, the European Union, or your local jurisdiction. Prohibited uses include:

- Child Sexual Abuse Material (CSAM), Child Sexual Exploitation and Abuse (CSAE), or any content depicting minors that violates 18 U.S.C. § 2256, the UK Protection of Children Act 1978, or local law.
- Non-consensual intimate imagery (revenge porn) or private personal data (doxxing).
- Material that promotes terrorism, suicide, self-harm, or unlawful violence.
- Malware, phishing links, or denial-of-service payloads.
- Command spam, flooding third-party APIs, or abusing the bot's proxy connections.

We report illegal content and severe violations to Discord Trust & Safety and the relevant authorities, and we block offending users and servers.

## Copyright, artist opt-out, and takedowns

All media and text fetched by Beattie belong to their respective creators and source platforms. Beattie claims no ownership over crossposted material.

Beattie only caches downloaded media in volatile RAM (`queue_cache`) to avoid downloading the same URL twice. Discord uploads and hosts the media files shown in chat on its own CDN.

Users and moderators can delete crossposted content inside Discord at any time:
- The user who posted the original link can delete their message or react to the bot's reply with `❌`, which deletes the bot's message from Discord.
- Server moderators with the `manage_messages` permission can delete the bot's reply directly or react to it with `❌`.
- Server administrators can clear cached entries with `crosspost evict` or block a site on their server with `crosspost blacklist`.

If you are a copyright owner or creator and want your work evicted from the bot's cache, want a crossposted message removed, or want your domain blocked from being crossposted, join https://discord.gg/zG849bNYqU and contact the bot owner. If the Discord invite has expired, please create a Github issue and be careful not to include any personal information, as Github issues are public.

## Disclaimers, liability, and termination

Beattie is provided "as is" and "as available" without warranties of any kind. The bot operator does not guarantee uninterrupted uptime, error-free operation, or the delivery of scheduled reminders (`remind`). Do not rely on the reminder system for medical, safety, legal, or financial deadlines.

The bot operator may block any user or server, clear cached data, change features, or shut down the bot at any time without notice.

To the fullest extent permitted by law, the bot operator and contributors are not liable for any damages resulting from your use of the bot, your interactions with proxied third-party services, or third-party content fetched through the bot.

If your use of the bot violates these terms, infringes third-party rights, or breaks applicable law, you agree to indemnify and hold harmless the bot operator from any resulting claims, liabilities, or legal expenses.