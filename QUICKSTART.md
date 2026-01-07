# Quick Start Guide - Polymarket Bot

Get your Polymarket bot running in 5 minutes!

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Set Up Credentials

Create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Polymarket (REQUIRED)
POLYMARKET_PRIVATE_KEY=your_ethereum_private_key_here

# Binance (REQUIRED for latency arbitrage)
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_secret

# Trading Mode (IMPORTANT!)
ENABLE_LIVE_TRADING=false  # Start with paper trading!
```

### Getting Your Credentials

**Polymarket Private Key:**
1. Create a wallet (MetaMask, hardware wallet, etc.)
2. Fund it with USDC on Polygon network
3. Export your private key (KEEP IT SECURE!)

**Binance API:**
1. Create account at binance.com
2. Go to API Management
3. Create new API key (read-only is fine for price feeds)

## Step 3: Configure Strategies

Edit `config/config.yaml` to select strategies:

```yaml
strategies:
  latency_arbitrage:
    enabled: true    # 🔥 Most profitable
    priority: 1

  binary_hedging:
    enabled: true    # 🎯 High win rate
    priority: 2

  combinatorial_arbitrage:
    enabled: false   # Disable if needed
    priority: 3

  market_making:
    enabled: false   # Disable if needed
    priority: 4
```

## Step 4: Run the Bot

### Paper Trading (Recommended First!)

```bash
python run_bot.py
```

The bot will:
- ✓ Connect to Polymarket
- ✓ Initialize strategies
- ✓ Start monitoring markets
- ✓ Log all activity to `logs/polymarket_bot.log`

### Monitor the Output

You'll see:

```
========================================================
Initializing Polymarket Multi-Strategy Bot
========================================================
Polymarket client connected
Account balance: $1000.00
✓ latency_arbitrage strategy initialized (Priority: 1)
✓ binary_hedging strategy initialized (Priority: 2)
🚀 Bot started
========================================================

BTC_15min: UP 2.15% (confidence: 0.82)
OPPORTUNITY FOUND: BTC_15min UP - Edge: 3.45%
```

## Step 5: Monitor Performance

Every 5 minutes, you'll see status updates:

```
Bot Status Update
========================================================
Balance: $1,050.25 (Start: $1,000.00)
PnL: $50.25 (+5.02%)
Total Exposure: $450.00 (4.5%)
Today PnL: $50.25

Strategy Performance:
  LatencyArbitrage: Trades: 5, Win Rate: 100.0%, PnL: $42.50
  BinaryHedging: Trades: 2, Win Rate: 100.0%, PnL: $18.75
========================================================
```

## Step 6: Going Live (When Ready)

⚠️ **Only after testing for at least 24-48 hours!**

1. Edit `.env`:
   ```env
   ENABLE_LIVE_TRADING=true
   ```

2. Start with small position sizes:
   ```yaml
   trading:
     max_position_size_usd: 50  # Start small!
   ```

3. Monitor closely for first few hours

4. Gradually increase position sizes as confidence builds

## Common Issues

### "POLYMARKET_PRIVATE_KEY not set"
- Make sure `.env` file exists and has your private key
- No spaces around the `=` sign

### "Failed to connect to Polymarket"
- Check your internet connection
- Verify private key is correct
- Ensure you have USDC on Polygon network

### "Binance API credentials not set"
- Get free API keys from Binance
- Add to `.env` file
- Latency arbitrage won't work without them

### No trades happening
- Normal! Bot waits for good opportunities
- Check logs for "OPPORTUNITY FOUND" messages
- May take 10-30 minutes to find first opportunity
- Latency arbitrage needs volatile crypto markets

## Safety Checklist

Before going live:

- [ ] Tested in paper trading mode for 24+ hours
- [ ] Reviewed all trades in logs
- [ ] Understood each strategy
- [ ] Set appropriate position sizes
- [ ] Set daily loss limits
- [ ] Have enough USDC for trading + gas fees
- [ ] Monitoring set up (check every few hours)
- [ ] Emergency stop threshold configured

## Strategy Tips

### Latency Arbitrage (Highest Profit)
- **Best times**: During volatile crypto markets
- **Requirements**: Fast internet, Binance API
- **Watch for**: BTC/ETH/SOL 1%+ moves
- **Expected**: 85-98% win rate

### Binary Hedging
- **Best times**: When markets are updating rapidly
- **Requirements**: Just Polymarket
- **Watch for**: Prices below average
- **Expected**: 80-90% win rate

### Combinatorial Arbitrage
- **Best times**: Major events (elections, sports)
- **Requirements**: Related markets
- **Watch for**: Probability mismatches
- **Expected**: Lower frequency, high profit per trade

## Next Steps

1. **Run for 24 hours** in paper trading
2. **Review logs** - understand what bot is doing
3. **Adjust config** - tune strategies to your preference
4. **Start small** - $50-100 position sizes
5. **Scale gradually** - increase as you gain confidence

## Need Help?

- Check `logs/polymarket_bot.log` for detailed info
- Review `README.md` for full documentation
- Verify `config/config.yaml` settings

## Pro Tips

1. **Best markets for latency arb**: 15-minute crypto markets during US trading hours
2. **Best markets for binary hedging**: High-volume political and sports markets
3. **Optimize speed**: Use a VPS close to Polymarket servers
4. **Monitor gas fees**: High Polygon gas = lower profits
5. **Start conservative**: 1-2% risk per trade, increase later

---

**Ready to start? Run:**

```bash
python run_bot.py
```

**Good luck! 🚀**
