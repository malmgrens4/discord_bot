import asyncio
import configparser
import logging
import discord
from art import *
import shutil
from random import random
from google_images_download import google_images_download
from PIL import Image, ImageFont, ImageDraw

from discord.ext import commands


config = configparser.ConfigParser()
config.read('config.ini')

log = logging.getLogger()

class Meme(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def img(self, ctx, keyword: str, offset: int = None):
        """Google image results based off of entered word. CS for multiple."""
        response = google_images_download.googleimagesdownload()  # class instantiation
        if not offset :
            offset = int(100 * random()) + 1
        offset = abs(offset)
        offset = min(offset, 100)

        arguments = {"keywords": keyword, "limit": offset, "output_directory": "./google_downloads",
                     "image_directory": "images", "offset": offset, "silent_mode": True}  # creating list of arguments
        try:
            paths = response.download(arguments)  # passing the arguments to the function
            await self.send_google_imgs(ctx, paths)

        except Exception as err:
            log.error(err)
        finally:
            shutil.rmtree('./google_downloads/images')


    @commands.command()
    async def meme(self, ctx, keyword: str, top_line: str, btm_line: str, offset:int = None):
        """Generate a meme with a google image results by entering a keyword then the top and bottom lines."""

        font = ImageFont.truetype("./fonts/Roboto-Black.ttf", 12)
        response = google_images_download.googleimagesdownload()  # class instantiation
        if not offset:
            offset = int(100 * random()) + 1
        offset = abs(offset)
        offset = min(offset, 100)

        arguments = {"keywords": keyword, "limit": offset, "output_directory": "./google_downloads",
                     "image_directory": "images", "offset": offset, "silent_mode": True}  # creating list of arguments
        try:
            paths = response.download(arguments)  # passing the arguments to the function
            for path in paths:
                try:
                    for key, value in path.items():
                        for file_path in value:
                            img_fraction = .65
                            font_size = 12
                            cur_img = Image.open(file_path)
                            width, height = cur_img.size
                            draw = ImageDraw.Draw(cur_img)

                            while font.getsize(top_line)[0] <= img_fraction * width:
                                font_size += 1
                                font = ImageFont.truetype("./fonts/Roboto-Black.ttf", font_size)

                            font_size -= 1
                            font = ImageFont.truetype("./fonts/Roboto-Black.ttf", font_size)
                            text_width, text_height = font.getsize(top_line)
                            text_x = ((width - text_width) / 2)
                            draw.text((text_x + 1, 1), top_line, (0, 0, 0), font=font)
                            draw.text((text_x - 1, 1), top_line, (0, 0, 0), font=font)
                            draw.text((text_x, 1), top_line, (255, 255, 255), font=font)

                            font_size = 1
                            font = ImageFont.truetype("./fonts/Roboto-Black.ttf", font_size)
                            while font.getsize(btm_line)[0] <= img_fraction * width:
                                font_size += 1
                                font = ImageFont.truetype("./fonts/Roboto-Black.ttf", font_size)

                            font_size -= 1
                            font = ImageFont.truetype("./fonts/Roboto-Black.ttf", font_size)
                            text_width, text_height = font.getsize(btm_line)
                            text_x = ((width - text_width) / 2)

                            draw.text((text_x + 1, height - text_height - 1), btm_line, (0, 0, 0), font=font)
                            draw.text((text_x - 1, height - text_height - 1), btm_line, (0, 0, 0), font=font)
                            draw.text((text_x, height - text_height - 1), btm_line, (255, 255, 255), font=font)
                            cur_img.save(file_path)
                except Exception as err:
                    log.error(err)
            await self.send_google_imgs(ctx, paths)
        except Exception as err:
            log.error(err)
        finally:
            shutil.rmtree('./google_downloads/images')


    async def send_google_imgs(self, ctx, paths):
        for path in paths:
            for key, value in path.items():
                for file_path in value:
                    file = discord.File(file_path, filename=str(key) + '.png')
                    await ctx.send("", files=[file])



    @commands.command()
    async def ascii(self, ctx, word: str):
        """Display ASCII art of the entered word."""
        display_text = '```' + text2art(text=word, font="random", chr_ignore=True) + '```'
        await ctx.send(display_text)


    @commands.command()
    async def ascii_art(self, ctx, word: str = None):
        """Display ASCII art based off of the entered word."""
        if not word:
            word = "rand"
        display_text = '```' + art(word) + '```'
        await ctx.send(display_text)


def setup(bot):
    bot.add_cog(Meme(bot))