# Technical Indicators

This directory contains documentation for Alpha Vantage technical indicators.

## Documented Indicators

### Moving Averages
- [SMA (Simple Moving Average)](./sma.md) - **Free Tier Available**
- [EMA (Exponential Moving Average)](./ema.md) - **Free Tier Available**
- [WMA (Weighted Moving Average)](./wma.md) - **Free Tier Available**
- [DEMA (Double Exponential Moving Average)](./dema.md) - **Free Tier Available**
- [TEMA (Triple Exponential Moving Average)](./tema.md) - **Free Tier Available**
- [TRIMA (Triangular Moving Average)](./trima.md) - **Free Tier Available**
- [KAMA (Kaufman Adaptive Moving Average)](./kama.md) - **Free Tier Available**
- [MAMA (MESA Adaptive Moving Average)](./mama.md) - **Free Tier Available**
- [T3 (Triple Exponential Moving Average T3)](./t3.md) - **Free Tier Available**
- [VWAP (Volume Weighted Average Price)](./vwap.md) - **Free Tier Available**

### Momentum Indicators
- [RSI (Relative Strength Index)](./rsi.md) - **Free Tier Available**
- [MACD (Moving Average Convergence Divergence)](./macd.md) - **Free Tier Available**
- [MACDEXT (MACD with Controllable Moving Average Type)](./macdext.md) - **Free Tier Available**
- [STOCH (Stochastic Oscillator)](./stoch.md) - **Free Tier Available**
- [STOCHF (Stochastic Fast)](./stochf.md) - **Free Tier Available**
- [STOCHRSI (Stochastic Relative Strength Index)](./stochrsi.md) - **Free Tier Available**
- [WILLR (Williams' %R)](./willr.md) - **Free Tier Available**
- [ROC (Rate of Change)](./roc.md) - **Free Tier Available**
- [ROCR (Rate of Change Ratio)](./rocr.md) - **Free Tier Available**
- [MOM (Momentum)](./mom.md) - **Free Tier Available**
- [MFI (Money Flow Index)](./mfi.md) - **Free Tier Available**
- [CMO (Chande Momentum Oscillator)](./cmo.md) - **Free Tier Available**
- [ULTOSC (Ultimate Oscillator)](./ultosc.md) - **Free Tier Available**
- [TRIX](./trix.md) - **Free Tier Available**
- [APO (Absolute Price Oscillator)](./apo.md) - **Free Tier Available**
- [PPO (Percentage Price Oscillator)](./ppo.md) - **Free Tier Available**
- [BOP (Balance of Power)](./bop.md) - **Free Tier Available**

### Trend Indicators
- [ADX (Average Directional Movement Index)](./adx.md) - **Free Tier Available**
- [ADXR (Average Directional Movement Index Rating)](./adxr.md) - **Free Tier Available**
- [DX (Directional Movement Index)](./dx.md) - **Free Tier Available**
- [PLUS_DI (Plus Directional Indicator)](./plus-di.md) - **Free Tier Available**
- [MINUS_DI (Minus Directional Indicator)](./minus-di.md) - **Free Tier Available**
- [PLUS_DM (Plus Directional Movement)](./plus-dm.md) - **Free Tier Available**
- [MINUS_DM (Minus Directional Movement)](./minus-dm.md) - **Free Tier Available**
- [AROON](./aroon.md) - **Free Tier Available**
- [AROONOSC (Aroon Oscillator)](./aroonosc.md) - **Free Tier Available**
- [SAR (Parabolic SAR)](./sar.md) - **Free Tier Available**

### Volatility Indicators
- [BBANDS (Bollinger Bands)](./bbands.md) - **Free Tier Available**
- [ATR (Average True Range)](./atr.md) - **Free Tier Available**
- [NATR (Normalized Average True Range)](./natr.md) - **Free Tier Available**
- [TRANGE (True Range)](./trange.md) - **Free Tier Available**
- [MIDPOINT](./midpoint.md) - **Free Tier Available**
- [MIDPRICE (Midpoint Price)](./midprice.md) - **Free Tier Available**

### Volume Indicators
- [OBV (On Balance Volume)](./obv.md) - **Free Tier Available**
- [AD (Chaikin A/D Line)](./ad.md) - **Free Tier Available**
- [ADOSC (Chaikin A/D Oscillator)](./adosc.md) - **Free Tier Available**

### Cycle Indicators (Hilbert Transform)
- [HT_TRENDLINE (Hilbert Transform - Instantaneous Trendline)](./ht-trendline.md) - **Free Tier Available**
- [HT_SINE (Hilbert Transform - Sine Wave)](./ht-sine.md) - **Free Tier Available**
- [HT_TRENDMODE (Hilbert Transform - Trend vs Cycle Mode)](./ht-trendmode.md) - **Free Tier Available**
- [HT_DCPERIOD (Hilbert Transform - Dominant Cycle Period)](./ht-dcperiod.md) - **Free Tier Available**
- [HT_DCPHASE (Hilbert Transform - Dominant Cycle Phase)](./ht-dcphase.md) - **Free Tier Available**
- [HT_PHASOR (Hilbert Transform - Phasor Components)](./ht-phasor.md) - **Free Tier Available**

### Other Indicators
- [CCI (Commodity Channel Index)](./cci.md) - **Free Tier Available**

## Common Parameters

Most technical indicators share common parameters:

- `function`: The indicator function name (e.g., `SMA`, `RSI`)
- `symbol`: Stock ticker symbol
- `interval`: Time interval (`1min`, `5min`, `15min`, `30min`, `60min`, `daily`, `weekly`, `monthly`)
- `time_period`: Number of periods for calculation (varies by indicator)
- `series_type`: Price type (`close`, `open`, `high`, `low`) - not all indicators require this
- `apikey`: Your Alpha Vantage API key
- `datatype`: Output format (`json` or `csv`)

## Rate Limits

- **Free Tier**: 25 requests per day
- **Premium Tier**: 75-1200 requests per minute (depending on plan)

## Notes

- All technical indicators are available on the free tier
- Premium tier offers higher rate limits but no additional indicator features
- Most indicators support multiple time intervals
- Response format is consistent across all indicators with metadata and technical analysis data
