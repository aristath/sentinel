# Retrieving trades history

### Description of server request parameters and a sample response:

#### Request:

```json
{
    "cmd" (string)   : "getTradesHistory",
    "SID" (string)   : "[SID by authorization]",
    "params" (array) : {
        "beginDate" (date|string) : "2020-03-23",
        "endDate"   (date|string) : "2020-04-08",
        "tradeId"   (int|null)    : 232327727,
        "max"       (int|null)    : 100,
        "nt_ticker" (string|null) : "AAPL.US",
        "curr"      (string|null) : "USD",
        "reception" (int|null)    : 1
    }
}
```

**Description of request parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| cmd |   | string | Request execution command
| SID |   | string | SID received during the user's authorization
| params |   | array | Request execution parameters
| params | beginDate | date | Request execution parameters. Period start date, format ISO 8601 YYYY-MM-DD
| params | endDate | date | Request execution parameters. Period end date, format ISO 8601 YYYY-MM-DD
| params | tradeId | int|null | Request execution parameters. From which Trade ID to start retrieving report data. Optional parameter
| params | max | int|null | Request execution parameters. Number of trades. If 0 or no parameter is specified - then all trades. Optional parameter
| params | nt_ticker | string|null | Request execution parameters. Instrument ticker. Optional parameter
| params | curr | string|null | Request execution parameters. Base currency or quote currency. Optional parameter
| params | reception | int|null | Request execution parameters. Office ID. Optional parameter

#### Response:

Getting a response if successful.

```json
/**
 * @typedef {{}} MaxTradeIdRow (max_trade_id)
 * @property {string} @text - Last Trade ID
 */

/**
 * @typedef {{}}TradeRow (trade)
 *
 * @property id (string) -  ID in the Tradernet system
* @property order_id (string) - Exchange order number
* @property p (string) -  trade price
* @property q (string) -  Quantity
* @property v (string) -  trade amount
* @property date (string|datetime) - Date of compilation
* @property profit (string) - trade profit
* @property instr_nm (string) - Security
* @property curr_c (string) - Current currency
* @property type (string) - Trade type. 1 – Buy, 2 – Sell.
* @property reception (string) - Office
* @property login (string) - Client login
* @property summ (string) - Amount
* @property curr_q (string) - number before the transaction
* @property instr_type_c (string) -  Security type
* @property mkt_id (string) -  Market
* @property instr_id (string) - Instrument ID
* @property comment (string) - Comment
* @property step_price (string) - Price increment
* @property min_step (string) - Minimum price increment
* @property rate_offer (string) - cross rate - portfolio currency to the security currency
* @property fv (string) - coefficient for securities traded in relative currencies, for example, future contracts
* @property acd (string) - Accumulated coupon interest (ACI)
* @property go_sum (string) - initial margin per trade
* @property curr_price (string) - Currency price
* @property curr_price_money (string) - Currency price
* @property curr_price_begin (string) - Starting price in currency
* @property curr_price_begin_money (string) - Starting price in currency
* @property pay_d (string) - Trade date
* @property trade_d_exch (string|datetime|NULL) - Trade time on the exchange
* @property T2_confirm (string) - Confirmation of settlement for a trade
* @property trade_nb (string) - Trade exchange number
* @property repo_close (string) - Repo closing
* @property StartCash (string) - The amount of repo opening
* @property EndCash (string) - Closing price of REPO
* @property commiss_exchange (string) - Exchange commission for a transaction on the derivatives market
* @property otc (string) - OTC trade sign
* @property details (string) - Transaction details for TN
* @property OrigClOrdID (string|NULL) -
 */

{
    "trades": {
        "max_trade_id": [
            {
                "@text": "40975888"
            }
        ],
        "trade": [
            {
                "id": 2229992229292,
                "order_id": 299998887727,
                "p": 141.4,
                "q": 20,
                "v": 2828,
                "date": "2019-08-15T10:10:22",
                "profit": ".00000000",
                "instr_nm": "AAPL.US",
                "curr_c": "USD",
                "type": 1,
                "reception": 1,
                "login": "example@domain.com",
                "summ": 2828,
                "curr_q": ".000000000000",
                "instr_type_c": 1,
                "mkt_id": 95006833,
                "instr_id": 10000005775,
                "comment": "56896\/",
                "step_price": ".02000000",
                "min_step": ".02000000",
                "rate_offer": 1,
                "fv": 100,
                "acd": ".0000000000",
                "go_sum": ".000000000000",
                "curr_price": ".000000000000",
                "curr_price_money": ".000000000000",
                "curr_price_begin": ".000000000000",
                "curr_price_begin_money": ".000000000000",
                "pay_d": "2019-08-19T00:00:00",
                "T2_confirm": "2019-08-19T00:00:00",
                "trade_nb": 299998887727,
                "repo_close": "0",
                "StartCash": ".000000",
                "EndCash": ".000000",
                "commiss_exchange": ".00000000",
                "otc": "0",
                "details": ""
            }
            ...
        ]
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
    "error" : "User is not found",
    "code"  : 7
}
```

**Description of response parameters:**

| Base parameter | Parameter | Type | Description
|---|---|---|---|
| trades |   | array | Trades
| trades | max_trade_id | array | Last Trade ID
| trades | trade | array | User's trades list

### Examples of using

## Examples

### JS (jQuery)

```json
/**
 * @type {Trades}
 */
var exampleParams = {
    "cmd"    : "getTradesHistory",
    "SID"    : "[SID by authorization]",
    "params" : {
        "beginDate" : "2020-03-23",
        "endDate"   : "2020-04-08",
        "tradeId"   : 232327727,
        "max"       : 100,
        "nt_ticker" : "AAPL.US",
        "curr"      : "USD",
        "reception" : 1
    }
};

function getTradesHistory(callback) {
    $.getJSON("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getTradesHistory(function(json){
    console.log(json);
});
```
