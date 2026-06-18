from __future__ import annotations

import asyncio
import io
import re
import toml
from typing import TYPE_CHECKING

import discord
from discord import Embed
from discord.ext import commands
from discord.ext.commands import Cog
from lxml import html

if TYPE_CHECKING:
    from beattie.bot import BeattieBot
    from beattie.context import BContext


# Ordered by priority
ARCHIVES: list[tuple[str, frozenset[str]]] = [
    (
        "desuarchive.org",
        frozenset({
            "a", "aco", "an", "c", "cgl", "co", "d", "fit", "g", "gif",
            "his", "int", "k", "m", "mlp", "mu", "q", "qa", "r9k", "tg",
            "trash", "vr", "wsg",
        }),
    ),
    (
        "boards.fireden.net",
        frozenset({
            "cm", "co", "sci", "v", "y"
        }),
    ),
    (
        "arch.b4k.dev",
        frozenset({
            "g", "mlp", "qb", "v", "vg", "vm", "vmg", "vp", "vrpg", "vst"
        }),
    ),
    (
        "archive.palanq.win",
        frozenset({
            "bant", "c", "con", "e", "i", "n", "news", "out", "p", "pw", "qst",
            "toy", "vip", "vp", "vt", "w", "wg", "wsr"
        }),
    ),
    (
        "archive.4plebs.org",
        frozenset({
            "adv", "f", "hr", "o", "pol", "s4s", "sp", "tg", "trv", "tv", "x"
        }),
    ),
    (
        "archiveofsins.com",
        frozenset({
            "aco", "d", "e", "h", "hc", "hm", "hr", "s", "t", "u"
        }),
    ),
    (
        "archived.moe",
        frozenset({
            "3", "a", "aco", "adv", "an", "asp", "b", "bant", "biz", "c",
            "can", "cgl", "ck", "cm", "co", "cock", "con", "d", "diy", "e",
            "f", "fa", "fap", "fit", "fitlit", "g", "gd", "gif", "h", "hc",
            "his", "hm", "hr", "i", "ic", "int", "jp", "k", "lgbt", "lit",
            "m", "mlp", "mlpol", "mo", "mtv", "mu", "n", "news", "o", "out",
            "outsoc", "p", "po", "pol", "pw", "q", "qa", "qb", "qst", "r",
            "r9k", "s", "s4s", "sci", "soc", "sp", "spa", "t", "tg", "toy",
            "trash", "trv", "tv", "u", "v", "vg", "vint", "vip", "vmg",
            "vp", "vr", "vrpg", "vt", "w", "wg", "wsg", "wsr", "x", "xs",
            "y",
        }),
    ),
]

ALL_ARCHIVED_BOARDS: frozenset[str] = frozenset(
    board for _, boards in ARCHIVES for board in boards
)

# reduce the chance of Cloudflare blocks
ARCHIVE_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MAX_FIELD_LEN = 1024
MAX_FOOTER_LEN = 2048


def get_archives(board: str) -> list[str]:
    """Returns a priority-ordered list of all archives that support the given board."""
    return [host for host, boards in ARCHIVES if board in boards]


def _text_from_div(div: html.HtmlElement) -> str:
    for br in div.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    return (div.text_content() or "").strip()


def _4chan_comment_to_text(comment: str) -> str:
    """Safely extract plain text from 4chan's raw HTML `com` field."""
    fragment = html.fragment_fromstring(f"<div>{comment}</div>")
    for br in fragment.xpath(".//br"):
        br.tail = "\n" + (br.tail or "")
    for wbr in fragment.xpath(".//wbr"):
        wbr.drop_tag()
    return (fragment.text_content() or "").strip()


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------


class Chan(Cog):
    """Fetch and display 4chan posts via archive sites."""

    def __init__(self, bot: BeattieBot) -> None:
        self.bot = bot
        self.fs_solver_url = None
        self.fs_proxy_url = None
        
        # Track command invocation messages to their corresponding bot responses
        self.responses: dict[int, list[discord.Message]] = {}
        self.response_keys: list[int] = []
        
        # try:
        #     with open("config/crosspost/flaresolverr.toml", "r") as fp:
        #         fsconfig = toml.load(fp)
        #         self.fs_solver_url = fsconfig.get("solver")
        #         self.fs_proxy_url = fsconfig.get("proxy")
        # except (FileNotFoundError, KeyError):
        #     pass

    async def _tracked_reply(self, ctx: BContext, *args, **kwargs) -> discord.Message:
        """Sends a message and tracks it so it can be deleted if the invoking message is deleted."""
        msg = await ctx.send(*args, **kwargs)
        
        invoke_id = ctx.message.id
        if invoke_id not in self.responses:
            self.responses[invoke_id] = []
            self.response_keys.append(invoke_id)
            
            # Keep cache size manageable to prevent memory leaks over time
            if len(self.response_keys) > 500:
                old_id = self.response_keys.pop(0)
                self.responses.pop(old_id, None)
                
        self.responses[invoke_id].append(msg)
        return msg

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Automatically delete the bot's response if the original invoking message is deleted."""
        if responses := self.responses.pop(message.id, None):
            try:
                self.response_keys.remove(message.id)
            except ValueError:
                pass
                
            for response in responses:
                try:
                    await response.delete()
                except Exception:
                    pass

    def _extract_post_data(self, board: str, thread_id: str, post_data: dict) -> tuple[str, str, str, str]:
        """Helper to construct standard output from 4chan API JSON data."""
        text = ""
        if "com" in post_data:
            text = _4chan_comment_to_text(post_data["com"])
            
        image_url = ""
        ext = ""
        if "tim" in post_data:
            ext = post_data["ext"]
            image_url = f"https://i.4cdn.org/{board}/{post_data['tim']}{ext}"
            
        return text, image_url, ext, thread_id

    async def _download_file(self, ctx: BContext, url: str) -> discord.File | None:
        """Attempt to download the image/webm into memory to bypass hotlinking protections."""
        if url.startswith("//"):
            url = f"https:{url}"
            
        try:
            async with self.bot.get(url, headers={"User-Agent": ARCHIVE_UA}, error_for_status=False) as resp:
                status = getattr(resp, "status_code", getattr(resp, "status", None))
                if status == 200:
                    if hasattr(resp, "content") and not callable(resp.content):
                        file_bytes = resp.content
                    elif hasattr(resp, "read"):
                        file_bytes = await resp.read()
                    else:
                        return None
                        
                    file_size = len(file_bytes)
                    # Use guild limit if available, fallback to typical 25MB Discord limit
                    max_bytes = ctx.guild.filesize_limit if ctx.guild else 25 * 1024 * 1024
                    
                    if file_size <= max_bytes:
                        clean_url = url.split("?")[0]
                        filename = clean_url.split("/")[-1]
                        
                        # Fallback if no valid filename is extracted
                        if not filename or "." not in filename:
                            ext = "." + clean_url.rsplit(".", 1)[-1] if "." in clean_url else ".png"
                            filename = f"media{ext}"
                            
                        return discord.File(io.BytesIO(file_bytes), filename=filename)
        except Exception:
            pass
        return None

    async def _fetch_from_live_api_brute_force(self, board: str, post_number: str) -> tuple[str, str, str, str] | None:
        """
        Resolves a post ID against the live 4chan JSON API when archives fail.
        """
        catalog_url = f"https://a.4cdn.org/{board}/catalog.json"
        
        async with self.bot.get(catalog_url, error_for_status=False) as resp:
            if getattr(resp, "status_code", getattr(resp, "status", None)) != 200:
                return None
            
            catalog_data = resp.json()
            if asyncio.iscoroutine(catalog_data):
                catalog_data = await catalog_data
                
        thread_ids = []
        
        # Step 1: Fast check (OPs and last 3-5 replies)
        for page in catalog_data:
            for thread in page.get("threads", []):
                thread_id = str(thread["no"])
                thread_ids.append(thread_id)
                
                # Check if it's the OP
                if thread_id == post_number:
                    return self._extract_post_data(board, thread_id, thread)
                    
                # Check if it's in the recent replies
                for reply in thread.get("last_replies", []):
                    if str(reply["no"]) == post_number:
                        return self._extract_post_data(board, thread_id, reply)
                        
        # Step 2: Brute force fallback (Search every active thread one by one)
        for thread_id in thread_ids:
            # Prevent Server IP Ban
            await asyncio.sleep(1.0) 
            
            thread_url = f"https://a.4cdn.org/{board}/thread/{thread_id}.json"
            async with self.bot.get(thread_url, error_for_status=False) as resp:
                if getattr(resp, "status_code", getattr(resp, "status", None)) != 200:
                    continue
                
                thread_data = resp.json()
                if asyncio.iscoroutine(thread_data):
                    thread_data = await thread_data
                    
                for post in thread_data.get("posts", []):
                    if str(post["no"]) == post_number:
                        return self._extract_post_data(board, thread_id, post)
                        
        return None

    async def _fetch_from_live_html(self, board: str, post_number: str) -> tuple[str, str, str, str] | None:
        """Attempts to scrape live 4chan HTML directly (OP only)."""
        thread_url = f"https://boards.4chan.org/{board}/thread/{post_number}"
        async with self.bot.get(thread_url, headers={"User-Agent": ARCHIVE_UA}, error_for_status=False) as resp:
            if getattr(resp, "status_code", getattr(resp, "status", None)) != 200:
                return None
                
            if hasattr(resp, "content") and not callable(resp.content):
                content = resp.content
            elif hasattr(resp, "read"):
                content = await resp.read()

        root = html.document_fromstring(content)
        posts = root.xpath(f".//div[@id='p{post_number}']")
        
        if not posts:
            return None
            
        post_elem = posts[0]
        
        image_url = ""
        ext = ""
        file_links = post_elem.xpath(".//a[@class='fileThumb']/@href")
        if file_links:
            image_url = file_links[0]
            if image_url.startswith("//"):
                image_url = f"https:{image_url}"
            ext = "." + image_url.rsplit(".", 1)[-1] if "." in image_url else ""
            
        text = ""
        text_blocks = post_elem.xpath(".//blockquote[contains(@class, 'postMessage')]")
        if text_blocks:
            text = _text_from_div(text_blocks[0])
            
        return text, image_url, ext, post_number

    async def _fetch_from_archive(
        self,
        host: str,
        board: str,
        post_number: str,
    ) -> tuple[str, str, str, str] | None:
        """
        Returns (text, image_url, ext, thread_number) or None on failure.
        """
        CF_ARCHIVES = {"archived.moe", "archiveofsins.com", "archive.4plebs.org"}
        
        # use_flaresolverr = host in CF_ARCHIVES and self.fs_solver_url is not None

        # 1. Try to pull it from the live HTML site directly if it's protected
        if host in CF_ARCHIVES:
            live_result = await self._fetch_from_live_html(board, post_number)
            if live_result:
                return live_result

        redirect_url = f"https://{host}/{board}/post/{post_number}"
        content = None
        status = None
        thread_url = str(redirect_url)

        # 2. First HTTP Request (Redirect Endpoint)
        # if use_flaresolverr:
        #     payload = {
        #         "cmd": "request.get",
        #         "url": redirect_url,
        #         "maxTimeout": 15000 
        #     }
        #     if self.fs_proxy_url:
        #         payload["proxy"] = {"url": self.fs_proxy_url}
        #     
        #     try:
        #         resp = await self.bot.session.post(
        #             self.fs_solver_url,
        #             json=payload,
        #             timeout=16.0
        #         )
        #         data = resp.json()
        #         if data.get("status") == "ok":
        #             content = data["solution"]["response"].encode("utf-8")
        #             status = 200
        #             if "url" in data["solution"]:
        #                 thread_url = data["solution"]["url"]
        #     except Exception:
        #         pass

        if content is None:
            async with self.bot.get(
                redirect_url,
                headers={"User-Agent": ARCHIVE_UA},
                error_for_status=False,
            ) as resp:
                status = getattr(resp, "status_code", getattr(resp, "status", None))
                
                if hasattr(resp, "content") and not callable(resp.content):
                    content = resp.content
                elif hasattr(resp, "read"):
                    content = await resp.read()

                thread_url = str(getattr(resp, "url", redirect_url))
                
                if status in (301, 302, 303, 307, 308):
                    thread_url = resp.headers.get("Location", thread_url)
                    content = None

        if status in (403, 503):
            return "CLOUDFLARE_BLOCK", "", "", ""

        if status not in (200, 301, 302, 303, 307, 308):
            return None

        if content is not None:
            body_text = content.decode("utf-8", errors="replace")
            
            meta_match = re.search(r'url\s*=\s*[\'"]?([^\'">\s]+)', body_text, re.IGNORECASE)
            fallback_match = re.search(r'redirected to\s+(https?://[^\s<]+)', body_text, re.IGNORECASE)

            if meta_match and "/thread/" in meta_match.group(1):
                thread_url = meta_match.group(1).strip()
                content = None
            elif fallback_match and "/thread/" in fallback_match.group(1):
                thread_url = fallback_match.group(1).strip()
                content = None 

        if thread_url.startswith("//"):
            thread_url = f"https:{thread_url}"
        elif thread_url.startswith("/"):
            thread_url = f"https://{host}{thread_url}"

        m = re.search(r"/thread/(\d+)", thread_url)
        if m:
            thread_number = m.group(1)
        else:
            if content is not None:
                body_text = content.decode("utf-8", errors="ignore")
                canon_match = re.search(r'<link[^>]*rel=[\'"]canonical[\'"][^>]*href=[\'"]([^\'"]+)[\'"]', body_text, re.IGNORECASE)
                if canon_match:
                    thread_url = canon_match.group(1)
                    m = re.search(r"/thread/(\d+)", thread_url)
                    if m:
                        thread_number = m.group(1)
                    else:
                        return None
                else:
                    thread_match = re.search(r'/(?:thread|res)/(\d+)', body_text)
                    if thread_match:
                        thread_number = thread_match.group(1)
                    else:
                        return None
            else:
                return None
            
        # 3. Second HTTP Request (Actual Thread Page)
        if content is None:
            clean_thread_url = thread_url.split("#")[0]
            
            # if use_flaresolverr:
            #     payload = {
            #         "cmd": "request.get",
            #         "url": clean_thread_url,
            #         "maxTimeout": 15000
            #     }
            #     if self.fs_proxy_url:
            #         payload["proxy"] = {"url": self.fs_proxy_url}
            #     
            #     try:
            #         resp = await self.bot.session.post(
            #             self.fs_solver_url,
            #             json=payload,
            #             timeout=16.0
            #         )
            #         data = resp.json()
            #         if data.get("status") == "ok":
            #             content = data["solution"]["response"].encode("utf-8")
            #             status = 200
            #     except Exception:
            #         pass

            if content is None:
                async with self.bot.get(
                    clean_thread_url,
                    headers={"User-Agent": ARCHIVE_UA},
                    error_for_status=False,
                ) as resp:
                    status = getattr(resp, "status_code", getattr(resp, "status", None))
                    
                    if status in (403, 503):
                        return "CLOUDFLARE_BLOCK", "", "", ""
                    if status != 200:
                        return None
                        
                    if hasattr(resp, "content") and not callable(resp.content):
                        content = resp.content
                    elif hasattr(resp, "read"):
                        content = await resp.read()

        root = html.document_fromstring(content)

        articles = root.xpath(f".//article[@id='{post_number}']")
        if not articles:
            return None
            
        article = articles[0]

        image_url = ""
        ext = ""
        img_links = article.xpath(".//div[contains(@class,'thread_image_box')]//a")
        if img_links:
            href = img_links[0].get("href", "")
            if href:
                image_url = href.rstrip()
                if image_url.startswith("//"):
                    image_url = f"https:{image_url}"
                elif image_url.startswith("/"):
                    image_url = f"https://{host}{image_url}"
                    
                ext = "." + image_url.rsplit(".", 1)[-1] if "." in image_url else ""

        text = ""
        text_divs = article.xpath(".//div[contains(@class,'text')]")
        if text_divs:
            text = _text_from_div(text_divs[0])

        return text, image_url, ext, thread_number

    @commands.command()
    async def chan(self, ctx: BContext, board: str, post_number: str):
        """Fetch a 4chan post or thread OP from an archive.

        Usage: chan <board> <post/thread number>
        Example: chan trash 123456789
        """
        board = board.lower().lstrip("/").rstrip("/")

        if board not in ALL_ARCHIVED_BOARDS:
            all_boards = ", ".join(sorted(ALL_ARCHIVED_BOARDS))
            await self._tracked_reply(
                ctx,
                f"**/{board}/** is not covered by any supported archive.\n"
                f"Supported boards: {all_boards}"
            )
            return

        hosts = get_archives(board)
        result = None
        used_host = None
        cf_blocked = False
        found_live = False

        async with ctx.typing():
            # try every archive that supports this board
            for host in hosts:
                res = await self._fetch_from_archive(host, board, post_number)
                
                if res is None:
                    continue
                if res[0] == "CLOUDFLARE_BLOCK":
                    cf_blocked = True
                    continue
                    
                # We successfully found it
                result = res
                used_host = host
                break

            # If archive failed or Cloudflare blocked us
            if result is None:
                warning_msg = await self._tracked_reply(
                    ctx,
                    f"⚠️ Post not found in archive (or Cloudflare blocked the bot's request).\n"
                    f"Initiating scan of the live **/{board}/** board (this may take up to 2 minutes)..."
                )
                
                live_result = await self._fetch_from_live_api_brute_force(board, post_number)
                
                if live_result:
                    result = live_result
                    found_live = True
                    try:
                        await warning_msg.delete()
                    except Exception:
                        pass
                else:
                    # Update warning message with failure reason
                    if cf_blocked:
                        await warning_msg.edit(
                            content=f"❌ Could not retrieve post. All available archives are actively blocking the bot's request "
                                    f"with a Cloudflare security challenge, and the post is no longer on the live board."
                        )
                    else:
                        await warning_msg.edit(
                            content=f"Post **{post_number}** not found on any supported archive or the live board "
                                    f"(it may never have been archived or was deleted before capture)."
                        )
                    return

        text, image_url, ext, thread_number = result

        # Override URL generation if we successfully fetched it straight from 4chan
        if found_live:
            post_link = f"https://boards.4chan.org/{board}/thread/{thread_number}#p{post_number}"
        elif used_host == "desuarchive.org":
            post_link = f"https://desuarchive.org/{board}/thread/{thread_number}/#{post_number}"
        else:
            post_link = f"https://boards.4chan.org/{board}/thread/{thread_number}#p{post_number}"

        embed = Embed(colour=0x00b300)
        embed.add_field(
            name=f"/{board}/ — Thread: {thread_number}",
            value=f"[>>{post_number}]({post_link})",
            inline=False,
        )

        if text:
            if len(text) <= MAX_FIELD_LEN:
                embed.add_field(name="\u200b", value=text, inline=False)
            elif len(text) <= MAX_FOOTER_LEN:
                embed.set_footer(text=text)
            else:
                embed.add_field(
                    name="PostERROR",
                    value="Post exceeded character limit (2048)",
                    inline=False,
                )

        # Attempt to natively download and attach media
        discord_file = None
        if image_url:
            discord_file = await self._download_file(ctx, image_url)

        if discord_file:
            # Only set inside embed if it's an image. WebMs render cleanly directly above the embed.
            if ext.lower() != ".webm":
                embed.set_image(url=f"attachment://{discord_file.filename}")
            await self._tracked_reply(ctx, file=discord_file, embed=embed)
        else:
            # Silent fallback to hotlinking
            if ext.lower() == ".webm" and image_url:
                # Hotlinked WebMs require their own string content context to unroll native video player 
                await self._tracked_reply(ctx, content=image_url, embed=embed)
            elif image_url:
                embed.set_image(url=image_url)
                await self._tracked_reply(ctx, embed=embed)
            else:
                await self._tracked_reply(ctx, embed=embed)

    @chan.error
    async def chan_error(self, ctx: BContext, exc: Exception):
        if isinstance(exc, commands.MissingRequiredArgument):
            await self._tracked_reply(ctx, "Usage: `chan <board> <post number>`  e.g. `chan trash 123456789`")
        else:
            await ctx.bot.handle_error(ctx, exc)


async def setup(bot: BeattieBot) -> None:
    await bot.add_cog(Chan(bot))