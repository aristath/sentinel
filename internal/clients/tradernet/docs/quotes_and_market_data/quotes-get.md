# Receive quotes.

### Description of response data from the server

[!]  The same fields can be specified in the search parameters


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
