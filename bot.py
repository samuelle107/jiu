import asyncio
import datetime
import discord
import os
import logging
import mysql.connector
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv
from subreddit_scrapper import get_scraped_submissions
from db_helper import get_all, get_all_conditional, insert, remove, does_exist

logging.getLogger().setLevel(logging.INFO)

load_dotenv()

intents = discord.Intents.default()
intents.members = True

# Secret variable. Do not push to github
# Either ask me for the token or make your own bot
# this will go in .env
# DISCORD_BOT_TOKEN=xxxx
DISCORD_BOT_TOKEN = os.environ['DISCORD_BOT_TOKEN']
# These values are found by right clicking on the channel and then clicking copy ID
BOT_TESTING_CHANNEL_ID = 809303956667891752
MECH_MARKET_CHANNEL_ID = 829538527133171732

con_info = dict(
    user=os.getenv("MYSQL_USERNAME"),
    password=os.getenv("MYSQL_PASSWORD"),
    host=os.getenv("MYSQL_HOST"),
    database=os.getenv("MYSQL_DB"),
    charset="utf8",
    use_unicode=True
)

client = commands.Bot(command_prefix='!', intents=intents)

def query_keywords() -> list:
    con = mysql.connector.connect(**con_info)
    results = get_all(con, "keywords")
    con.close()
    return list(result[0] for result in results)


def query_users_by_keywords(keyword: str) -> list:
    con = mysql.connector.connect(**con_info)
    results = get_all_conditional(con, "keywords_users", ["keyword_id"], [keyword])
    con.close()
    return list(result[1] for result in results)


def query_forbidden_words_by_user_id(user_id: int) -> list:
    con = mysql.connector.connect(**con_info)
    results = get_all_conditional(con, "forbidden_words_users", ["user_id"], [user_id])
    con.close()
    return list(result[1] for result in results)

def get_url_at(index: int, text: str) -> str:
    try:
        urls = re.findall('https?://[^\s<>"]+|www\.[^\s<>"]+', text)
        return urls[index]
    except Exception as e:
        print(e)
        return ""

@client.event
async def on_ready():
    bot_testing_channel = client.get_channel(BOT_TESTING_CHANNEL_ID)
    mechmarket_channel = client.get_channel(MECH_MARKET_CHANNEL_ID)

    subreddits = ["MechMarket", "MechGroupBuys", "MechanicalKeyboards"]
    announcement_keywords = ["[gb]", "[ic]", "[IN STOCK]", "[PRE-ORDER]", "Novelkeys Updates"]

    logging.info(f'{str(datetime.datetime.now())}: Bot is ready')
    await bot_testing_channel.send("The charasmatic leader, JiU bot, is ready!! uWu")

    while True:
        con = mysql.connector.connect(**con_info)

        keywords = query_keywords()

        logging.info(f'{str(datetime.datetime.now())}: Checking for new submissions: ')
        submissions = get_scraped_submissions("+".join(subreddits))

        for submission in submissions:
            post_does_exist = does_exist(con, "mechmarket_posts", ["post_id"], [submission.id])

            if not post_does_exist:
                logging.info(f'{str(datetime.datetime.now())}: Found new submission: {submission.title[:20]}')
                insert(con, "mechmarket_posts", ["post_id", "title"], [submission.id, submission.title[:100]])

                if submission.subreddit == "MechMarket":
                    matching_keywords = list(filter(lambda keyword: keyword.lower() in submission.title.lower(), keywords))
                    mentions = set()

                    for matching_keyword in matching_keywords:
                        users = query_users_by_keywords(matching_keyword)

                        for uid in users:
                            forbidden_words = query_forbidden_words_by_user_id(uid)

                            if not any(forbidden_word.lower() in submission.title.lower() for forbidden_word in forbidden_words):
                                try:
                                    mentions.add(client.get_user(uid).mention)
                                except Exception as e:
                                    logging.info(f'{str(datetime.datetime.now())}: {e}')
                    
                    embed = discord.Embed()
                    embed.title = submission.title[:200]
                    embed.url = f"https://redd.it/{submission.id}"
                    image_url = get_url_at(0, submission.selftext_html)

                    if mentions:
                        await mechmarket_channel.send(f'{", ".join(list(set(mentions)))}')

                    await mechmarket_channel.send(embed=embed)

                    if image_url:
                        await mechmarket_channel.send(image_url)

        logging.info(f'{str(datetime.datetime.now())}: Finished scraping')
        con.close()
        await asyncio.sleep(90)


# Called when a new member joins
# Will add them to a refugee role, send a gif, and message
@client.event
async def on_member_join(member):
    try:
        con = mysql.connector.connect(**con_info)
        insert(con, "users", ["user_id"], [member.id])
        con.close()

    except Exception as e:
        logging.info(f'{str(datetime.datetime.now())}: Added {member}: ')

@client.command()
async def gugl(ctx, *args):
    base_url = "https://www.google.com/search?"
    query = f"q={'+'.join(args)}"
    await ctx.send(base_url + query)                                                                                                                                     

@client.command(aliases=["ak"])
async def add_keyword(ctx, *arg):
    keyword = " ".join(arg)

    con = mysql.connector.connect(**con_info)
    insert(con, "keywords", ["keyword_id"], [keyword])
    insert(con, "users", ["user_id"], [ctx.message.author.id])
    existance = does_exist(con, "keywords_users", ["user_id", "keyword_id"], [ctx.message.author.id, keyword])

    if not existance:
        keywords_users_id = insert(con, "keywords_users", ["user_id", "keyword_id"], [ctx.message.author.id, keyword])

        if keywords_users_id != -1:
            await ctx.send(f"Hewwo! I added **{keyword}** to your Keywords!")
        else:
            await ctx.send(f"Oh nyo! I couldn't add **{keyword}** to your Keywords.")
    else:
        await ctx.send(f"Baka! **{keyword}** is already in your Keywords.")

    con.close()


@client.command(aliases=["rk"])
async def remove_keyword(ctx, *arg):
    keyword = " ".join(arg)

    con = mysql.connector.connect(**con_info)
    num_removed = remove(con, "keywords_users", ["user_id", "keyword_id"], [ctx.message.author.id, keyword])
    con.close()

    if num_removed != 0:
        await ctx.send(f"Done! I removed **{keyword}** from your Keywords.")
    else:
        await ctx.send(f"Oh Nyo! I couldn't find **{keyword}**....")


@client.command(aliases=["gk"])
async def get_keywords(ctx):
    con = mysql.connector.connect(**con_info)
    results = get_all_conditional(con, "keywords_users", ['user_id'], [ctx.message.author.id])
    con.close()

    await ctx.send(f"Hewwo! Your keywords are **{', '.join(list(result[2] for result in results))}**.")


@client.command(aliases=["afw"])
async def add_forbidden_word(ctx, *arg):
    forbidden_word = " ".join(arg)

    con = mysql.connector.connect(**con_info)
    insert(con, "forbidden_words", ["forbidden_word_id"], [forbidden_word])
    insert(con, "users", ["user_id"], [ctx.message.author.id])
    existance = does_exist(con, "forbidden_words_users", ["forbidden_word_id", "user_id"], [forbidden_word, ctx.message.author.id])

    if not existance:
        forbidden_words_users_id = insert(con, "forbidden_words_users", ["forbidden_word_id", "user_id"], [forbidden_word, ctx.message.author.id])

        if forbidden_words_users_id != -1:
            await ctx.send(f"Hewwo! I added **{forbidden_word}** to your Forbidden Words!")
        else:
            await ctx.send(f"Oh nyo! I couldn't add **{forbidden_word}** to your Forbidden Words")
    else:
        await ctx.send(f"Baka! **{forbidden_word}** is already in your Forbidden Words!")

    con.close()


@client.command(aliases=["rfw"])
async def remove_forbidden_word(ctx, *arg):
    forbidden_word = " ".join(arg)

    con = mysql.connector.connect(**con_info)
    num_removed = remove(con, "forbidden_words_users", ["user_id", "forbidden_word_id"], [ctx.message.author.id, forbidden_word])
    con.close()

    if num_removed != 0:
        await ctx.send(f"Done! I removed **{forbidden_word}** from your Forbidden Words.")
    else:
        await ctx.send(f"Oh Nyo! I couldn't find **{forbidden_word}**....")


@client.command(aliases=["gfw"])
async def get_forbidden_words(ctx):
    con = mysql.connector.connect(**con_info)
    results = get_all_conditional(con, "forbidden_words_users", ['user_id'], [ctx.message.author.id])
    con.close()

    await ctx.send(f"Hewwo! Your keywords are **{', '.join(list(result[1] for result in results))}**.")

client.run(DISCORD_BOT_TOKEN)
