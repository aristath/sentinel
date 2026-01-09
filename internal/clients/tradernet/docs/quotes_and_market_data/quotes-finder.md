# Stock tickers search.

### Description of the server reply and an example of the reply

## Examples

```json
/**
 * @typedef {{}} TickerFinderDataRow

* @property {number} instr_id -  unique ticker ID
* @property {string} nm - name is too long
* @property {string} n - name
* @property {string} ln - English name
* @property {string} t - ticker in Tradernet's system
* @property {string} isin - Ticker ISIN code
* @property {number} type - Instrument type
* @property {number} kind - Instrument sub-type
    type 1 kind 1 - Regular stock
    type 1 kind 2 - Preferred stock
    type 1 kind 7 - Investment units
    type 2 - Bonds
    type 3 - Futures
    type 5 - Exchange index
    type 6 kind 1 - Cash
    type 6 kind 8 - Сrypto
    type 8,9,10 - Repo
* @property {string} tn - Ticker plus name
* @property {string} code_nm - exchange ticker
* @property {number} mkt_id - Market code
* @property {string} mkt - market
 */

/**
 * @typedef {{}} TickerFinderResult
 * @property {TickerFinderDataRow[]} found - list of found tickers
 */
```

```json
/**
 * @typedef {{}} TickerFinderDataRow

* @property {number} instr_id -  unique ticker ID
* @property {string} nm - name is too long
* @property {string} n - name
* @property {string} ln - English name
* @property {string} t - ticker in Tradernet's system
* @property {string} isin - Ticker ISIN code
* @property {number} type - Instrument type
* @property {number} kind - Instrument sub-type
    type 1 kind 1 - Regular stock
    type 1 kind 2 - Preferred stock
    type 1 kind 7 - Investment units
    type 2 - Bonds
    type 3 - Futures
    type 5 - Exchange index
    type 6 kind 1 - Cash
    type 6 kind 8 - Сrypto
    type 8,9,10 - Repo
* @property {string} tn - Ticker plus name
* @property {string} code_nm - exchange ticker
* @property {number} mkt_id - Market code
* @property {string} mkt - market
*/

$responseExample = [
    'found' => [
        [0] => [
            "instr_id":"1005554",
             "nm":"Apple inc.",
             "n":"Apple inc.",
             "ln":"Apple",
             "t":"AAPL.US",
             "isin":"US0000001",
             "type":1,
             "kind":1,
             "tn":"Apple inc.",
             "code_nm":"AAPL.US",
             "mkt_id":"900000001",
             "mkt":"FIX"
        ]
    ]
    'code' => 0
]
```

### Examples of using

## Examples

### Browser

```json
/**
 * @typedef {{
 *  search: string,
 *  q: {
 *      cmd: 'tickerFinder',
 *      params: {
 *          text: string
 *      }
 *  }
 * }} TickerFinderQueryParams
 */

Search on the specified Exchange

q:{
    "cmd":"tickerFinder",
    "params":{
        "text": '<ticker>@<market>'
    }
}

where:
    ticker: search bar {string}
    market:
        'MCX' - MICEX
        'FORTS' - MICEX Derivatives
                'FIX' - NYSE/NASDAQ
        'UFORTS' - Ukrainian Derivatives Exchange
        'UFOUND' - Ukrainian Exchange
        'EU' - Europe
        'KASE' - Kazakhstan
/**
 * @param {string} phrase
 * @param {function} callback
 */
function findTickers(phrase, callback) {
    /**
     * @type {TickerFinderQueryParams}
     */
    var queryParams = {
        q: {
            cmd: 'tickerFinder',
            params: {
                text: phrase.toLowerCase()
            }
        }
    };


    $.getJSON('https://tradernet.com/api', queryParams, callback);
}

findTickers('AAPL.US',

    /**
     * @param {TickerFinderResults} data
     */
    function (data) {
        console.info(data);
    }
);
```

### PHP

```php
/**

* @param {string} text - Search bar
    text = '<ticker>
    text = '<ticker>@<market>'
*/

where:
ticker: search bar {string}
market:
    'MCX' - MICEX
    'FORTS' - MICEX Derivatives
    'FIX' - NYSE/NASDAQ
    'UFORTS' - Ukrainian Derivatives Exchange
    'UFOUND' - Ukrainian Exchange
    'EU' - Europe

    'KASE' - Kazakhstan


$publicApiClient = new PublicApiClient($apiKey, $apiSecretKey, Nt\PublicApiClient::V1);

$responseExample = $publicApiClient->sendRequest('tickerFinder', ['text'=> 'AAPL.US'], 'array');
```
