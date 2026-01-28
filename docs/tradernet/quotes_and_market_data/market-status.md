# Market status list

### Description of server request parameters and a sample response:

Obtaining information about market statuses and operation.

#### Request:

```json
{
    "cmd"    (string) : "getMarketStatus",
    "params" (array)  : {
        market (string)      : "*",
        mode   (string|null) : "demo"
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| params |   | array | Request execution parameters
| params | market | string #### Response:

Getting a response if successful.

```json
            params
            mode
            string|null







        Market list


            Full title
            Abbreviated name




            *

            all markets


                AMX
                Armenia Securities Exchange
                AMX


                AIX
                Astana International Exchange
                AIX


                ATHEX
                Athens Stock Exchange
                ATHEX


                BEB.RUS
                BEB. The market for the conversions calendar
                BEB.RUS


                BEX
                BEX Best Execution
                BEX


                Broker Quote System (BQS)
                Broker Quote System (BQS)
                SBQ


                US_OPT
                CBOE (US Options)
                US_OPT


                CMX
                COMEX (Commodity Exchange)
                CMX


                CBF
                Cboe Futures Exchange
                CBF


                CBT
                Chicago Board of Trade
                CBT


                CME
                Chicago Mercantile Exchange
                CME


                SecForCrypto
                Crypto
                SecForCrypto


                FINERY
                Crypto Finery Market
                FINERY


                CRPT
                Cryptocurrency market
                CRPT


                EU
                EU Europe
                EU


                EXANTE
                EXANTE
                EXANTE


                EASTE
                East Exchange
                EASTE


                EUX
                Eurex
                EUX


                EUROBOND
                Eurobonds
                EUROBOND


                FORTS
                FORTS Market FORTS
                FORTS


                FFSP
                Freedom Finance Structural Products
                FFSP


                HKG
                Hong Kong Futures Exchange
                HKG


                HKEX
                Hong Kong Stock Exchange
                HKEX


                EDX
                ICE Endex
                EDX


                NYB
                ICE Futures U.S.
                NYB


                WCE
                ICE Futures US-Canadian Grains
                WCE


                IMEX
                IMEX Crypto Market
                IMEX


                ISF
                ISF: ICE Futures Europe S2F
                ISF


                ITS
                ITS
                ITS


                ITS_MONEY
                ITS Money Market
                ITS_MONEY


                ICE
                Intercontinental Exchange
                ICE


                KASE
                Kazakhstan Stock Exchange
                KASE


                KASE.CUR
                Kazakhstan Stock Exchange. Currency section
                KASE.CUR


                Kraken
                Kraken Crypto Exchange
                Kraken


                LME
                LME: London Metal Exchange
                LME


                LMAX
                Lmax currency
                LMAX


                MCX.CUR
                MCX Currency. Currency exchange
                MCX.CUR


                MCX.OTC
                MCX Over-The-Counter Market
                MCX.OTC


                MCX.nottraded
                MCX.nottraded
                MCX.nottraded


                MOEX
                MICEX. Stock market
                MCX


                MONEY
                MONEY Foreign Exchange Market
                MONEY


                OTC.xxxx.RUR
                Market for settlement of forwards on foreign stocks for Russian Rubles
                OTC.xxxx.RUR


                MBANK_EU
                MayBank EU Instruments
                MBANK_EU


                MBANK
                MayBank HKE Instruments
                MBANK


                MBANK_US
                MayBank US Instruments
                MBANK_US


                MGE
                Minneapolis Grain Exchange (MGEX)
                MGE


                NGC
                NSE IFSC
                NGC


                NYF
                NYF - ICE Futures US Indices
                NYF


                FIX
                NYSE/NASDAQ
                FIX


                NSE
                Natl Stock Exchange of India
                NSE


                NYM
                New York Mercantile Exchange
                NYM


                FIX.OTC
                OTC. Foreign securities.
                FIX.OTC


                PFTS_OBL
                PFTS. Obligations
                PFTS_OBL


                PFTS_SPOT
                PFTS. Spot
                PFTS_SPOT


                PRSP_OBL
                Perspektiva market. Obligations
                PRSP_OBL


                PRSP_SPOT
                Perspektiva market. Spot
                PRSP_SPOT


                RTSBoard
                RTSBoard РТС board
                RTSBoard


                UZSE
                Republican Stock Exchange "Toshkent" (UZSE)
                UZSE


                SGC
                SGQ system of guaranteed quotes on RTS
                RTS


                SGX
                SGX: Singapore Exchange
                SGX


                SPBFOR
                SPB Foreign securities.
                SPBFOR


                SPBEX
                SPB. Russian securities.
                SPBEX


                KASE.OTC
                Store. Kazakhstan. F24
                KASE.OTC


                TABADUL
                Tabadul Exchange
                TABADUL


                UB_OBL
                UB. Obligations
                UB_OBL


                UKR_FORTS
                UKR_FORTS FORTS Ukraine
                UFORTS


                UKR_FOUND
                UKR_FOUND Stock Ukraine
                UFOUND


                UX.OTC
                UX Over-The-Counter Market
                UX.OTC









/**
 * @property {string} t  - Current request time
 *
 * @typedef {m: {}} MarketInfoRow
 * @property {string} n  - Full market name
 * @property {string} n2 - Market abbreviation
 * @property {string} s  - Current market status
 * @property {string} o  - Market opening time (MSK)
 * @property {string} dt - Time difference in regards to MSK time (in minutes)
**/

{
  "result" : {
    "markets" : {
      "t"     : "2020-11-18 19:29:27",
      "m"     : [
        {
          "n"  : "KASE",
          "n2" : "KASE",
          "s"  : "CLOSE",
          "o"  : "08:20:00",
          "c"  : "14:00:00",
          "dt" : "-180"
        }
      ]
    }
  }
}
```

We get an answer in case of failure

```json
// Common error
{
    "errMsg" : "Bad json",
    "code"   : 2
}

// Method error
{
    "error" : "Something wrong, service unavailable",
    "code"  : 14
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| result | markets | array[ ] | Market status list array

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {getMarketStatus}
 */
var paramsToGetStatus = {
    "cmd"    : "getMarketStatus",
    "params" : {
        market : "*",
        mode   : "demo"
    }
};

/**
 * The request allows you to get updates on the market status directly from the server
 */
function getMarketStatuses(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(paramsToGetStatus)}, callback);
}

getMarketStatuses(function (json) {
    console.info(json);
});
```

### Websockets

The server sends the 'markets' event with market status updates

```json
ws.onmessage = function (m) {
    const [event, data] = JSON.parse(m.data);
    if (event === 'markets') {
        console.info(data);
    }
);

ws.onopen = function() { // Waiting for the connection to open
    ws.send(JSON.stringify(["markets"]));
}
```
