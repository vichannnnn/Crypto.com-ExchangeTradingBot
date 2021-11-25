from discord.ext import commands, tasks
import cryptocom.exchange as cro
import discord
import xlsxwriter
import yaml
import sqlite3
import math

conn = sqlite3.connect('bot.db', timeout=5.0)
c = conn.cursor()
conn.row_factory = sqlite3.Row

c.execute(
    '''CREATE TABLE IF NOT EXISTS trades (
       `tradeID` INT PRIMARY KEY, 
       `type` TEXT,
       `pair` TEXT,
       `qty` FLOAT,
       `costBasis` FLOAT,
       `totalPrice` FLOAT
       ) ''')

c.execute(
    '''CREATE TABLE IF NOT EXISTS orders (
       `orderID` INT PRIMARY KEY, 
       `type` TEXT,
       `pair` TEXT,
       `qty` FLOAT,
       `costBasis` FLOAT,
       `totalPrice` FLOAT
       ) ''')

c.execute('''CREATE TABLE IF NOT EXISTS sold (
             `orderID` INT PRIMARY KEY, 
             `type` TEXT,
             `pair` TEXT,
             `qty` FLOAT,
             `buyCostBasis` FLOAT,
             `sellCostBasis` FLOAT
             `totalPrice` FLOAT,
             `profitLoss` FLOAT
             ) ''')

with open("authentication.yml", "r", encoding="utf8") as stream:
    yaml_data = yaml.safe_load(stream)

API_KEY = yaml_data["API_KEY"]
SECRET_KEY = yaml_data["SECRET_KEY"]


async def updateTrade():
    account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
    data = await account.get_trades()

    for order in data:
        try:
            total_cost = order.filled_price * order.filled_quantity
            c.execute('INSERT INTO trades VALUES (?, ?, ?, ?, ?, ?) ',
                      (order.order_id, order.side, order.pair.exchange_name,
                       order.filled_quantity, order.filled_price, total_cost))
            conn.commit()
        except sqlite3.IntegrityError:
            continue


class Menu(discord.ui.View):
    def __init__(self, ctx, data):
        super().__init__()
        self.timeout = 60
        self.value = 1
        self.ctx = ctx
        self.data = data
        self.pages = math.ceil(len(self.data) / 15)

    async def interaction_check(self, interaction):
        self.message = interaction.message
        return interaction.user.id == self.ctx.author.id

    @discord.ui.button(label="Previous Page", emoji="⏪")
    async def left(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value -= 1
        if self.value <= 0 or self.value > self.pages:
            embed = discord.Embed(title="Profit & Loss", description=f"You have reached the end of the pages.")
            if self.ctx.guild.icon:
                embed.set_thumbnail(url=self.ctx.guild.icon.url)
            else:
                pass
            embed.set_footer(text=f"Press '⏩' to go back.", icon_url=self.ctx.author.avatar.url)

            if self.value < 0:
                self.value += 1
            await self.message.edit(embed=embed)

        else:
            everyPage = [item for item in self.data[15 * (self.value - 1):self.value * 15]]

            description = '```\n'
            description += "Ticker   | Quantity | $ Sold | Real PnL\n"
            for id, type, name, qty, cost_basis, sell_price, profit in everyPage:
                percentage = (profit - 1) * 100
                pnl = sell_price * qty - cost_basis * qty
                description += f"{name}{(10 - len(name)) * ' '}" \
                               f"{round(qty, 3)}{(11 - (len(str(round(qty, 3))))) * ' '}" \
                               f"${round(sell_price, 3)}{(9 - len(str(round(sell_price, 3)))) * ' '}" \
                               f"${round(pnl, 2)} ({round(percentage, 2)}%)\n"

            description += '\n```'

            embed = discord.Embed(title="Profit & Loss", description=description)
            if self.ctx.guild.icon:
                embed.set_thumbnail(url=self.ctx.guild.icon.url)
            else:
                pass
            embed.set_footer(text=f"Page {self.value} of {self.pages}", icon_url=self.ctx.author.avatar.url)
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Next Page", emoji="⏩")
    async def right(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value += 1

        if self.value > self.pages:
            embed = discord.Embed(title="Profit & Loss", description=f"You have reached the end of the pages.")
            if self.ctx.guild.icon:
                embed.set_thumbnail(url=self.ctx.guild.icon.url)
            else:
                pass
            embed.set_footer(text=f"Press '⏩' to go back.", icon_url=self.ctx.author.avatar.url)

            if self.value > self.pages + 1:
                self.value -= 1
            await self.message.edit(embed=embed)

        else:
            everyPage = [item for item in self.data[15 * (self.value - 1):self.value * 15]]

            description = '```\n'
            description += "Ticker   | Quantity | $ Sold | Real PnL\n"
            for id, type, name, qty, cost_basis, sell_price, profit in everyPage:
                percentage = (profit - 1) * 100
                pnl = sell_price * qty - cost_basis * qty
                description += f"{name}{(10 - len(name)) * ' '}" \
                               f"{round(qty, 3)}{(11 - (len(str(round(qty, 3))))) * ' '}" \
                               f"${round(sell_price, 3)}{(9 - len(str(round(sell_price, 3)))) * ' '}" \
                               f"${round(pnl, 2)} ({round(percentage, 2)}%)\n"

            description += '\n```'

            embed = discord.Embed(title="Profit & Loss", description=description)
            if self.ctx.guild.icon:
                embed.set_thumbnail(url=self.ctx.guild.icon.url)
            else:
                pass
            embed.set_footer(text=f"Page {self.value} of {self.pages}", icon_url=self.ctx.author.avatar.url)
            await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.red, emoji="<:cross:907833612471242852>")
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.clear_items()
        self.add_item(item=discord.ui.Button(emoji="<:cross:907833612471242852>", label="Command Closed",
                                             style=discord.ButtonStyle.red, disabled=True))
        await self.message.edit(view=self)
        await interaction.response.send_message("Shop closed successfully. Interface will close in 5 seconds.",
                                                ephemeral=True)
        self.stop()

    async def on_timeout(self) -> None:
        self.clear_items()
        self.add_item(item=discord.ui.Button(emoji="<:cross:907833612471242852>", label="Command Closed",
                                             style=discord.ButtonStyle.red, disabled=True))
        await self.message.edit(view=self)
        self.stop()


class TradeCommands(commands.Cog, name="🛠️ Trade Commands"):
    def __init__(self, bot):
        self.bot = bot
        self.historyUpdate.start()

    @tasks.loop(seconds=3600)
    async def historyUpdate(self):
        await updateTrade()

    @historyUpdate.before_loop
    async def before_status(self):
        print('Waiting to update orders...')
        await self.bot.wait_until_ready()

    @commands.command(brief="Shows your balance.", description=f"balance**\n\nShows your balance.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def balance(self, ctx):
        exchange = cro.Exchange()
        pairs = await exchange.get_pairs()
        account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
        balance = await account.get_balance()

        balances = []
        for coin in balance:
            if balance[coin].total:
                if str(coin.exchange_name) != "USDT":
                    pairObject = [n for n in pairs if n.exchange_name == f"{coin.exchange_name}_USDT"][0]
                    current_price = await exchange.get_price(pairObject)
                else:
                    current_price = 1
                balances.append([balance[coin], coin, current_price])

        description = '```\n'
        description += "Ticker   | Quantity | $ Price | $ Total Value | Staking \n"
        for ticker, coin, current_price in balances:
            name = ticker.coin.exchange_name
            qty = ticker.total
            stake = ticker.in_stake
            description += f"{str(name)}{(10 - len(str(name))) * ' '}" \
                           f"{round(qty, 3)}{(11 - (len(str(round(qty, 3))))) * ' '}" \
                           f"${round(current_price, 3)}{(10 - (len(str(round(current_price, 3)))) - 1) * ' '}" \
                           f"${round((current_price * qty), 3)}{(16 - (len(str(round((current_price * qty), 3)))) - 1) * ' '}" \
                           f"{round(stake, 3)}{(16 - (len(str(round((current_price * qty), 3))))) * ' '}"


        description += '\n```'
        embed = discord.Embed(title="Coin Balance", description=description)
        await ctx.send(embed=embed)




    @commands.command(brief="Opens your portfolio.", description=f"portfolio**\n\nOpens your portfolio.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def portfolio(self, ctx):

        await updateTrade()

        row = 0
        col = 0

        workbook = xlsxwriter.Workbook('portfolio.xlsx')
        worksheet = workbook.add_worksheet()
        worksheet.write(row, col, "Order ID")
        worksheet.write(row, col + 1, "Type")
        worksheet.write(row, col + 2, "Pair")
        worksheet.write(row, col + 3, "Quantity")
        worksheet.write(row, col + 4, "Cost Basis")
        worksheet.write(row, col + 5, "Total Price")

        shares_price_list = []
        sold_list = []
        allTrades = [i for i in c.execute('SELECT * FROM trades')]

        for tradeID, type, pair, qty, costBasis, totalPrice in allTrades:
            worksheet.write(row + 1, col, tradeID)
            worksheet.write(row + 1, col + 1, type)
            worksheet.write(row + 1, col + 2, pair)
            worksheet.write(row + 1, col + 3, qty)
            worksheet.write(row + 1, col + 4, costBasis)
            worksheet.write(row + 1, col + 5, totalPrice)
            row += 1

            if type == "BUY":
                if shares_price_list:
                    ticker_list = [i[0] for i in shares_price_list]
                    if pair not in ticker_list:
                        shares_price_list.append([pair, qty, costBasis, totalPrice])

                    else:
                        idx = ticker_list.index(pair)
                        name, quantity, cost_basis, cost = shares_price_list[idx]
                        new_cost_basis = (costBasis * qty + cost_basis * quantity) / (qty + quantity)
                        quantity += qty
                        cost += totalPrice
                        shares_price_list[idx] = [name, quantity, new_cost_basis, cost]

                else:
                    shares_price_list.append([pair, qty, costBasis, totalPrice])

            else:
                if sold_list:
                    ticker_list = [i[0] for i in sold_list]
                    if pair not in ticker_list:
                        sold_list.append([pair, qty, totalPrice])

                    else:
                        idx = ticker_list.index(pair)
                        name, quantity, cost = sold_list[idx]
                        quantity += qty
                        cost += totalPrice
                        sold_list[idx] = [name, quantity, cost]

                else:
                    sold_list.append([pair, qty, totalPrice])

        for n, elements in enumerate(shares_price_list):
            pair, qty, cost_basis, totalPrice = elements
            ticker_list = [i[0] for i in sold_list]
            try:
                idx = ticker_list.index(pair)
                sold_pair, sold_qty, sold_total_price = sold_list[idx]
                qty -= sold_qty
                totalPrice -= sold_total_price
                shares_price_list[n] = [pair, qty, cost_basis, totalPrice]
            except ValueError:
                continue

        exchange = cro.Exchange()

        row += 3
        worksheet.write(row, col, "Pair")
        worksheet.write(row, col + 1, "Cost Basis")
        worksheet.write(row, col + 2, "Quantity")
        description = '```\n'
        description += "Ticker   | $ Cost | Quantity | Cost Basis | Unreal PnL\n"
        for name, qty, cost_basis, cost in shares_price_list:
            pairs = await exchange.get_pairs()
            pairObject = [n for n in pairs if n.exchange_name == name][0]
            current_price = await exchange.get_price(pairObject)
            pnl = qty * (current_price - cost_basis)
            percentage = (pnl / cost) * 100
            description += f"{name}{(10 - len(name)) * ' '}" \
                           f"${round(cost, 2)}{(8 - (len(str(round(cost, 2)))) + 1) * ' '}" \
                           f"{round(qty, 2)}{(11 - len(str(round(qty, 2)))) * ' '}" \
                           f"${round(cost_basis, 3)}{(10 - len(str(round(cost_basis, 3))) + 1) * ' '}" \
                           f"${round(pnl, 2)} ({round(percentage, 2)}%)\n"

            worksheet.write(row + 1, col, name)
            worksheet.write(row + 1, col + 1, cost / qty)
            worksheet.write(row + 1, col + 2, qty)
            row += 1
        workbook.close()
        description += '\n```'

        embed = discord.Embed(title="Portfolio", description=description)
        await ctx.send(embed=embed)


    @commands.command(brief="Starts a market buy order.",
                      description=f"marketbuy [Symbol] [Total Price]**\n\nStarts a market buy order.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def marketbuy(self, ctx, symbol, total_price: float):

        exchange = cro.Exchange()
        a = await exchange.get_pairs()
        pairObject = [n for n in a if n.exchange_name == symbol][0]
        current_price = await exchange.get_price(pairObject)

        qty = total_price / current_price

        account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
        order_id = await account.buy_market(pair=pairObject, spend=total_price, wait_for_fill=False)

        description = "Successfully placed a buy order.\n\n"
        description += f"> Order ID: **{order_id}**\n"
        description += f"> Symbol: **{symbol}**\n"
        description += f"> Price: **${current_price}**\n"
        description += f"> Quantity: **{qty}**\n"
        description += f"> Total Price: **${total_price}**\n\n"
        description += f"Current Price of {symbol}: **${current_price}**"

        c.execute('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?) ', (order_id, 'BUY', symbol, qty, current_price, total_price))
        conn.commit()
        embed = discord.Embed(title="Market Buy Order Placed", description=description)
        await ctx.send(embed=embed)


    @commands.command(brief="Starts a buy order.",
                      description=f"buy [Symbol] [Price] [Quantity]**\n\nStarts a buy order.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def buy(self, ctx, symbol, price: float, qty: float):

        exchange = cro.Exchange()
        a = await exchange.get_pairs()
        pairObject = [n for n in a if n.exchange_name == symbol][0]
        current_price = await exchange.get_price(pairObject)

        account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
        order_id = await account.buy_limit(pair=pairObject, quantity=qty, price=price)

        description = "Successfully placed a buy order.\n\n"
        description += f"> Order ID: **{order_id}**\n"
        description += f"> Symbol: **{symbol}**\n"
        description += f"> Price: **${price}**\n"
        description += f"> Quantity: **{qty}**\n"
        description += f"> Total Price: **${price * qty}**\n\n"
        description += f"Current Price of {symbol}: **${current_price}**"

        c.execute('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?) ', (order_id, 'BUY', symbol, qty, price, price * qty))
        conn.commit()
        embed = discord.Embed(title="Buy Order Placed", description=description)
        await ctx.send(embed=embed)


    @commands.command(brief="Starts a sell order.",
                      description=f"sell [Symbol] [Price] [Quantity]**\n\nStarts a sell order.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def sell(self, ctx, symbol, price: float, qty: float):

        exchange = cro.Exchange()
        a = await exchange.get_pairs()
        pairObject = [n for n in a if n.exchange_name == symbol][0]
        current_price = await exchange.get_price(pairObject)

        account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
        order_id = await account.sell_limit(pair=pairObject, quantity=qty, price=price)

        description = "Successfully placed a sell order.\n\n"
        description += f"> Order ID: {order_id}\n"
        description += f"> Symbol: {symbol}\n"
        description += f"> Price: ${price}\n"
        description += f"> Quantity: {qty}\n"
        description += f"> Total Price: ${price * qty}\n\n"
        description += f"> Current Price of {symbol}: ${current_price}"

        sum_qty, total_price = [i for i in c.execute(
            'SELECT SUM(qty), SUM(qty * costBasis) FROM trades WHERE type = ? AND pair = ? ',
            ('BUY', symbol))][0]
        cost_basis = total_price / sum_qty
        profit = cost_basis / current_price

        c.execute('INSERT INTO sold VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (order_id, 'SELL', symbol, qty, cost_basis, current_price,
                   price * qty, profit))
        conn.commit()
        c.execute('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?) ', (order_id, 'SELL', symbol, qty, price, price * qty))
        conn.commit()
        embed = discord.Embed(title="Sell Order Placed", description=description)
        await ctx.send(embed=embed)

    @commands.command(brief="Starts a market sell order.",
                      description=f"marketsell [Symbol] [Quantity]**\n\nStarts a market sell order.")
    @commands.is_owner()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def marketsell(self, ctx, symbol, total_price: float):

        exchange = cro.Exchange()
        a = await exchange.get_pairs()
        pairObject = [n for n in a if n.exchange_name == symbol][0]
        current_price = await exchange.get_price(pairObject)

        qty = total_price / current_price

        account = cro.Account(api_key=API_KEY, api_secret=SECRET_KEY)
        order_id = await account.sell_market(pair=pairObject, quantity=qty,  wait_for_fill=False)

        description = "Successfully placed a sell order.\n\n"
        description += f"> Order ID: {order_id}\n"
        description += f"> Symbol: {symbol}\n"
        description += f"> Price: ${current_price}\n"
        description += f"> Quantity: {qty}\n"
        description += f"> Total Price: ${total_price}\n\n"
        description += f"> Current Price of {symbol}: ${current_price}"

        sum_qty, total_price = [i for i in c.execute(
            'SELECT SUM(qty), SUM(qty * costBasis) FROM trades WHERE type = ? AND pair = ? ',
            ('BUY', symbol))][0]
        cost_basis = total_price / sum_qty
        profit = cost_basis / current_price

        c.execute('INSERT INTO sold VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (order_id, 'SELL', symbol, qty, cost_basis, current_price,
                   current_price * qty, profit))
        conn.commit()
        c.execute('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?) ', (order_id, 'SELL', symbol, qty, current_price, total_price))
        conn.commit()
        embed = discord.Embed(title="Market Sell Order Placed", description=description)
        await ctx.send(embed=embed)

    @commands.command(brief="Checks for a coin's price.", description=f"price**\n\nChecks for a pair price.")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def price(self, ctx, ticker):
        exchange = cro.Exchange()
        a = await exchange.get_pairs()
        pairObject = [n for n in a if n.exchange_name == ticker][0]
        exchange = cro.Exchange()
        price = await exchange.get_price(pairObject)
        await ctx.send(f"{ticker}'s Price is currently **${price}**")


def setup(bot):
    bot.add_cog(TradeCommands(bot))
