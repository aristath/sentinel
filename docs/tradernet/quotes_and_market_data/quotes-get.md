# Receive quotes.

### Description of response data from the server

| c | Ticker
|---|---|
| ltr | Exchange of the latest trade
| name | Name of security
| name2 | Security name in Latin
| bbp | Best bid
| bbc | Designations of the best bid changes (\'\' – no changes, \'D\' - down, \'U\' - up)
| bbs | Best bid size
| bbf | Best bid volume
| bap | Best offer
| bac | Designations of price change (\'\' – no changes, \'D\' - down, \'U\' - up)
| bas | Value (size) of the best offer
| baf | Volume of the best offer
| pp | Previous closing
| op | Opening price of the current trading session
| ltp | Last trade price
| lts | Last trade size
| ltt | Time of last trade
| chg | Change in the price of the last trade in points, relative to the closing price of the previous trading session
| pcp | Percentage change relative to the closing price of the previous trading session
| ltc | Designations of price change (\'\' – no changes, \'D\' - down, \'U\' - up)
| mintp | Minimum trade price per day
| maxtp | Maximum trade price per day
| vol | Trade volume per day, in pcs
| vlt | Trading volume per day in currency
| yld | Yield to maturity (for bonds)
| acd | Accumulated coupon interest (ACI)
| fv | Face value
| mtd | Maturity date
| cpn | Coupon, in the currency
| cpp | Coupon period (in days)
| ncd | Next coupon date
| ncp | Latest coupon date
| dpb | Purchase margin
| dps | Short sale margin
| trades | Number of trades
| min_step | Minimum price increment
| step_price | Price increment
| strike_price | Option strike

```json
$responseExample = [
       'result' => [
              'q' => [
                     '0' => [
                            'c' => 'AAPL.US'
                            'mrg' => 'M',
                            'bbp' => '147,39',
                            'bbs' => '89170',
                            'bbc' => '',
                            'bbf' => '0',
                            'bap' => '147,45',
                            'bas' => '46250',
                            'bac' => 'U',
                            'baf' => '0',
                            'pp' => '147,95',
                            'op' => '147,95',
                            'ltp' => '147,42',
                            'lts' => '4380',
                            'ltt' => '2016-10-05T17:04:43',
                            'ltr' => '',
                            'ltc' => 'U',
                            'mintp' => '144',
                            'maxtp' => '151,9',
                            'pcp' => '-0,36',
                            'vol' => '129617290',
                            'vlt' => '3816983,97',
                            'yld' => '0',
                            'acd' => '0',
                            'mtd' => '',
                            'cpn' => '0',
                            'cpp' => '0',
                            'ncd' => '',
                            'dpb' => '0',
                            'dps' => '0',
                            'ncp' => '0',
                            'chg' => '-0,53',
                            'trades' => '0',
                            'min_step' => '0,01',
                            'step_price' => '0,01',
                            'kind' => '1',
                            'type' => '1',
                            'name' => 'Apple Inc.',
                            'name2' => 'Apple Inc.',
                     ]
              ]
    ]
]
```

### Examples of using

## Examples

### JS

```php
/**
 * @type {getStockQuotesJson}
 */
var exampleParams = {
    "cmd": "getStockQuotesJson",
    "params": {
        "tickers": ["AAPL.US","F.US"],
    },
};

function getStockQuotesJson(callback) {
    $.post("https://tradernet.com/api/", {q: JSON.stringify(exampleParams)}, callback);
}

/**
 * Get the object **/
getStockQuotesJson(function(json){
    console.log(json);
});
```

### PHP

```php
/**
* @param {string} tickers -  One or more tickers with +
*/

$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V2);

//  Based on one instrument
$responseExample = $publicApiClient->sendRequest('getStockQuotesJson', ['tickers' => "AAPL.US"]);

//  Based on several instruments
$responseExample = $publicApiClient->sendRequest('getStockQuotesJson', ['tickers' => ["AAPL.US","T.US"]]);
```

### REST

You can get quotes in JSON format by direct query to the server, separating tickers and necessary parameters with the + sign, for example

/securities/export?tickers=USD/KZT+EUR/KZT
